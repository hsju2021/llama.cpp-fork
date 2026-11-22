set -eu
root=/home/hs/scx-state-validation
export SCX_TOOLS="$root/toolchain/root/usr"
export LD_LIBRARY_PATH="$SCX_TOOLS/lib/x86_64-linux-gnu"
export LIBRARY_PATH="$SCX_TOOLS/lib/x86_64-linux-gnu"
export CPATH="$SCX_TOOLS/include"
export PATH="$SCX_TOOLS/bin:$PATH"
cd "$root/scheduler"
set +e
make check VMLINUX_BTF="$root/vmlinux.h" KERNEL_HEADERS="$root/fixture-kernel" > "$root/logs/scheduler-make-check.log" 2>&1
status=$?
set -e
printf 'make check exit=%s\n' "$status"
tail -n 12 "$root/logs/scheduler-make-check.log"
python3 -m py_compile scripts/*.py tests/*.py
bash -n scripts/bootstrap_ubuntu.sh scripts/validate_phase.sh scripts/run_validation.sh