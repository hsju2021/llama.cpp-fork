set -eu
python3 - <<'PY'
import hashlib,json,re
from pathlib import Path
root=Path('/home/hs/scx-state-validation')
provider=Path('/mnt/c/Users/HS/.codex/worktrees/182f/Graduation Project')
scheduler=Path('/mnt/c/Users/HS/Documents/llama-scheduler')
files={
'provider':['common/arg.cpp','common/common.h','ggml/src/ggml-cpu/ggml-cpu.c','tests/CMakeLists.txt','tests/test-arg-parser.cpp','tests/test-server-scx.cpp','tests/test-server-scx-sync.cpp','tools/server/server-context.cpp','tools/server/server-scx.h'],
'scheduler':['include/llama_phase.h','src/llama_scx_simple.c','src/llama_scx_simple.bpf.c','scripts/validate_phase.py','tests/test_phase_state.py','tests/test_m11.py','Makefile']}
result={}
for project, paths in files.items():
    original=provider if project=='provider' else scheduler
    result[project]={}
    for name in paths:
        data=(original/name).read_bytes()
        copied=(root/project/name).read_bytes()
        assert data==copied,(project,name,'snapshot does not match')
        result[project][name]=hashlib.sha256(data).hexdigest()
(root/'logs'/'validated-source-sha256.json').write_text(json.dumps(result,indent=2)+'\n')
print('Validated source snapshots match all changed code/test files.')
for log in sorted((root/'logs').glob('provider-*-tests.log')):
    data=log.read_text()
    assert '100% tests passed, 0 tests failed' in data,log
    print(log.name,re.search(r'100% tests passed, 0 tests failed out of \d+',data).group())
for log in sorted((root/'logs').glob('provider-*-backend.log')):
    data=log.read_text()
    assert '100/100 tests passed' in data,log
    print(log.name,'100/100 passed')
PY