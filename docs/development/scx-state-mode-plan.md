# SCX state notification implementation plan

Server v2 publication, CPU worker marker cleanup, and scheduler v2 reception are complete. The local build and unprivileged test milestone has passed. Native-kernel validation and matched performance trials are pending.

Drafted 2026-10-03. Updated 2026-11-22.

## Goal

Reduce uprobe hits during repeated decode work while preserving the existing v1 diagnostic path. The scope covers phase notification, attachment, lifecycle handling, and validation with the existing compute-profile routing.

Skipping duplicate state publications reduces the number of marker calls. The smaller payload reduces the bytes per call.

| Change | Bytes per event | Number of marker calls |
| --- | --- | --- |
| Reduce the payload only | Lower | Unchanged |
| Notify only on state changes | Independent of payload size | Lower when the same state repeats |

For 100 consecutive DECODE calls followed by IDLE, `trace` emits 200 events and `state` emits DECODE and IDLE, or two events. This count assumes no intermediate state change and excludes earlier initialization or prefill events. Mixed workloads can cause more transitions.

## Current checkouts

The server changes landed in `44c95d5eb` and are present in `llama.cpp-fork` at `21537a585`. [Current compute-profile documentation](compute-profile.md)

The scheduler v2 integration landed in `llama-scheduler` at `ca43b4f`. Its M11R provider pin in `config/versions.env` is `5219055a578fd741e029e81fefef6f3a5695086d`. [Scheduler commit](https://github.com/hsju2021/llama-scheduler/commit/ca43b4f160eeb07f95d3f8f25225c9c1de5c89b6)

## Mode contract and compatibility

The server accepts `--scx-phase-mode off|trace|state`.

| Mode | Behavior | Intended use |
| --- | --- | --- |
| `off` | No SCX marker calls | Performance baseline without phase input |
| `trace` | Existing v1 begin/end events around every decode attempt | Exact call, retry, and compute-interval diagnostics |
| `state` | v2 endpoint called only when phase or active state changes | Lower-frequency scheduling phase input |

- With neither mode nor run ID specified, use `off`.
- An existing command that specifies only `--scx-phase-run-id N` keeps using `trace`.
- Explicit `trace` or `state` requires a nonzero run ID and a trace-enabled build.
- Explicit `off` with a run ID is a configuration error. The parser checks the final combination independently of option order.
- Enabled modes support single-context, decoder-only text generation on Linux with bundled CPU ggml and explicit `-ngl 0`.
- `trace` uses the original 80-byte v1 ABI and decode begin/end endpoints, with synchronization before each marker.

State represents the phase of the most recently submitted batch until another batch changes it or work becomes inactive. That interval includes sampling and server processing between decode calls.

The scheduler state is TGID-wide. Threads in the same server process share the classification. Interpret state intervals and v1 compute intervals according to their respective boundaries.

## Server v2 endpoint

The server exports `llama_scx_phase_set_v2(const server_scx_state_v2 * event)` as a visible, noinline marker in trace-enabled builds. The provider asserts the size and each field offset. [Server marker implementation](../../tools/server/server-scx.h)

The v2 payload is 32 bytes.

| Field | Type | Purpose |
| --- | --- | --- |
| `version` | `uint32_t` | ABI version 2 |
| `phase` | `uint32_t` | UNKNOWN, PREFILL, DECODE, or MIXED |
| `active` | `uint32_t` | 0 or 1 |
| `reserved` | `uint32_t` | Must be zero |
| `run_id` | `uint64_t` | Run identity |
| `sequence` | `uint64_t` | Increases for each emitted notification |

IDLE uses `active=0, phase=UNKNOWN`. Active UNKNOWN uses `active=1`.

Run identity and sequence support validation of stale or duplicate updates. The v1 diagnostics carry call ID, retry number, token counts, requested compute profile, and result.

## Server implementation (complete)

The state publisher belongs to `server_context_impl` and stores the run ID, sequence, and last published `(phase, active)` pair. The execution loop updates it. Phase classification uses the token origins in the actual submitted batch view, including split and retry ranges. [Server execution and lifecycle](../../tools/server/server-context.cpp)

| Trigger | Current behavior |
| --- | --- |
| First actual batch | Publish its active phase, even if no prior event was observed |
| Next batch has the same phase | Skip the marker call |
| Next batch has a different phase | Publish the new active phase before execution |
| Successful decode return | Retain the state |
| Recoverable smaller-batch retry | Reclassify the retry and publish only if the phase changes |
| One slot finishes while others continue | Keep the state active |
| Last processing slot finishes or is cancelled | Publish IDLE |
| Fatal decode error or escaping exception | Clear the state after pending work is settled |
| Sleep, model unload, or normal loop exit | Clear the state before context teardown |

`update_slots()` reconciles state on entry and exit, including early returns. Its exception path settles pending work before clearing state. `terminate()` signals the queue, and the execution loop handles final cleanup.

Sequence continues across model sleep and resume within the same run. Pre/post-decode synchronization runs in `state` mode even when publication is skipped for a duplicate state.

## Worker endpoint cleanup (complete)

The worker cleanup removed the definitions and calls of `ggml_scx_worker_begin_v1` and `ggml_scx_worker_end_v1` from the CPU graph code. The final graph barrier remains in place. The current loader attaches at the server, so the worker cleanup removes ordinary function calls outside its uprobe path. External tracers that used the removed worker symbols lose those hook points. [CPU graph workers](../../ggml/src/ggml-cpu/ggml-cpu.c)

## Build and unprivileged tests (complete)

The current provider passed `test-server-scx` with trace ON and OFF and `test-server-scx-sync` with trace ON. The fixtures cover the v1 and v2 layouts, repeated DECODE followed by IDLE, the five publications in PREFILL/DECODE/DECODE/MIXED/DECODE/IDLE, active UNKNOWN, lifecycle reconciliation, sequence continuity, and synchronization. The CLI tests cover option order and run-ID-only compatibility. [State fixture](../../tests/test-server-scx.cpp) and [argument parser tests](../../tests/test-arg-parser.cpp)

The scheduler at `ca43b4f` built its loader, BPF object, launcher, and workloads using Fedora kernel `7.3.4-200.fc44.x86_64` BTF and UAPI. The BPF ELF contains both v1 handlers and the v2 handler. `make check-unprivileged` passed 57 tests and skipped two checks that depend on external provider sources. The v1 ABI check passed separately against the pinned M11R provider and the current sibling provider. The M10B suite passed seven tests. [Scheduler validation record](https://github.com/hsju2021/llama-scheduler/blob/ca43b4f160eeb07f95d3f8f25225c9c1de5c89b6/docs/STATUS.md#scx-v2-reception)

The 2026-10-03 WSL archive covers a separate candidate. It records four provider build combinations, 14 CTest passes, 400 CPU backend cases, ELF symbol checks, and a scheduler suite with 62 passes and two skips. Its `make check` stopped at the WSL kernel-state check. [Archived candidate validation](scx-state-validation.md) and [source hashes](../../results/scx-state-notification-20261003-local/validated-source-sha256.json)

## Scheduler v2 reception (complete)

The loader accepts `--phase-uprobe-mode trace|state` and defaults to `trace`. The legacy socket and uprobe sources are mutually exclusive.

- `trace` attaches to the two v1 decode endpoints and retains the v1 diagnostic report.
- `state` attaches to `llama_scx_phase_set_v2`. The receiver asserts the 32-byte ABI and every field offset. It uses the bounded `phase_state` map with a distinct source value.
- The receiver checks the version, phase, active and reserved fields, run identity, and increasing sequence. The first applied event pins the run for that registration. A malformed event or map update failure clears active state while retaining the accepted run ID and sequence.
- A pidfd tracks the registered process. Exit triggers probe detachment and state cleanup. The BPF observation path checks the group leader's start time to guard against PID reuse.
- State reports record the mode, applied transitions, diagnostic failures, and the phase at target exit. IDLE is reported as inactive UNKNOWN.

The acceptance runner selects matching server and loader modes and waits for the registration ACK before sending inference requests. The unprivileged fixtures exercise v2 event validation, map failures, stale sequences, process exit, and state report acceptance. [Runner and receiver validation](https://github.com/hsju2021/llama-scheduler/blob/ca43b4f160eeb07f95d3f8f25225c9c1de5c89b6/tests/test_phase_state.py)

## Native-kernel validation (pending)

- Run the existing M11R trace acceptance path and a separate state acceptance path on the intended native host.
- Verify selected-process isolation, the attached mode, applied v2 events, transition counts, zero diagnostic failures, and final inactive state. Zero applied events fail acceptance.
- Run both state acceptance cases. The normal case requires three applied transitions and final sequence 3. The `--state-abort` case requires five applied transitions and sequence 5, with active DECODE retired on target exit. Verify registration and state cleanup, including PID reuse.
- Use a model to exercise split batches, retry phase changes, partial slot completion, final cancellation, decode errors, sleep/resume, and loop exit.
- Record provider revision, loader revision, build options, kernel, and actual marker ELF paths.

Use a current trace-enabled shared-library provider build at the manual kernel-load checkpoint. Kernel loading and privileged commands require explicit approval under `llama-scheduler/AGENTS.md`. [Manual state acceptance commands](https://github.com/hsju2021/llama-scheduler/blob/ca43b4f160eeb07f95d3f8f25225c9c1de5c89b6/docs/STATUS.md#manual-state-acceptance-checkpoint) and [native acceptance criteria](scx-state-validation.md#manual-checkpoint)

Record each completed checkpoint in `llama-scheduler/docs/STATUS.md`. Preserve the historical M11R provider pin and evidence, and record the candidate revisions with the new run.

## Performance comparison (pending)

Run matched trials on the confirmed benchmark host after native acceptance. Use the same model, quantization, thread counts, affinity, workload, scheduler policy, and instrumentation settings. The previously selected target was a Ryzen 5 5600G with 48 GB RAM.

| Configuration | Purpose |
| --- | --- |
| Trace-disabled build | Baseline without phase markers |
| Trace-enabled build, runtime `off` | Cost of including the feature without phase publication |
| `trace` with v1 attachment | Existing observation cost |
| `state` with state attachment | Transition-notification cost |

Use the current observation-only policy for the comparison. Keep the scheduler's task/CPU instrumentation and phase lookups fixed across runs, including runtime `off`. A future phase-aware policy experiment must keep phase input enabled for both baseline and treatment.

Measure uprobe hit counts in dedicated diagnostic runs. Run timing trials with diagnostic tracing and verbose logging disabled. Record token interval p95/p99, throughput, prefill TTFT, and CPU time. Cover sustained decode and prefill injection during active decode. Preserve raw SSE timestamps and grouped events.

Functional acceptance checks that applied event counts match state transitions. Agree on regression thresholds before the performance experiment and evaluate the measured metrics against them.

## Deferred work

- Removing or reducing explicit synchronization.
- Live reattachment, reconnect, and state resynchronization.
- Per-worker state, multi-context aggregation, and additional backends.
- New scheduling policy, priority changes, or prefill admission control.
- Broader reduction of scheduler-side instrumentation overhead.
