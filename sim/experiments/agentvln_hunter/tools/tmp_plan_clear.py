
import json
from pathlib import Path
d = json.loads(Path('/mnt/d/rob-memory/outputs/agentvln_reverse_record_20261110_043800/report.json').read_text())
fc = d.get('forward_control') or {}
plan = fc.get('plan')
print('forward_control', {k: fc.get(k) for k in ('safe',)})
print('plan clearance', None if not plan else round(plan['audit']['clearance_m'], 3))
print('leg2 audit', round(d['legs'][2]['audit']['clearance_m'],3), 'leg4', round(d['legs'][4]['audit']['clearance_m'],3))
print('evaluation lateral', round(d['evaluation']['lateral_m'],3))
