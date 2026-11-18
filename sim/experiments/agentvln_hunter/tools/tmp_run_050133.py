
import json
from pathlib import Path
d = json.loads(Path('/mnt/d/rob-memory/outputs/agentvln_reverse_record_20261110_050133/report.json').read_text())
ev = d.get('evaluation') or {}
print('pass', d['pass'], 'checks', json.dumps(d.get('checks')))
print('lateral', round(ev.get('lateral_m',0),3), 'yaw_deg', round(ev.get('yaw_error_rad',0)*57.2958,2),
      'standoff', round(ev.get('front_standoff_m',0),3), 'clear', round(d['whole_episode_audit']['clearance_m'],3))
print('model', json.dumps(d['model_decision'], ensure_ascii=False)[:220])
print('selection_check', json.dumps(d.get('selection_check'), ensure_ascii=False))
print('face', [round(v,4) for v in d['face']['centre']], 'dock', [round(v,4) for v in d['measured_dock']])
print('legs', [(l['phase'], l['status'], round(l['forward_m'],2), round(l['reverse_m'],2)) for l in d['legs']])
print('observation candidates', json.dumps(d['observation']['candidates'], ensure_ascii=False)[:300])
