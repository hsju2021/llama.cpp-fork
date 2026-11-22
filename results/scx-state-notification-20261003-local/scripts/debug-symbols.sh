set -eu
root=/home/hs/scx-state-validation
rg -n 'ggml_scx_worker' "$root/provider/ggml/src/ggml-cpu/ggml-cpu.c" || true
stat -c '%y %n' "$root/provider/ggml/src/ggml-cpu/ggml-cpu.c" "$root/build-on-openmp/ggml/src/CMakeFiles/ggml-cpu.dir/ggml-cpu/ggml-cpu.c.o" "$root/build-on-openmp/bin/libggml-cpu.so"
for variant in on-openmp off-openmp on-native off-native; do
    printf '%s\n' "$variant"
    nm -D --defined-only "$root/build-$variant/bin/libggml-cpu.so" | rg scx || true
    nm -D --defined-only "$root/build-$variant/bin/libllama-server-impl.so" | rg scx || true
done
sha256sum '/mnt/c/Users/HS/.codex/worktrees/182f/Graduation Project/ggml/src/ggml-cpu/ggml-cpu.c' "$root/provider/ggml/src/ggml-cpu/ggml-cpu.c"