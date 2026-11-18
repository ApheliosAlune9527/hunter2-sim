
import json
from pathlib import Path
D = Path('/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy')
print('== image_input_control')
for e in json.loads((D/'image_input_control.json').read_text()):
    print('  ', json.dumps(e, ensure_ascii=False)[:300])
print('== paired_2x2_natural_f16/report.json')
p = D/'paired_2x2_natural_f16/report.json'
if p.exists():
    d = json.loads(p.read_text())
    print('  keys', list(d)[:12])
    print('  ', json.dumps(d, ensure_ascii=False)[:1200])
else:
    print('  MISSING; dir:', [x.name for x in (D/'paired_2x2_natural_f16').iterdir()][:10])
