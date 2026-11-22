set -eu
root=/home/hs/scx-state-validation
export SCX_TOOLS="$root/toolchain/root/usr"
export LD_LIBRARY_PATH="$SCX_TOOLS/lib/x86_64-linux-gnu"
export PATH="$SCX_TOOLS/bin:$PATH"
cp '/mnt/c/Users/HS/.codex/worktrees/182f/Graduation Project/tools/server/server-context.cpp' "$root/provider/tools/server/server-context.cpp"
check_variant() {
    name="$1"
    cmake --build "$root/build-$name" --target llama-server -j2 > "$root/logs/provider-$name-final-build.log" 2>&1
    ctest --test-dir "$root/build-$name" --output-on-failure -R '^test-(arg-parser|compute-profile|server-scx|server-scx-sync)$' > "$root/logs/provider-$name-tests.log" 2>&1
    if [ "$name" != on-openmp ]; then
        "$root/build-$name/bin/test-backend-ops" test -b CPU -o ADD,MUL -p 'type=f32' > "$root/logs/provider-$name-backend.log" 2>&1
    fi
    printf 'FINAL PASS %s\n' "$name"
}
check_variant on-openmp & p1=$!
check_variant off-openmp & p2=$!
check_variant on-native & p3=$!
check_variant off-native & p4=$!
status=0
wait "$p1" || status=1
wait "$p2" || status=1
wait "$p3" || status=1
wait "$p4" || status=1
exit "$status"