#!/usr/bin/env python3
"""Standard-library tests; every child server is the model-free fixture."""

import base64
import contextlib
import json
import os
import signal
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import runner
import overhead
import check_threadpools


FIXTURE = Path(__file__).with_name("fixture_server.py")


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.cancel = threading.Event()

    def tearDown(self):
        self.temp.cleanup()

    @contextlib.contextmanager
    def server(self, scenario="normal", *extra):
        port = runner.free_port()
        command = [sys.executable, str(FIXTURE), "--port", str(port), "--scenario", scenario, *extra]
        server = runner.Server(command, port, self.directory / f"{port}.log", 0.15)
        try:
            server.start(2, self.cancel)
            yield server
        finally:
            server.stop()
        self.assertTrue(server.cleanup["leader_reaped"])
        with self.assertRaises(ProcessLookupError):
            os.kill(server.process.pid, 0)

    def request(self, server, n=8, timeout=1):
        return runner.stream_request(server.port, {"prompt": [1, 2], "n_predict": n}, "decode_0",
                                     self.directory / f"raw-{server.port}.jsonl", timeout, self.cancel)

    def test_stream_raw_grouping_and_terminal_summary(self):
        for scenario in ("normal", "terminal_tokens"):
            with self.subTest(scenario=scenario), self.server(scenario, "--group-size", "2", "--interval", "0") as server:
                result = self.request(server)
                self.assertEqual(result["status"], "ok", result)
                self.assertEqual(result["streamed_tokens"], 8)
                metrics = runner.request_metrics(result)
                self.assertEqual(metrics["grouped_events"], 4)
                self.assertEqual(metrics["valid_token_intervals_ms"], [])
                self.assertIsNone(metrics["p95_token_interval_ms"])
                raw = [json.loads(line) for line in Path(result["raw_sse"]).read_text().splitlines()]
                self.assertTrue(base64.b64decode(raw[0]["raw_b64"]).startswith(b": fixture ping"))
                self.assertTrue(all(a["t_ns"] <= b["t_ns"] for a, b in zip(raw, raw[1:])))

    def test_failures_preserve_partial_records(self):
        for scenario in ("http_error", "malformed", "sse_error", "truncated", "disconnect", "count_mismatch"):
            with self.subTest(scenario=scenario), self.server(scenario) as server:
                result = self.request(server)
                self.assertEqual(result["status"], "failed", result)
                self.assertIn("error", result)
                self.assertGreaterEqual(result["end_ns"], result["start_ns"])
                if scenario == "truncated":
                    self.assertTrue(json.loads(Path(result["raw_sse"]).read_text())["incomplete"])

    def test_hard_deadline_including_trickled_stream(self):
        for scenario in ("idle", "trickle"):
            with self.subTest(scenario=scenario), self.server(scenario) as server:
                start = time.monotonic()
                result = self.request(server, timeout=0.12)
                self.assertEqual(result["status"], "timeout", result)
                self.assertLess(time.monotonic() - start, 0.8)

    def test_cancellation_interrupts_read(self):
        with self.server("idle") as server:
            timer = threading.Timer(0.08, self.cancel.set)
            timer.start()
            try:
                result = self.request(server, timeout=2)
                self.assertEqual(result["status"], "cancelled")
                self.assertLess((result["end_ns"] - result["start_ns"]) / 1e9, 0.8)
            finally:
                timer.join()

    def test_startup_exit_and_readiness_timeout(self):
        for scenario, error in (("startup_exit", RuntimeError), ("unready", TimeoutError)):
            port = runner.free_port()
            server = runner.Server([sys.executable, str(FIXTURE), "--port", str(port), "--scenario", scenario],
                                   port, self.directory / "startup.log", 0.15)
            try:
                with self.assertRaises(error):
                    server.start(2 if scenario == "startup_exit" else 0.25, self.cancel)
            finally:
                server.stop()
            self.assertIsNotNone(server.process.returncode)

    def test_cleanup_kills_descendants_and_unresponsive_leader(self):
        for scenario in ("normal", "ignore_term"):
            pid_path = self.directory / "grandchild.pid"
            with self.server(scenario, "--grandchild-pid", str(pid_path)) as server:
                pid = int(pid_path.read_text())
            self.assertEqual(server.cleanup["forced_leader_kill"], scenario == "ignore_term")
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                try:
                    state = Path(f"/proc/{pid}/stat").read_text().split(") ")[1].split()[0]
                except FileNotFoundError:
                    break
                if state == "Z":
                    break
                time.sleep(0.01)
            else:
                self.fail("grandchild still running")

    def test_metric_arithmetic_and_grouped_boundaries(self):
        def event(ms, tokens, **extra):
            return {"t_ns": ms * 1_000_000, "data": {"tokens": tokens, **extra}}

        request = {"role": "decode_0", "status": "ok", "start_ns": 0, "end_ns": 160_000_000, "output_tokens": 6,
                   "events": [event(5, [-1], prompt_progress={}), event(10, [1]), event(30, [2]),
                              event(90, [3, 4]), event(100, [5]), event(150, [6]), event(155, list(range(6)), stop=True)]}
        metrics = runner.request_metrics(request)
        self.assertEqual(metrics["valid_token_intervals_ms"], [20, 50])
        self.assertEqual(metrics["p95_token_interval_ms"], 50)
        self.assertEqual(metrics["ttft_ms"], 10)
        self.assertEqual(metrics["completion_ms"], 160)
        self.assertEqual(metrics["max_event_gap_ms"], 60)
        self.assertEqual(metrics["terminal_silence_ms"], 10)
        self.assertEqual(metrics["interval_coverage"], 0.4)
        trial = runner.trial_metrics([request], 3, 0.2, 2)
        self.assertEqual(trial["throughput_tokens_s"], 3)
        self.assertEqual(trial["cpu_s_per_output_token"], 0.5)
        self.assertEqual(trial["client_cpu_s_per_output_token"], 0.2 / 6)
        self.assertEqual(trial["worst_request_p95_interval_ms"], 50)
        self.assertEqual(runner.percentile(list(range(1, 21))), 19)
        request["status"] = "cancelled"
        self.assertIsNone(runner.trial_metrics([request], 3, 0.2, 2)["throughput_tokens_s"])

    def config(self):
        return {**runner.DEFAULTS, "conditions": [{"threads": 1, "batch_threads": 2, "profile": "auto"}],
                "server": sys.executable, "model": str(self.directory / "fixture.gguf"), "model_description": "fixture bytes; no model",
                "build_cache": str(self.directory / "CMakeCache.txt"), "repetitions": 1,
                "prompt_tokens": 16, "output_tokens": 20, "long_prompt_tokens": 512, "long_output_tokens": 2,
                "inject_after_tokens": 2, "ready_timeout_s": 2, "request_timeout_s": 2, "trial_timeout_s": 3}

    def test_all_workloads_and_overlap_rejection(self):
        config = self.config()
        with self.server() as server:
            prompts = runner.make_prompts(server.port, config)
            self.assertEqual(len(prompts["short"]), 16)
            for name in runner.WORKLOADS:
                with self.subTest(workload=name):
                    result = runner.workload(server, config, name, prompts, self.directory / name, self.cancel)
                    self.assertEqual(result["status"], "ok", result)
                    self.assertGreaterEqual(result["metrics"]["client_cpu_s"], 0)
                    self.assertGreaterEqual(result["metrics"]["server_cpu_s"], 0)
                    if name.startswith("m"):
                        self.assertTrue(result["metrics"]["overlap"]["valid"])
        with self.server("no_overlap") as server:
            result = runner.workload(server, config, "m1", prompts, self.directory / "no-overlap", self.cancel)
            self.assertEqual(result["status"], "invalid_overlap", result)
            self.assertIsNone(result["metrics"]["throughput_tokens_s"])

    def test_randomized_blocks_and_validation(self):
        config = self.config()
        config["conditions"] *= 2
        config["repetitions"] = 3
        self.assertEqual(runner.execution_order(config), runner.execution_order(config))
        self.assertEqual(len(runner.execution_order(config)), 36)
        for rep in range(3):
            self.assertEqual(len({(r["condition"], r["workload"]) for r in runner.execution_order(config) if r["repetition"] == rep}), 12)
        path = self.directory / "config.json"
        path.write_text(json.dumps(config))
        self.assertEqual(runner.load_config(path)["conditions"], config["conditions"])
        config["request_timeout_s"] = float("inf")
        path.write_text(json.dumps(config))
        with self.assertRaises(ValueError):
            runner.load_config(path)

    def test_cpu_pool_controls(self):
        config = self.config()
        condition = config["conditions"][0]
        condition.update(poll=0, poll_batch=1, cpu_mask="0x3", cpu_mask_batch="C",
                         cpu_strict=1, cpu_strict_batch=0, priority=0, priority_batch=0)
        path = self.directory / "config.json"
        path.write_text(json.dumps(config))
        loaded = runner.load_config(path)
        command = runner.server_command(loaded, loaded["conditions"][0], 1234)
        for key, flag in runner.CPU_FLAGS.items():
            self.assertEqual(command[command.index(flag) + 1], str(condition[key]))
        for key, value in (("cpu_mask", "--bad"), ("cpu_mask", "0X3"), ("cpu_mask", "f" * 129), ("cpu_mask_batch", ""), ("cpu_strict", 2),
                           ("cpu_strict_batch", True), ("priority", -2), ("priority_batch", -1)):
            with self.subTest(key=key):
                bad = json.loads(path.read_text())
                bad["conditions"][0][key] = value
                invalid = self.directory / "invalid.json"
                invalid.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    runner.load_config(invalid)

    def test_threadpool_diagnostics_exclude_startup_and_require_evidence(self):
        path = self.directory / "server.log"
        startup = b"startup: disposable_threadpool=yes\n"
        path.write_bytes(startup + b"decode: disposable_threadpool=no\n")
        self.assertEqual(check_threadpools.pool_diagnostics(path, len(startup), "no"), ["no"])
        with self.assertRaises(RuntimeError):
            check_threadpools.pool_diagnostics(path, 0, "no")
        with self.assertRaises(RuntimeError):
            check_threadpools.pool_diagnostics(path, path.stat().st_size, "no")
        with self.assertRaises(RuntimeError):
            check_threadpools.pool_diagnostics(path, len(startup), "yes")
        snapshot = check_threadpools.task_snapshot(os.getpid())
        task = next(task for task in snapshot["tasks"] if task["tid"] == threading.get_native_id())
        self.assertEqual(task["allowed_cpus"], sorted(os.sched_getaffinity(0)))
        self.assertGreater(task["start_ticks"], 0)

    def test_threadpool_diagnostic_failure_still_stops_server(self):
        output = self.directory / "diagnostics"
        stopped = []

        class FakeServer:
            def __init__(self, command, port, log_path, *args):
                self.log_path = log_path
                self.process = type("Process", (), {"pid": os.getpid()})()
                self.cleanup = None

            def start(self, *args):
                self.log_path.write_text("startup\n")

            def stop(self):
                stopped.append(True)
                self.cleanup = {"forced_leader_kill": False, "returncode": 0, "leader_reaped": True}

        args = ["check_threadpools.py", "--config", "unused.json", "--run", "--output", str(output)]
        with contextlib.ExitStack() as stack:
            for target, value in (("load_config", self.config()), ("existing_servers", []),
                                  ("manifest", {}), ("process_environment", {}), ("loaded_libraries", []),
                                  ("json_request", {}), ("make_prompts", {}), ("workload", {"status": "failed"})):
                stack.enter_context(patch.object(runner, target, return_value=value))
            stack.enter_context(patch.object(runner, "Server", FakeServer))
            stack.enter_context(patch.object(sys, "argv", args))
            stack.enter_context(patch.object(check_threadpools.signal, "signal"))
            self.assertEqual(check_threadpools.main(), 1)
        report = json.loads((output / "report.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertTrue(report["cleanup"]["leader_reaped"])
        self.assertEqual(stopped, [True])

    def test_campaign_warmup_failure_and_partial_status(self):
        config = self.config()
        config["workloads"] = ["d1", "d2"]
        Path(config["model"]).write_bytes(b"model-free fixture identity")
        Path(config["build_cache"]).write_text("FIXTURE_ONLY:BOOL=ON\n")

        def command(config, condition, port):
            return [sys.executable, str(FIXTURE), "--port", str(port), "--scenario", "http_error"]

        with patch.object(runner, "server_command", command), patch.object(runner, "existing_servers", return_value=[]):
            output = self.directory / "campaign"
            self.assertEqual(runner.run_campaign(config, output, self.cancel), 1)
        rows = json.loads((output / "trials.json").read_text())
        self.assertTrue(all(r["status"] == "failed" and r["failed_stage"] == "warmup" for r in rows))
        self.assertTrue(all(r["cleanup"]["leader_reaped"] for r in rows))
        self.assertEqual(json.loads((output / "summary.json").read_text())["status"], "completed_with_failures")
        self.assertFalse(list(output.glob("trial-*/measurement")))
        manifest = json.loads((output / "manifest.json").read_text())
        self.assertEqual(manifest["model_files"][0]["sha256"], runner.sha256(config["model"]))

    def test_campaign_success_and_cancel_during_measurement(self):
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled):
                config = self.config()
                config["workloads"] = ["m1", "d1"]
                Path(config["model"]).write_bytes(b"not a model")
                Path(config["build_cache"]).write_text("FIXTURE_ONLY:BOOL=ON\n")

                def command(config, condition, port):
                    return [sys.executable, str(FIXTURE), "--port", str(port)]

                real_workload = runner.workload

                def workload(server, config, name, prompts, directory, cancel):
                    timer = None
                    if cancelled and directory.name == "measurement":
                        timer = threading.Timer(0.03, cancel.set)
                        timer.start()
                    try:
                        return real_workload(server, config, name, prompts, directory, cancel)
                    finally:
                        if timer:
                            timer.join()

                output = self.directory / ("success" if not cancelled else "cancel-active")
                with patch.object(runner, "server_command", command), patch.object(runner, "existing_servers", return_value=[]), patch.object(runner, "workload", workload):
                    code = runner.run_campaign(config, output, self.cancel)
                self.assertEqual(code, 130 if cancelled else 0)
                rows = json.loads((output / "trials.json").read_text())
                if cancelled:
                    self.assertEqual([r["status"] for r in rows], ["cancelled", "not_started"])
                else:
                    self.assertTrue(all(r["status"] == "ok" and r["metrics"]["valid"] for r in rows))
                self.assertTrue(rows[0]["cleanup"]["leader_reaped"])

    def test_overhead_validation_and_failed_budget(self):
        report = overhead.run_check(self.directory / "overhead", events=30, concurrencies=(2,), intervals=(0.001,), group_sizes=(1, 4), max_p95_lag_ms=1000)
        self.assertEqual(report["status"], "ok", report)
        for case in report["cases"]:
            self.assertEqual(case["received_events"], 60)
            self.assertGreater(case["client_cpu_s"], 0)
            self.assertTrue(case["cleanup"]["leader_reaped"])
        report = overhead.run_check(self.directory / "overhead-fail", events=2, concurrencies=(1,), intervals=(0,), group_sizes=(1,), max_p95_lag_ms=0)
        self.assertEqual(report["status"], "failed")

    def test_overlap_requires_server_observation(self):
        config = self.config()
        with self.server() as server:
            result = runner.workload(server, config, "m1", runner.make_prompts(server.port, config), self.directory / "overlap", self.cancel)
        self.assertTrue(result["metrics"]["overlap"]["valid"])
        self.assertFalse(runner.overlap_evidence(result["requests"], [])["valid"])
        for observation in result["slot_observations"]:
            for slot in observation.get("slots", []):
                if slot["id"] == 1:
                    slot["n_prompt_tokens_processed"] = config["long_prompt_tokens"]
        self.assertFalse(runner.overlap_evidence(result["requests"], result["slot_observations"])["valid"])

    def test_campaign_pre_cancel_and_manifest_failure(self):
        config = self.config()
        self.cancel.set()
        output = self.directory / "cancelled"
        self.assertEqual(runner.run_campaign(config, output, self.cancel), 130)
        self.assertTrue(all(r["status"] == "not_started" for r in json.loads((output / "trials.json").read_text())))
        self.assertEqual(json.loads((output / "summary.json").read_text())["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
