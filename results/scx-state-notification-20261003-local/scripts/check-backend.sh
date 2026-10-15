set -eu
root=/home/hs/scx-state-validation
export SCX_TOOLS="$root/toolchain/root/usr"
export LD_LIBRARY_PATH="$SCX_TOOLS/lib/x86_64-linux-gnu"
export PATH="$SCX_TOOLS/bin:$PATH"
"$root/build-on-openmp/bin/test-backend-ops" test -b CPU -o ADD,MUL -p 'type=f32' > "$root/logs/provider-on-openmp-backend.log" 2>&1
cat "$root/logs/provider-on-openmp-backend.log" | tail -n 8