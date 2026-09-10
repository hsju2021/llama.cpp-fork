# Explicit compute profiles

`llama_decode_with_options()` lets an application select the compute profile for one decode call. A compute profile selects the configured thread count and threadpool. It does not describe or change the semantic contents of the batch.

This API is useful when an application scheduler already knows whether a decode call belongs to latency-sensitive generation or throughput-oriented batch processing. Existing callers can continue to use `llama_decode()`.

## API usage

Initialize the options with `llama_decode_default_options()`, set the profile, and pass the options to `llama_decode_with_options()`:

```c
struct llama_decode_options options = llama_decode_default_options();
options.compute_profile = LLAMA_COMPUTE_PROFILE_GENERATION;

int32_t result = llama_decode_with_options(ctx, batch, options);
```

Always start with `llama_decode_default_options()` instead of zero-initializing the structure. The default profile is `LLAMA_COMPUTE_PROFILE_AUTO`.

`llama_decode()` is equivalent to calling `llama_decode_with_options()` with the default options:

```c
struct llama_decode_options options = llama_decode_default_options();
int32_t result = llama_decode_with_options(ctx, batch, options);
```

The profiles select resources already configured on the context:

- `n_threads` and `threadpool` for the generation profile.
- `n_threads_batch` and `threadpool_batch` for the batch profile.

Set the thread counts through `llama_context_params` when creating the context or with `llama_set_n_threads()`. Use `llama_attach_threadpool()` to attach explicit threadpools. If `threadpool_batch` is `NULL`, libllama uses `threadpool` for both profiles.

The return values and memory-state behavior are the same as for `llama_decode()`. An invalid `compute_profile` returns `-1` before the batch is decoded.

## Profile meanings

| Profile | Selection for each physical ubatch |
| --- | --- |
| `LLAMA_COMPUTE_PROFILE_AUTO` | Uses the generation resources when the physical ubatch contains one token and the batch resources when it contains more than one token. This preserves the behavior of `llama_decode()`. |
| `LLAMA_COMPUTE_PROFILE_GENERATION` | Always uses `n_threads` and `threadpool`, regardless of the physical ubatch token count. |
| `LLAMA_COMPUTE_PROFILE_BATCH` | Always uses `n_threads_batch` and `threadpool_batch`, regardless of the physical ubatch token count. |

`GENERATION` and `BATCH` name resource profiles. They do not validate that a call is token generation or prompt processing. The caller may use either explicit profile for any valid decode batch.

## Call unit

The option applies to one `llama_decode_with_options()` call. A submitted `llama_batch` is a logical batch. Libllama can split it into one or more physical ubatches before graph execution.

The selected profile applies as follows:

- `AUTO` is resolved independently for each physical ubatch from that ubatch's token count. One call can therefore use both profiles if its physical ubatches have different token counts.
- `GENERATION` applies the generation resources to every physical ubatch produced by the call.
- `BATCH` applies the batch resources to every physical ubatch produced by the call.

The API does not select a profile per sequence or per token within one call. An application that requires different profiles must submit separate decode calls.

## Constraints

- The API controls the decoder path of `llama_decode_with_options()`. It does not add compute-profile options to `llama_encode()` or internal maintenance graphs. If a context has no decoder memory and `llama_decode_with_options()` falls back to the encoder path, the encoder keeps its existing `AUTO` behavior.
- A profile selects the thread count and threadpool used for graph execution. It does not change the logical batch, physical ubatch splitting, graph topology, KV cache behavior, sampling, output selection, or device placement.
- CPU graph execution uses the selected threadpool. Backends that expose a thread-count setter receive the selected thread count. A backend can ignore the setting if it does not support that control.
- The profiles can behave identically when their thread counts and threadpools are the same. They can also have no measurable effect when the active backend does not use these CPU resources.
- The call does not create, resize, or own caller-provided threadpools. The caller must keep attached threadpools valid and must synchronize any context reconfiguration with decode calls.
- The API does not provide request queuing, admission control, fairness, or synchronization for concurrent use of a context.

