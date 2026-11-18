
import json
from pathlib import Path
R = Path('/mnt/d/rob-memory/outputs/agentvln_hunter_20261109_repro_check')
print('map_readback:', (R/'map_readback.json').read_text().strip())
print('preflight:', (R/'preflight.txt').read_text().strip())
print('map_source:', (R/'map_source.log').read_text().strip())
print('stop:', (R/'stop_receipt.log').read_text().strip())
print('session:', (R/'session.txt').read_text().strip()[:400])
p = R/'replay_new_frame'/'report.json'
print('== replay report exists', p.exists())
if p.exists():
    d = json.loads(p.read_text())
    print('keys', list(d))
    for k in ('mode','pass','decision','fresh_measurement','sent_goal','final_truth','error','parking_distance_m','stop'):
        if k in d: print(' ', k, '=', json.dumps(d[k], ensure_ascii=False)[:260])
