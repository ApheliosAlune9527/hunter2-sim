
import json
from pathlib import Path
d = json.loads(Path('/mnt/d/rob-memory/outputs/agentvln_reverse_record_20261110_043800/report.json').read_text())
print('pass', d['pass'], '| error', d.get('error'))
print('checks', json.dumps(d.get('checks'), ensure_ascii=False))
print('evaluation', json.dumps(d.get('evaluation'), ensure_ascii=False))
print('measured_dock', [round(v,4) for v in d['measured_dock']])
print('face', d['face']['centre'], round(d['face']['heading'],4))
print('whole_episode_audit', json.dumps(d['whole_episode_audit'], ensure_ascii=False))
for i, leg in enumerate(d['legs']):
    print(' leg', i, leg['phase'], 'status', leg['status'], 'clearance', round(leg['audit']['clearance_m'],3), 'fwd', round(leg['forward_m'],2), 'rev', round(leg['reverse_m'],2))
