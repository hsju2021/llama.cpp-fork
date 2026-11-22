# Environment

## Source

- Repository: llama.cpp working tree
- Branch: `feature/explicit-compute-profile`
- HEAD: `4c1742f34be270f95ff24a1fdaf47773b5e8661a`
- No commit, push, PR, issue, or external comment was created.
- The sibling `llama-scheduler` working tree was not modified.
- The checkout had pre-existing whole-tree line-ending differences. Only the experiment target files were edited; unrelated changes were preserved.

## Host

- OS: Ubuntu 26.04.1 LTS
- Kernel: Linux 7.0.0-22-generic x86_64
- Execution context: native Linux host kernel inside the Codex restricted container/PID namespace (`systemd-detect-virt: container-other`); this is not claimed as an isolated bare-metal benchmark
- CPU: AMD Ryzen 5 5600G, 1 socket, 6 cores, 2 threads/core, 12 logical CPUs
- Allowed CPUs: `0-11`; allowed NUMA nodes: `0`
- NUMA: 1 node, CPUs `0-11`
- RAM: 45 GiB; swap: 8 GiB
- CPU frequency driver: `amd-pstate-epp`; governor observed as `performance`
- sched_ext state observed as `disabled`; no scheduler or system setting was changed
- No other `llama-server` process remained after the runs. During performance measurement, one server per mode stayed loaded; only the selected target server's `/proc/PID/stat` CPU time delta was measured.

## Toolchain and build

- GCC/G++: Ubuntu 15.2.0
- CMake: 4.2.3
- Build type: Release
- CPU backend: enabled with `GGML_NATIVE=ON`
- OpenMP: enabled, linked to `libgomp.so.1`
- BLAS: disabled
- CUDA, HIP, SYCL, and Vulkan: disabled
- curl: disabled
- server and tests: enabled
- examples: disabled
- Embedded server UI: unavailable because the disconnected build could not download UI assets; all runs used `--no-ui`

Configuration command:

```sh
cmake -S . -B build-server-phase-profile -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_OPENMP=ON -DGGML_CUDA=OFF -DGGML_VULKAN=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=ON -DLLAMA_BUILD_SERVER=ON -DLLAMA_BUILD_EXAMPLES=OFF
```

## Model

- File: `benchmark-models/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf`
- Size: 1,117,320,800 bytes
- SHA-256: `1741e5b2d062b07acf048bf0d2c514dadf2a48f94e2b4aa0cfe069af3838ee2f`
- Tokenizer probe text: ` fixed benchmark token sequence`
- Without special tokens: `[8356, 28431, 3950, 8500]`
- With special tokens: `[151646, 8356, 28431, 3950, 8500]`
- Special prefix/BOS: `[151646]`
- Exact numeric 128, 513, and 2048 token prompts were constructed by retaining the prefix and repeating the four-token body.
