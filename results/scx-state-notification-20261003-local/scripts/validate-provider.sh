set -eu
root=/home/hs/scx-state-validation
export SCX_TOOLS="$root/toolchain/root/usr"
export LD_LIBRARY_PATH="$SCX_TOOLS/lib/x86_64-linux-gnu"
export PATH="$SCX_TOOLS/bin:$PATH"
rsync -a --exclude=.git --exclude=results --exclude='build*' '/mnt/c/Users/HS/.codex/worktrees/182f/Graduation Project/' "$root/provider/"
mkdir -p "$root/logs"
cd "$root/provider"
cmake --build ../build-on-openmp --target llama-server test-arg-parser test-compute-profile test-backend-ops test-server-scx test-server-scx-sync -j4 > "$root/logs/provider-on-openmp-build.log" 2>&1
ctest --test-dir ../build-on-openmp --output-on-failure -R '^test-(arg-parser|compute-profile|server-scx|server-scx-sync)$' > "$root/logs/provider-on-openmp-tests.log" 2>&1
cat "$root/logs/provider-on-openmp-tests.log"