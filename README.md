# llama.cpp-fork: Graduation Project

This personal fork of [llama.cpp](https://github.com/ggml-org/llama.cpp) is used solely for a graduation project on **phase-aware CPU resource management for LLM inference**. Changes in this fork will not be contributed to the original repository.

The research goal is to distinguish prompt processing (Prefill), token generation (Decode), and Mixed work, expose that information to a scheduler, and evaluate how CPU resource choices affect latency, throughput, and interference. This repository provides the inference-side implementation. The companion [llama-scheduler](https://github.com/codinghuman0/llama-scheduler) repository owns the Linux sched_ext/eBPF integration and kernel scheduling experiments.

## What this fork adds

| Component | Implemented behavior |
| --- | --- |
| Per-call compute profiles | `llama_decode_with_options()` selects `AUTO`, `GENERATION`, or `BATCH` using the context's configured thread counts and threadpools. |
| Benchmark controls | `llama-batched-bench` accepts separate `--pp-compute-profile` and `--tg-compute-profile` choices for measured prompt processing and generation. |
| Semantic server routing | The server records token origin, classifies each submitted or retried batch view, and optionally selects a profile from its phase. |
| Diagnostic traces | `--server-compute-profile-trace` records phase, token counts, requested profile, call/retry identity, and timing. |
| Optional Linux phase markers | `LLAMA_SCX_PHASE_TRACE` exposes decode and CPU-worker uprobe markers for the companion scheduler. It defaults to OFF. |
| Reproducible evidence | Focused tests and an archived CPU-only server experiment document behavior and the limits of the measurements. |

The compute-profile API and markers provide resource controls and observability. They do not implement a phase-aware kernel scheduling policy or establish a general performance improvement. The upstream inference engine and tools remain available; this project's research focus is CPU-only decoder inference.

## Phase and resource selection

The application knows where tokens came from. Libllama selects execution resources. The companion scheduler observes phase information and schedules opted-in Linux tasks. These are separate responsibilities.

`GENERATION` selects `n_threads` and the normal threadpool. `BATCH` selects `n_threads_batch` and the batch threadpool, falling back to the normal pool if no batch pool is attached. `AUTO` retains the existing selection: generation resources for a one-token physical ubatch and batch resources for larger physical ubatches. These profile names do not detect the semantic phase.

The server exposes three experiment modes:

| `--server-compute-profile-mode` | Behavior |
| --- | --- |
| `legacy` (default) | Use the existing `llama_decode()` path. |
| `auto` | Use `llama_decode_with_options()` with `AUTO`. |
| `phase` | Use `BATCH` for Prefill, `GENERATION` for Decode, and `AUTO` for Mixed or Unknown work. |

A final prompt fragment with one token is still Prefill. Generated tokens from several requests can form a multi-token Decode batch. Continuous batching can combine both into Mixed work. An explicit profile applies to every physical ubatch produced by one decode call; it does not independently allocate resources to different tokens in a Mixed batch.

See [the compute-profile documentation](docs/development/compute-profile.md) for the API, fallback behavior, threadpool lifetime requirements, and supported server paths.

## Build the research fork

Build from this checkout to use the fork-specific APIs and flags. Upstream release binaries do not provide this project's extensions. A C/C++ toolchain, CMake, and a compatible local GGUF model are needed for inference; model weights are not included.

The following commands use a fresh CPU build directory with phase markers disabled. Run them from the repository root. The [build guide](docs/build.md) covers toolchain setup and other platforms.

### Linux

```sh
cmake -S . -B build-graduation -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=OFF -DGGML_BLAS=OFF -DLLAMA_SCX_PHASE_TRACE=OFF -DLLAMA_BUILD_TESTS=ON
cmake --build build-graduation --config Release --parallel --target llama-server llama-batched-bench test-compute-profile test-arg-parser
ctest --test-dir build-graduation -C Release -R '^test-compute-profile$' --output-on-failure
```

### Windows / MSVC

From a Visual Studio developer PowerShell with Visual Studio 2022 C++ build tools installed:

```powershell
cmake -S . -B build-graduation-msvc -G "Visual Studio 17 2022" -A x64 -DGGML_CUDA=OFF -DGGML_BLAS=OFF -DLLAMA_SCX_PHASE_TRACE=OFF -DLLAMA_BUILD_TESTS=ON
cmake --build build-graduation-msvc --config Release --parallel --target llama-server llama-batched-bench test-compute-profile test-arg-parser
ctest --test-dir build-graduation-msvc -C Release -R '^test-compute-profile$' --output-on-failure
```

For the Linux command examples below, Windows users can substitute `./build-graduation-msvc/bin/Release/<tool>.exe` for `./build-graduation/bin/<tool>`. Keep Windows and Linux build directories separate.

## Run a CPU experiment

Replace `model.gguf` with your local model path. The example thread counts (`-t 2`, `-tb 6`) are experimental inputs, not an optimal allocation recommendation.

Compare explicit prompt/generation profiles:

```sh
./build-graduation/bin/llama-batched-bench -m model.gguf -ngl 0 -t 2 -tb 6 -c 2048 -b 512 -ub 256 -npp 128 -ntg 64 -npl 1,4 --pp-compute-profile batch --tg-compute-profile generation --output-format jsonl
```

Repeat with both profile flags set to `auto` for a baseline. See [batched-bench usage](tools/batched-bench/README.md) for workload dimensions and output fields.

Start the server with semantic routing:

```sh
./build-graduation/bin/llama-server -m model.gguf -ngl 0 -t 2 -tb 6 -c 2048 -b 512 -ub 256 --parallel 4 --host 127.0.0.1 --port 8080 --server-compute-profile-mode phase
```

Use the same model and workload with `legacy`, `auto`, and `phase` to compare behavior. See [server usage](tools/server/README.md) for HTTP requests. Add `--server-compute-profile-trace` for phase diagnostics and `--verbose` for physical-ubatch and CPU team-size details. Diagnostic tracing synchronizes work and changes timing; collect performance results separately with tracing disabled.

## Connect to llama-scheduler

The optional bridge requires Linux with the bundled CPU backend and GPU/BLAS backends disabled. Its supported workload is a single-context, decoder-only text-generation server with explicit `-ngl 0`; speculative decoding, multimodal input, embeddings, and router mode are outside this scope.

Build markers in a separate Linux directory:

```sh
cmake -S . -B build-graduation-scx -DCMAKE_BUILD_TYPE=RelWithDebInfo -DBUILD_SHARED_LIBS=ON -DGGML_CUDA=OFF -DGGML_BLAS=OFF -DLLAMA_SCX_PHASE_TRACE=ON
cmake --build build-graduation-scx --parallel --target llama-server
```

Pass a unique nonzero `--scx-phase-run-id UINT64` and `-ngl 0` when launching that server. Building or enabling markers does not load a scheduler or move a process into SCHED_EXT.

The provider exports `llama_scx_decode_begin_v1` / `llama_scx_decode_end_v1` and `ggml_scx_worker_begin_v1` / `ggml_scx_worker_end_v1`. In shared builds, the marker-bearing objects are `libllama-server-impl.so` and `libggml-cpu.so`, rather than only the launcher executable. The [server marker header](tools/server/server-scx.h) defines the 80-byte v1 event layout.

Follow the companion repository's setup and validation workflow and its `docs/LLAMA_PHASE.md` for the matching provider revision, loader, kernel requirements, and evidence. Keep privileged loader operations separate from the unprivileged inference process. Userspace marker observations and BPF compilation do not establish native scheduler attachment or execution.

## Tests and recorded results

- [Compute-profile test](tests/test-compute-profile.cpp): default options, profile resolution, and invalid-profile rejection.
- [Argument-parser tests](tests/test-arg-parser.cpp): profile options and server/marker flag handling. Run `ctest --test-dir build-graduation -C Release -R '^test-arg-parser$' --output-on-failure` after building the target; the wider parser suite includes external network checks.
- [Server profile tests](tools/server/tests/unit/test_compute_profile.py): completion and streaming coverage. Follow the [server test setup](tools/server/tests/README.md), select this test file, and use `LLAMA_SERVER_BIN_PATH` and `LLAMA_SERVER_TEST_MODEL` to point to the intended binary and local model.
- [2026-09-05 experiment archive](results/compute-profile-20260905T044005Z/README.md): [report](results/compute-profile-20260905T044005Z/REPORT.md), [reproduction commands](results/compute-profile-20260905T044005Z/REPRODUCE.md), environment details, raw results, and trace analysis.

The archive validates the scoped semantic-to-resource connection and records workload-dependent performance, including regressions. Its results belong to the recorded revision, model, and host; they are not fresh validation of the current checkout or proof of a universally better policy. Keep existing result directories immutable and save new runs under new identifiers.

For comparisons, record the source revision and dirty state, build options, model identity, CPU/kernel, thread counts, affinity, workload, seeds, and repetitions. Report time to first token, generation latency distributions, throughput, and interference as appropriate. Separate correctness checks, diagnostic runs, and performance measurements.

## Development and reference

[AGENTS.md](AGENTS.md) defines the graduation-project workflow, AI-assisted development, repository boundaries, and validation expectations. Local research does not require an upstream issue or PR. The inherited [CONTRIBUTING.md](CONTRIBUTING.md) remains upstream reference material.

Useful implementation entry points are [the public API](include/llama.h), [decode execution](src/llama-context.cpp), [server phase routing](tools/server/server-context.cpp), and [CPU workers](ggml/src/ggml-cpu/ggml-cpu.c). General documentation remains available for [building](docs/build.md), [models](docs/models.md), [the CLI](tools/cli/README.md), and [server development](tools/server/README-dev.md).

## License and acknowledgements

This fork retains the upstream [MIT license](LICENSE) and copyright notices. The underlying inference engine is [llama.cpp](https://github.com/ggml-org/llama.cpp), built on [ggml](https://github.com/ggml-org/ggml), by the ggml authors and contributors.

Upstream dependencies include:

- [yhirose/cpp-httplib](https://github.com/yhirose/cpp-httplib) - HTTP server, MIT license.
- [stb-image](https://github.com/nothings/stb) - Image decoder, public domain.
- [nlohmann/json](https://github.com/nlohmann/json) - JSON library, MIT license.
- [miniaudio.h](https://github.com/mackron/miniaudio) - Audio decoder, public domain.
- [subprocess.h](https://github.com/sheredom/subprocess.h) - Process launching, public domain.
