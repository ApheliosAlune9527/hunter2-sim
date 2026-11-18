
import json
from pathlib import Path
R = Path('/mnt/d/rob-memory/outputs/agentvln_hunter_20261109_repro_check')
d = json.loads((R/'virtual_dock'/'report.json').read_text())
print('keys', list(d))
for k in ('mode','pass','decision','fresh_measurement','proposed_goal','sent_goal','final_truth','goal_region_error_m','goal_region_yaw_error_rad','stopped','stop_truth_displacement_m','contact','plan'):
    if k in d:
        v = d[k]
        print(' ', k, '=', json.dumps(v, ensure_ascii=False)[:300])
print('== virtual_dock.log')
print((R/'virtual_dock.log').read_text().strip()[:600])
print('== virtual_observation_seed.log')
print((R/'virtual_observation_seed.log').read_text().strip()[:300])
