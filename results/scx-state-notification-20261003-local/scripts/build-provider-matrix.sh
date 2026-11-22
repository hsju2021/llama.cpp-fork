set -eu
root=/home/hs/scx-state-validation
export SCX_TOOLS="$root/toolchain/root/usr"
export LD_LIBRARY_PATH="$SCX_TOOLS/lib/x86_64-linux-gnu"
export PATH="$SCX_TOOLS/bin:$PATH"
mkdir -p "$root/logs"
run_variant() {
    name="$1"; trace="$2"; omp="$3"
    cmake -S "$root/provider" -B "$root/build-$name" -G Ninja -DCMAKE_BUILD_TYPE=Release -DLLAMA_SCX_PHASE_TRACE="$trace" -DGGML_OPENMP="$omp" -DGGML_NATIVE=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_TESTS=ON -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_TOOLS=ON -DLLAMA_BUILD_SERVER=ON -DLLAMA_BUILD_UI=OFF -DLLAMA_BUILD_APP=OFF > "$root/logs/provider-$name-configure.log" 2>&1
    targets='llama-server test-arg-parser test-compute-profile test-backend-ops test-server-scx'
    if [ "$trace" = ON ]; then targets="$targets test-server-scx-sync"; fi
    cmake --build "$root/build-$name" --target $targets -j3 > "$root/logs/provider-$name-build.log" 2>&1
    ctest --test-dir "$root/build-$name" --output-on-failure -R '^test-(arg-parser|compute-profile|server-scx|server-scx-sync)$' > "$root/logs/provider-$name-tests.log" 2>&1
    printf 'PASS %s\n' "$name"
}
run_variant off-openmp OFF ON & p1=$!
run_variant on-native ON OFF & p2=$!
run_variant off-native OFF OFF & p3=$!
status=0
wait "$p1" || status=1
wait "$p2" || status=1
wait "$p3" || status=1
exit "$status"