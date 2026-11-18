
import json
from pathlib import Path
d = json.loads(Path('/mnt/d/rob-memory/outputs/agentvln_reverse_record_20261110_055500/report.json').read_text())
print('face', [round(v,4) for v in d['face']['centre']], 'heading', round(d['face']['heading'],4))
print('face_samples', json.dumps(d.get('face_samples'), ensure_ascii=False)[:300])
print('dock', [round(v,4) for v in d['measured_dock']])
print('evaluation', {k: (round(v,3) if isinstance(v,float) else v) for k,v in (d.get('evaluation') or {}).items()})
print('checks', d.get('checks'))
print('standoff nominal', d.get('nominal_standoff_m'))
