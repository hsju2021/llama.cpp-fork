# SCX state notification validation

Candidate date: 2026-10-03. Provider: personal `hsju2021/llama.cpp-fork`, branch `codex/scx-state-notification`, based on `64f4f972a2758d3a730ce78f92aaa05406de40a0`. Scheduler: the paired `llama-scheduler` checkout based on `ffc03c8`. Changes are uncommitted. The M11/M11R provider pin and archived results remain unchanged.

## Implemented scope

- Server modes `off|trace|state`, order-independent option validation, and run-ID-only trace compatibility.
- Unchanged 80-byte v1 server ABI plus the separate 32-byte v2 state ABI, with size and all field offsets asserted on both sides.
- Transition suppression, actual submitted-view classification, retained synchronization, and execution-loop cleanup for idle, cancellation, errors, sleep, and exit.
- Worker endpoint removal with the final graph barrier preserved.
- Matching scheduler attachment modes, bounded TGID state, run/sequence validation, failure invalidation, process-instance cleanup, and mode-aware reports.
- A separate candidate acceptance path, including graceful completion and termination during active DECODE, without changing the historical trace provider pin.

Scheduling policy and compute-profile routing are unchanged. The state interval includes sampling and server processing; it is not a v1 compute interval. No performance improvement is claimed.

## Local evidence

Validation runs in an isolated Linux-filesystem source copy under `/home/hs/scx-state-validation`, using WSL Ubuntu 24.04 with kernel `6.6.87.2-microsoft-standard-WSL2`. Build tools were extracted into that task directory without system installation or elevated commands. Raw logs, build options, symbol checks, source hashes, and reproduction scripts are retained in `results/scx-state-notification-20261003-local/` in the provider worktree.

| Check | Result |
| --- | --- |
| Trace ON, OpenMP ON server build | PASS, clean rebuild |
| Trace OFF, OpenMP ON server build | PASS |
| Trace ON, native threadpool server build | PASS |
| Trace OFF, native threadpool server build | PASS |
| Provider CTest: argument parser, compute profile, state publisher, enabled-build synchronization fixture | 14/14 passed across the four builds |
| Small CPU ADD/MUL f32 backend checks | 100/100 per build, 400/400 total |
| ELF symbols in all four builds | PASS: worker symbols absent; v1/v2 server markers present only with trace enabled |
| Scheduler userspace and BPF compilation with `-Werror` | PASS, compile evidence only |
| Scheduler Python suites: instrumentation, M11, M11R, state, M10B, validation | 64 cases: 62 passed, 2 skipped |
| Full scheduler `make check` | Environment gate: selected-child shell test stops because `/sys/kernel/sched_ext/state` is absent |
| Python/shell syntax and both repository whitespace checks | PASS |

The two skipped cases require separate historical provider checkouts: the legacy socket producer and the fixed M11 semantic source. Current provider ABI and publisher checks run independently in the C++ fixtures. The shell gate expects a native sched_ext state file; the WSL launcher reports that the file is missing. It was not bypassed or treated as native success.

The final ELF audit detected an old worker symbol in the initially reused ON/OpenMP build. Preserved source timestamps had allowed an object from the baseline to remain. That variant was rebuilt with `--clean-first`; its tests and symbols were checked again. The other three variants were fresh builds. Final source SHA-256 checks match every changed code/test file to the validated Linux copy.

The BPF compilation uses the external sched-ext x86 `vmlinux-v6.18-rc4-g6146a0f1dfae.h` fixture from scx commit `e37ab1fd7ec09505c33beaefdc128bab2d582660`, and a Linux v6.17 scheduler UAPI fixture. These are recorded compile inputs, not the target kernel's BTF or proof of verifier compatibility.

Executable fixtures exercise production publication, phase reduction, lifecycle guards, synchronization, BPF handlers, map/read failures, run and sequence rejection, active UNKNOWN, real-child pidfd cleanup, exit/update races, and report acceptance. They verify two notifications for 100 repeated DECODE calls followed by IDLE, and five notifications for PREFILL/DECODE/DECODE/MIXED/DECODE/IDLE. Actual server token extraction, slot completion/cancellation, model unload, and loop integration were source-reviewed; model-backed lifecycle runs remain pending.

Registration cleanup also exercises 127 successive process identities, same-PID reuse, and deletion failures. The last inactive state is retained for reporting, then reclaimed when the next registration starts, so completed processes do not fill the bounded map.

## Manual checkpoint

The paired scheduler's `docs/LLAMA_PHASE.md` contains the exact native build and runtime commands. Its `AGENTS.md` requires explicit approval before `sudo` or sched_ext loading. No kernel load, uprobe attachment, SCHED_EXT workload, model inference, or performance trial was executed locally.

On the intended native host, verify the selected Ryzen 5 5600G / 48 GB machine, target BTF/UAPI, actual ELF paths, and build options. Run the old trace acceptance and the new state acceptance separately. The controlled state path requires exactly three applied transitions and sequence 3 for normal completion. The abnormal path adds PREFILL and DECODE from a second request, then requires sequence 5 plus evidence that termination invalidated active DECODE. Zero delivery, per-call DECODE publication, sequence gaps, and diagnostic failures fail acceptance.

Then agree on regression thresholds and run matched trace-disabled, runtime-off, trace, and state timing trials with fixed policy and instrumentation. Keep hit-count diagnostics separate from timed runs and preserve raw SSE grouped events. Live reattachment, resynchronization after loader restart, synchronization removal, and policy changes remain deferred.
