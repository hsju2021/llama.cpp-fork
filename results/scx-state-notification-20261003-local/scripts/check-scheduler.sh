set -eu
root=/home/hs/scx-state-validation
export SCX_TOOLS="$root/toolchain/root/usr"
export LD_LIBRARY_PATH="$SCX_TOOLS/lib/x86_64-linux-gnu"
export PATH="$SCX_TOOLS/bin:$PATH"
export CPATH="$SCX_TOOLS/include"
export LIBRARY_PATH="$SCX_TOOLS/lib/x86_64-linux-gnu"
cd "$root/scheduler"
python3 - <<'PY'
from pathlib import Path
for folder in ('scripts', 'tests'):
    for path in Path(folder).glob('*.sh'):
        path.write_bytes(path.read_bytes().replace(b'\r\n',b'\n'))
PY
python3 tests/test_instrumentation.py > "$root/logs/scheduler-instrumentation.log" 2>&1
python3 tests/test_m11.py > "$root/logs/scheduler-m11.log" 2>&1
python3 tests/test_m11r.py > "$root/logs/scheduler-m11r.log" 2>&1
python3 tests/test_phase_state.py > "$root/logs/scheduler-state.log" 2>&1
python3 tests/test_m10b.py > "$root/logs/scheduler-m10b.log" 2>&1
python3 tests/test_validation.py build/bin/llama_scx_child build/bin/cpu_burn build/bin/sleep_wake > "$root/logs/scheduler-validation.log" 2>&1
printf 'Scheduler Python suites PASS\n'