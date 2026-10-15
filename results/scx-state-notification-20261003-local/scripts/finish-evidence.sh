set -eu
root=/home/hs/scx-state-validation
archive='/mnt/c/Users/HS/.codex/worktrees/182f/Graduation Project/results/scx-state-notification-20261003-local'
export SCX_TOOLS="$root/toolchain/root/usr"
export LD_LIBRARY_PATH="$SCX_TOOLS/lib/x86_64-linux-gnu"
export PATH="$SCX_TOOLS/bin:$PATH"
cp "$root/logs"/scheduler-*.log "$root/logs/scheduler-bpf-symbols.txt" "$root/logs/wsl-kernel-gate.log" "$archive/logs/"
cp "$root/logs/validated-source-sha256.json" "$archive/"
cp /mnt/c/Users/HS/AppData/Local/Temp/scx-state-validation-20261003/*.sh "$archive/scripts/"
{ uname -a; cmake --version; clang-18 --version; cc --version; python3 --version; } > "$archive/environment.txt"
python3 - <<'PY'
import hashlib,json
from pathlib import Path
root=Path('/home/hs/scx-state-validation')
archive=Path('/mnt/c/Users/HS/.codex/worktrees/182f/Graduation Project/results/scx-state-notification-20261003-local')
summary={'date':'2026-10-03','provider_base':'64f4f972a2758d3a730ce78f92aaa05406de40a0','provider_branch':'codex/scx-state-notification','scheduler_base':'ffc03c82738e31977cf402061422b0ef0148fe67','provider_builds':4,'provider_ctest_passed':14,'cpu_backend_cases_passed':400,'scheduler_cases':64,'scheduler_passed':62,'scheduler_skipped':2,'kernel_load_run':False,'model_workload_run':False,'full_make_check':'blocked by missing /sys/kernel/sched_ext/state on WSL','scheduler_binaries':{}}
for name in ('bin/llama_scx_simple','llama_scx_simple.bpf.o'):
    path=root/'scheduler/build'/name
    summary['scheduler_binaries'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
(archive/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
(archive/'README.txt').write_text('Final local evidence for the uncommitted SCX state candidate.\nSee ../../docs/development/scx-state-validation.md for scope and boundaries.\nprovider-on-openmp-clean-build.log supersedes the initial incremental baseline build.\nOther variants were fresh builds, then rebuilt for the final classifier ABI assertion.\nScheduler make-check failure is the WSL native-kernel gate; Python suites ran separately.\nScripts record this Windows/WSL task environment; native commands are in llama-scheduler/docs/LLAMA_PHASE.md.\nNo kernel load or model inference was run.\n')
print(archive)
print('Archived final evidence files:',len(list(archive.rglob('*'))))
PY