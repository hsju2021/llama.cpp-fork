#!/usr/bin/env python3

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"


def fields_from_line(line):
    return dict(re.findall(r"([a-z_]+)=([^ ]+)", line))


def parse_log(path):
    calls = []
    current = None
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if "compute_profile_trace start:" in line:
            values = fields_from_line(line.split("compute_profile_trace start:", 1)[1])
            current = {
                "line_start": line_number,
                "run": int(values["run"]),
                "call": int(values["call"]),
                "retry": int(values["retry"]),
                "off": int(values["off"]),
                "n_tokens": int(values["n_tokens"]),
                "n_prefill": int(values["n_prefill"]),
                "n_decode": int(values["n_decode"]),
                "n_unknown": int(values["n_unknown"]),
                "phase": values["phase"],
                "mode": values["mode"],
                "requested_profile": values["requested_profile"],
                "slots": values["slots"],
                "tasks": values["tasks"],
                "t_start_us": int(values["t_start_us"]),
                "ubatches": [],
            }
        elif current is not None and "graph_compute: requested profile" in line:
            match = re.search(r"requested profile = ([a-z]+), resolved profile = ([a-z]+), n_tokens = ([0-9]+), n_threads = ([0-9]+), threadpool = ([a-z]+)", line)
            if match:
                current["ubatches"].append({
                    "line_profile": line_number,
                    "requested_profile": match.group(1).upper(),
                    "resolved_profile": match.group(2).upper(),
                    "n_tokens": int(match.group(3)),
                    "selected_threads": int(match.group(4)),
                    "threadpool_name": match.group(5),
                })
        elif current is not None and "ggml_graph_compute: planned_threads=" in line:
            values = fields_from_line(line.split("ggml_graph_compute:", 1)[1].replace(",", ""))
            if current["ubatches"]:
                current["ubatches"][-1].update({
                    "line_team": line_number,
                    "planned_threads": int(values["planned_threads"]),
                    "actual_team_size": int(values["actual_team_size"]),
                    "pool_threads": int(values["pool_threads"]),
                    "disposable_threadpool": values["disposable_threadpool"],
                })
        elif current is not None and "compute_profile_trace end:" in line:
            values = fields_from_line(line.split("compute_profile_trace end:", 1)[1])
            current.update({
                "line_end": line_number,
                "ret": int(values["ret"]),
                "return_elapsed_us": int(values["return_elapsed_us"]),
                "complete_elapsed_us": int(values["complete_elapsed_us"]),
            })
            calls.append(current)
            current = None
    return calls


def expected_profile(call):
    if call["mode"] == "legacy":
        return "LEGACY"
    if call["mode"] == "auto":
        return "AUTO"
    return {
        "PREFILL": "BATCH",
        "DECODE": "GENERATION",
        "MIXED": "AUTO",
        "UNKNOWN": "AUTO",
    }[call["phase"]]


def representative(calls, predicate):
    call = next(call for call in calls if predicate(call))
    return call


all_calls = {}
summary = {}
for path in sorted(LOGS.glob("functional-*-t*-tb*.log")):
    calls = parse_log(path)
    all_calls[path.name] = calls
    counts = Counter(call["phase"] for call in calls)
    phase_counts = {phase: counts[phase] for phase in ("PREFILL", "DECODE", "MIXED", "UNKNOWN")}
    mapping_errors = [call["call"] for call in calls if call["requested_profile"] != expected_profile(call)]
    token_count_errors = [
        call["call"]
        for call in calls
        if call["n_prefill"] + call["n_decode"] + call["n_unknown"] != call["n_tokens"]
    ]
    resource_errors = []
    for call in calls:
        for ubatch in call["ubatches"]:
            if ubatch.get("planned_threads") != ubatch["selected_threads"] or ubatch.get("actual_team_size") != ubatch["planned_threads"]:
                resource_errors.append(call["call"])
    summary[path.name] = {
        "calls": len(calls),
        "phase_counts": phase_counts,
        "phase_ratios": {phase: count / len(calls) for phase, count in phase_counts.items()},
        "retry_calls": sum(call["retry"] > 0 for call in calls),
        "nonzero_returns": sum(call["ret"] != 0 for call in calls),
        "token_count_errors": token_count_errors,
        "profile_mapping_errors": mapping_errors,
        "resource_mapping_errors": sorted(set(resource_errors)),
    }

phase_calls = all_calls["functional-phase-t2-tb6.log"]
auto_calls = all_calls["functional-auto-t2-tb6.log"]
evidence = {
    "single_token_prefill_phase": representative(phase_calls, lambda call: call["phase"] == "PREFILL" and call["n_tokens"] == 1),
    "multi_request_decode_phase": representative(phase_calls, lambda call: call["phase"] == "DECODE" and call["n_decode"] >= 4),
    "multi_request_decode_auto": representative(auto_calls, lambda call: call["phase"] == "DECODE" and call["n_decode"] >= 4),
    "mixed_phase": representative(phase_calls, lambda call: call["phase"] == "MIXED"),
}

lifecycle = []
phase_path = LOGS / "functional-phase-t2-tb6.log"
for line_number, line in enumerate(phase_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
    relevant_task = "task 273" in line or "task 285" in line or "id_task = 273" in line
    relevant_event = "new prompt" in line or "cancel task" in line or "release:" in line or "reset:" in line
    if relevant_task and relevant_event:
        lifecycle.append({"line": line_number, "text": line})

output = {
    "summary": summary,
    "representative_evidence": evidence,
    "lifecycle_evidence": lifecycle,
}
(ROOT / "analysis" / "trace-summary.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