## Scheduler and libllama responsibilities

There are two schedulers in this discussion:

- The application scheduler is caller code that decides which requests and sequences to place in a decode call.
- The ggml backend scheduler is internal graph-dispatch infrastructure used by libllama.

The application scheduler is responsible for:

- Building each logical batch and deciding when to submit it.
- Choosing `AUTO`, `GENERATION`, or `BATCH` from application-level workload knowledge.
- Managing request admission, priorities, fairness, context assignment, and serialization of calls that share a context.
- Configuring thread counts and threadpools and managing the lifetime of attached threadpools.
- Avoiding oversubscription across contexts or other application work.

Libllama is responsible for:

- Validating the requested profile.
- Splitting the logical batch into physical ubatches according to the context and model constraints.
- Resolving `AUTO` from each physical ubatch token count.
- Applying the selected thread count and threadpool before dispatching each graph through the ggml backend scheduler.
- Preserving the normal decode return values and memory-state behavior.

Libllama does not reinterpret an explicit profile from batch contents, regroup requests to match a profile, or implement application-level scheduling policy.

## Server experiment modes

`llama-server` can connect semantic prompt and generation work to compute profiles with `--server-compute-profile-mode MODE`:

| Mode | Decode call behavior |
| --- | --- |
| `legacy` | Calls `llama_decode()`. This is the default and preserves existing behavior. |
| `auto` | Calls `llama_decode_with_options()` with `LLAMA_COMPUTE_PROFILE_AUTO`. |
| `phase` | Requests `BATCH` for prompt-only work, `GENERATION` for generation-only work, and `AUTO` for mixed or unsupported work. |

The server records token origin when it adds tokens to its shared batch. It classifies each submitted `batch_view`, including split and retry ranges, from those recorded origins. A final prompt token remains prompt work even though its logits produce the first sampled token. Batching generated tokens from multiple slots remains generation work.

Use `--server-compute-profile-trace` to log the run, task and slot IDs, decode call and retry IDs, submitted range, token counts, phase, requested profile, return value, and monotonic timestamps in microseconds. Tracing synchronizes successful decode calls so that the logged completion timestamp covers computation completion; use it only for diagnostics. Add `--verbose` to include libllama physical-ubatch profile selection and CPU planned/actual team-size debug logs.

The initial server connection is limited to the target decoder batch assembled in `server_context`. Internal speculative, multimodal, encoder, and maintenance decode paths retain their existing `AUTO` behavior.

## Optional sched_ext phase markers

On Linux, `-DLLAMA_SCX_PHASE_TRACE=ON` adds experimental observation markers for the sibling llama-scheduler project. The option defaults to OFF and requires the bundled CPU backend without GPU or BLAS backends. Enable a run with `--scx-phase-run-id UINT64` and explicit `-ngl 0`. Only single-context decoder-only text generation is supported; speculative, multimodal, and embedding modes are rejected.

`llama_scx_decode_begin_v1` and `llama_scx_decode_end_v1` expose the existing call/retry identity, token-origin counts, semantic phase, and requested profile. `ggml_scx_worker_begin_v1` and `ggml_scx_worker_end_v1` mark actual CPU graph work in both OpenMP and native threadpool builds. Worker end occurs before the final graph barrier, and decode end synchronizes pending work. Tracing is diagnostic and changes timing.

These are optional uprobe symbols, not additions to the public libllama API. The fork does not depend on libbpf or update BPF maps itself. In shared builds, use the marker-bearing `libllama-server-impl.so` and `libggml-cpu.so` ELF paths. The matching 80-byte v1 wire layout is in `tools/server/server-scx.h`; the sibling repository documents the loader, bounded maps, manual kernel checkpoint, and validation in `docs/LLAMA_PHASE.md`.
