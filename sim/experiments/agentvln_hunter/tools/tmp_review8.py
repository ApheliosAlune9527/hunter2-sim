
import json
from pathlib import Path
D = Path('/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy')
v = json.loads((D/'validation_summary.json').read_text())
for name, r in v['runs'].items():
    print('%-24s sent_goal=%s' % (name, r.get('sent_goal')))
# dig into one VLM run report
for cand in ('vlm_r1_from_spawn/report.json', 'vlm_seeded_observation/report.json'):
    p = D/cand
    if p.exists():
        d = json.loads(p.read_text())
        print('==', cand, 'keys', list(d)[:14])
        print('   ', json.dumps({k: d.get(k) for k in ('sent_goal','dock','target','vlm','selection') if k in d}, ensure_ascii=False)[:600])
