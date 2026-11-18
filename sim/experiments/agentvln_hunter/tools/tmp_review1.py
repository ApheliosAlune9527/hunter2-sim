
import json
from pathlib import Path
D = Path('/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy')
def show(name, keys=None):
    p = D / name
    if not p.exists():
        print(name, 'MISSING'); return
    d = json.loads(p.read_text())
    print('==', name)
    if isinstance(d, dict):
        for k, v in d.items():
            if keys and k not in keys: continue
            s = json.dumps(v, ensure_ascii=False)
            print('  ', k, '=', s[:220])
    else:
        print('  list len', len(d))
show('runtime.json')
show('image_input_control.json')
show('stop_receipt.log') if (D/'stop_receipt.log').suffix == '.json' else print('== stop_receipt.log\n' + (D/'stop_receipt.log').read_text().strip())
print('== sim_processes.tsv')
print((D/'sim_processes.tsv').read_text().strip()[:600])
