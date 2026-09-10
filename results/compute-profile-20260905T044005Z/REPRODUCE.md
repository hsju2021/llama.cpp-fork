# Reproduction

Run from the llama.cpp repository root. No package installation, root access, kernel change, sched_ext operation, or external dataset is required.

## Build

```sh
cmake -S . -B build-server-phase-profile -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_OPENMP=ON -DGGML_CUDA=OFF -DGGML_VULKAN=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=ON -DLLAMA_BUILD_SERVER=ON -DLLAMA_BUILD_EXAMPLES=OFF
cmake --build build-server-phase-profile --target llama-server test-arg-parser test-compute-profile -j6
```

## Unit checks

```sh
ctest --test-dir build-server-phase-profile -R '^test-compute-profile$' --output-on-failure
build-server-phase-profile/bin/test-arg-parser
python3 -m py_compile results/compute-profile-20260905T044005Z/workload.py results/compute-profile-20260905T044005Z/analyze_trace.py tools/server/tests/unit/test_compute_profile.py
```

The complete `test-arg-parser` binary reaches and passes the new server-mode checks, then fails in its pre-existing external URL GET test when network access is blocked. The new pytest test can be run in an existing llama.cpp server-test environment with:

```sh
LLAMA_SERVER_TEST_MODEL="$PWD/benchmark-models/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf" python3 -m pytest tools/server/tests/unit/test_compute_profile.py
```

The experiment host did not have the `pytest` module, so no package was installed and that command was not executed successfully there.

## Functional HTTP run

```sh
python3 results/compute-profile-20260905T044005Z/workload.py functional \
  --server build-server-phase-profile/bin/llama-server \
  --model benchmark-models/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf \
  --output results/compute-profile-20260905T044005Z
python3 results/compute-profile-20260905T044005Z/analyze_trace.py
```

The driver starts six servers: `legacy`, `auto`, and `phase` at `t=2,tb=6`, plus the same modes at `t=6,tb=6`. It uses localhost `/completion`, `n_batch=512`, `n_ubatch=256`, four slots, total context 12288 (3072 per slot), streaming, returned token IDs, temperature 0, request seed 424242, `cache_prompt=false`, `ignore_eos=true`, and no speculative model. Detailed tracing and `--verbose` are enabled only for the functional run.

Scenarios are encoded in `workload.py`:

- S1: one request, 128 prompt tokens and 64 output tokens
- S2: one request, 513 prompt tokens and 8 output tokens
- S3: four concurrent requests, each 128 prompt tokens and 64 output tokens
- S4: request A is 128+128 tokens; after 8 output tokens, request B starts with 2048+8 tokens
- S5: cancel a 128+128 request after 8 streamed tokens, then run 128+8 on the reused slot

## Performance run

```sh
python3 results/compute-profile-20260905T044005Z/workload.py performance \
  --server build-server-phase-profile/bin/llama-server \
  --model benchmark-models/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf \
  --output results/compute-profile-20260905T044005Z
```

This starts one warmed server for each mode at `t=2,tb=6`, disables detailed tracing and verbose logs, and runs S1/S3/S4 five times per mode. The 45 cases are globally shuffled with seed 20260905. Exact server command arrays and execution order are in the JSON artifacts.
