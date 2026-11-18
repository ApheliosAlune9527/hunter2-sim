
import json
from pathlib import Path
d = json.loads(Path('/mnt/d/rob-memory/outputs/agentvln_reverse_record_20261110_060500/report.json').read_text())
print('pass', d['pass'], '| error', d.get('error'))
print('checks', json.dumps(d.get('checks'), ensure_ascii=False))
print('evaluation', {k: (round(v,3) if isinstance(v,float) else v) for k,v in (d.get('evaluation') or {}).items()})
print('face', [round(v,4) for v in d['face']['centre']], 'heading', round(d['face']['heading'],4))
print('face_samples', {k: d['face_samples'][k] for k in ('samples','spread_m')})
print('dock', [round(v,4) for v in d['measured_dock']])
print('standoff nominal', d.get('nominal_standoff_m'), 'plan gap', d.get('planning_gap_m'), 'brake gap', d.get('braking_gap_m'))
print('whole audit', round(d['whole_episode_audit']['clearance_m'],3), d['whole_episode_audit']['obstacle'])
for i, leg in enumerate(d['legs']):
    print(' leg', i, leg['phase'], 'status', leg['status'], 'clear', round(leg['audit']['clearance_m'],3), 'fwd', round(leg['forward_m'],2), 'rev', round(leg['reverse_m'],2))
