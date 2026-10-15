set -eu
root=/home/hs/scx-state-validation
export SCX_TOOLS="$root/toolchain/root/usr"
export LD_LIBRARY_PATH="$SCX_TOOLS/lib/x86_64-linux-gnu"
export PATH="$SCX_TOOLS/bin:$PATH"
python3 - <<'PY'
import hashlib,json,subprocess
from pathlib import Path
root=Path('/home/hs/scx-state-validation')
checks=[]
server_symbols={'llama_scx_decode_begin_v1','llama_scx_decode_end_v1','llama_scx_phase_set_v2'}
worker_symbols={'ggml_scx_worker_begin_v1','ggml_scx_worker_end_v1'}
for variant in ('on-openmp','off-openmp','on-native','off-native'):
    build=root/f'build-{variant}'
    expected=server_symbols if variant.startswith('on-') else set()
    binaries={}
    for name in ('libllama-server-impl.so','libggml-cpu.so'):
        path=build/'bin'/name
        output=subprocess.check_output(['nm','-D','--defined-only',str(path)],text=True)
        found={line.split()[-1] for line in output.splitlines()}
        assert not found&worker_symbols,(variant,name,'worker symbols retained')
        if name=='libllama-server-impl.so':
            assert found&server_symbols==expected,(variant,found&server_symbols,expected)
        binaries[name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'phase_symbols':sorted(found&server_symbols),'worker_symbols':sorted(found&worker_symbols)}
    (root/'logs'/f'provider-{variant}-cmake-cache.txt').write_bytes((build/'CMakeCache.txt').read_bytes())
    checks.append({'variant':variant,'binaries':binaries,'result':'PASS'})
(root/'logs'/'symbol-validation.json').write_text(json.dumps(checks,indent=2)+'\n')
print('ELF audit: all 4 variants PASS (worker symbols absent; v1/v2 only in trace-enabled builds)')
PY
cd "$root/scheduler"
set +e
build/bin/llama_scx_child -- /bin/true > "$root/logs/wsl-kernel-gate.log" 2>&1
status=$?
set -e
printf 'Selected child refusal exit=%s\n' "$status"
cat "$root/logs/wsl-kernel-gate.log"
readelf --wide --symbols build/llama_scx_simple.bpf.o > "$root/logs/scheduler-bpf-symbols.txt"