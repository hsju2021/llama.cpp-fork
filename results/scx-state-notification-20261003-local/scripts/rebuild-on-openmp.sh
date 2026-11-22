set -eu
root=/home/hs/scx-state-validation
export SCX_TOOLS="$root/toolchain/root/usr"
export LD_LIBRARY_PATH="$SCX_TOOLS/lib/x86_64-linux-gnu"
export PATH="$SCX_TOOLS/bin:$PATH"
cmake --build "$root/build-on-openmp" --clean-first --target llama-server test-arg-parser test-compute-profile test-backend-ops test-server-scx test-server-scx-sync -j6 > "$root/logs/provider-on-openmp-clean-build.log" 2>&1
ctest --test-dir "$root/build-on-openmp" --output-on-failure -R '^test-(arg-parser|compute-profile|server-scx|server-scx-sync)$' > "$root/logs/provider-on-openmp-tests.log" 2>&1
"$root/build-on-openmp/bin/test-backend-ops" test -b CPU -o ADD,MUL -p 'type=f32' > "$root/logs/provider-on-openmp-backend.log" 2>&1
printf 'Clean ON/OpenMP build, tests, and backend checks PASS\n'