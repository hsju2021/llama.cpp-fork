set -eu
curl -fLsS 'https://api.github.com/repos/sched-ext/scx/commits?path=scheds/vmlinux/arch/x86&until=2025-11-01T00:00:00Z&per_page=10' -o /home/hs/scx-state-validation/header-commits.json
python3 - <<'PY'
import json, urllib.request
from pathlib import Path
out=Path('/home/hs/scx-state-validation')
commits=json.loads((out/'header-commits.json').read_text())
for entry in commits:
    commit=entry['sha']
    items=json.load(urllib.request.urlopen(f'https://api.github.com/repos/sched-ext/scx/contents/scheds/vmlinux/arch/x86?ref={commit}'))
    for item in items:
        if item['name'].startswith('vmlinux-v6.17'):
            urllib.request.urlretrieve(item['download_url'],out/'vmlinux.h')
            (out/'vmlinux-source.txt').write_text(item['download_url']+'\n')
            print(item['download_url'])
            raise SystemExit(0)
raise SystemExit('No 6.17 fixture located')
PY