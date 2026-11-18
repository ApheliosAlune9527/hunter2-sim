
import json
from pathlib import Path
D = Path('/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy')
d = json.loads((D/'vlm_r1_from_spawn/report.json').read_text())
for k in ('mode','pass','decision','fresh_measurement','proposed_goal','start_truth','sent_goal'):
    print('==', k)
    print(json.dumps(d.get(k), ensure_ascii=False)[:700])
print('== nav', json.dumps(d.get('nav'), ensure_ascii=False)[:300])
print('== stop', json.dumps(d.get('stop'), ensure_ascii=False)[:300])
