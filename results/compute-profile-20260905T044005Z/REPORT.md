# Server semantic phase to CPU resource validation

## Conclusion

PASS for the scoped decoder-only text-completion path. The server records token origin when each token enters the shared batch, classifies the exact submitted view, maps PREFILL to BATCH, DECODE to GENERATION, and MIXED/UNKNOWN to AUTO, and the CPU backend executes with the selected OpenMP team size.

This validates the semantic-to-resource connection. It does not validate a fixed worker set, worker-TID handoff, sched_ext integration, or an optimal `t=2,tb=6` policy.

## Implementation

- Related upstream work was checked before implementation: [issue 21266](https://github.com/ggml-org/llama.cpp/issues/21266) and [PR 25675](https://github.com/ggml-org/llama.cpp/pull/25675) cover disaggregated prefill/decode, while [issue 26022](https://github.com/ggml-org/llama.cpp/issues/26022) discusses mixed server workloads. None is an exact duplicate of this CPU compute-profile wiring experiment.
- `common/common.h`, `common/arg.cpp`: add server modes `legacy` (default), `auto`, and `phase`, plus optional diagnostic tracing.
- `tools/server/server-context.cpp`: store task, slot, and PREFILL/DECODE origin per batch token; classify the exact split/retry range; route decode calls; log monotonic microsecond timestamps and return/completion time when tracing.
- `ggml/src/ggml-cpu/ggml-cpu.c`: optional debug evidence for planned threads, actual OpenMP team size, pool capacity, and disposable-pool status.
- `docs/development/compute-profile.md`: document modes, fallbacks, trace synchronization cost, and current scope.
- `tests/test-arg-parser.cpp`: cover defaults, all valid modes, tracing, and invalid input.
- `tools/server/tests/utils.py`, `tools/server/tests/unit/test_compute_profile.py`: add server-test configuration and completion/streaming coverage.
- `workload.py`, `analyze_trace.py`: dependency-free real HTTP scenarios, performance collection, and trace reconciliation.

With no option, the server still calls `llama_decode()`. Phase classification is skipped in untraced `legacy`/`auto` mode, and task/slot ID sets are only constructed for tracing.

## Functional verdicts

| Check | Status | Evidence |
| --- | --- | --- |
| A/B S1 output token IDs and stop reason, `t=2,tb=6` | PASS | IDs equal; both stop as `limit` |
| A/B S1 output token IDs and stop reason, `t=6,tb=6` | PASS | IDs equal; both stop as `limit` |
| S1 semantic PREFILL then DECODE | PASS | traced calls show origin-based transition |
| S2 final one-token PREFILL remains BATCH in phase mode | PASS | call 66 below |
| S3 four requests share one DECODE call | PASS | call 75 below |
| S3 AUTO/BATCH versus phase/GENERATION distinction | PASS | actual 6 versus 2 worker team below |
| S4 real mixed batch and AUTO fallback | PASS | call 147 below |
| S5 cancel, reset, slot reuse, no stale origin | PASS | task 273 released/reset; slot 0 starts task 285 with 128 PREFILL and no unknown tokens |
| Exact token accounting | PASS | all calls satisfy prefill + decode + unknown = submitted tokens |
| Profile mapping | PASS | zero mapping errors in all six functional logs |
| Physical ubatch resource mapping | PASS | zero planned/actual team-size mismatches |
| Retry behavior | NOT OBSERVED | zero retries occurred; code classifies each retry's submitted `[off, off+n_tokens)` view |
| Return behavior | PASS | all 1,041 traced decode calls returned 0 |
| `test-compute-profile` | PASS | CTest passed |
| New argument-parser cases | PASS | reached before the unrelated network failure |
| Complete `test-arg-parser` binary | BLOCKED | pre-existing external URL GET test cannot access the network |
| New pytest file | UNVERIFIED BY PYTEST | module absent; equivalent real HTTP completion/streaming paths passed without installing packages |

For each `t=2,tb=6` mode, 283 calls were observed:

| Phase | Calls | Ratio |
| --- | ---: | ---: |
| PREFILL | 7 | 2.4735% |
| DECODE | 271 | 95.7597% |
| MIXED | 5 | 1.7668% |
| UNKNOWN | 0 | 0.0000% |

The `t=6,tb=6` S1 regression run produced 64 calls per mode: one PREFILL and 63 DECODE calls. This is expected because the first output token is sampled from prompt computation.

## Representative end-to-end evidence

All times in the server trace use the monotonic `ggml_time_us()` clock and are microseconds. Diagnostic tracing calls `llama_synchronize()` after a successful decode, so `complete_elapsed_us` covers computation completion and tracing is not used for performance results.

| Scenario | Semantic call | Requested -> resolved | Physical ubatch | Selected/planned/actual team |
| --- | --- | --- | --- | --- |
| S2 final prompt fragment | call 66: 1 PREFILL, task 65, slot 3 | BATCH -> BATCH | 1 token | 6 / 6 / 6 |
| S3 phase mode | call 75: 4 DECODE, tasks 75-78, slots 0-3 | GENERATION -> GENERATION | 4 tokens | 2 / 2 / 2 |
| S3 auto mode | call 75: 4 DECODE, tasks 75-78, slots 0-3 | AUTO -> BATCH | 4 tokens | 6 / 6 / 6 |
| S4 mixed | call 147: 511 PREFILL + 1 DECODE, tasks 143 and 153 | AUTO -> BATCH | 2, 256, 254 tokens | 6 / 6 / 6 for each |

The CPU logs report `disposable_threadpool=yes`. The names `normal` and `batch` identify resource profiles; no attached independent fixed worker pools exist in this configuration. Therefore, the evidence establishes actual OpenMP team sizes, not stable worker identities.

## Performance

Final run: CPU-only, `t=2,tb=6`, detailed tracing off, five repetitions for each mode/scenario, globally shuffled with seed 20260905. There are 45 complete records, 6,735 valid single-token intervals, no grouped SSE token events, failures, or cancellations. TTFT, completion, and interval are medians; throughput and process CPU time are means.

| Mode | Scenario | TTFT ms | Completion ms | Token interval ms | Throughput tok/s | CPU s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| legacy | S1 | 709.137 | 3087.173 | 37.881 | 20.568 | 9.042 |
| auto | S1 | 696.485 | 3094.109 | 37.410 | 20.886 | 8.886 |
| phase | S1 | 710.364 | 3126.875 | 37.838 | 20.760 | 8.938 |
| legacy | S3 | 2753.523 | 5423.360 | 42.076 | 47.156 | 32.588 |
| auto | S3 | 2866.052 | 5605.056 | 43.431 | 45.384 | 33.762 |
| phase | S3 | 2822.997 | 8659.383 | 92.305 | 29.636 | 28.420 |
| legacy | S4 | 6735.367 | 15824.073 | 38.258 | 7.403 | 92.650 |
| auto | S4 | 6913.938 | 16243.099 | 38.543 | 7.241 | 94.878 |
| phase | S4 | 6712.888 | 16078.747 | 38.438 | 7.238 | 93.016 |

S1 and S4 are broadly similar at this sample size. S3 exposes the resource tradeoff: relative to AUTO, phase mode used 15.8% less target-process CPU time but completion time rose 54.5%, throughput fell 34.7%, and median token interval rose 112.5%. This is consistent with forcing a four-token multi-request DECODE batch from six threads to two. It demonstrates correct routing, not an optimal allocation. No P99 or general performance claim is made.

## Scope and remaining work

- The integrated path is the ordinary decoder-only target batch in `server_context`, with speculative decoding disabled.
- Internal speculative, multimodal, encoder, and maintenance decode paths retain AUTO and are not validated here.
- No change was made to server batch ordering, prompt budget, KV policy, admission policy, or same-context decode serialization.
- A future fixed-worker/sched_ext stage must create or attach stable worker pools, expose the participating worker TIDs, define a safe handoff to `llama-scheduler`, and validate CPU affinity/scheduling without inferring identity from `normal`/`batch` labels.
- The `t=2,tb=6` values are deliberately diagnostic. The scheduler project must select and validate a policy separately.
