
import json
from pathlib import Path
D = Path('/mnt/d/rob-memory/outputs/agentvln_hunter_20261109_meeting')
for name in ('nav_goal.json', 'nav_cancel.json'):
    p = D / name
    print('==', name, 'exists', p.exists())
    if not p.exists():
        continue
    d = json.loads(p.read_text())
    keys = [k for k in d if k not in ('track',)]
    print('   ', {k: d[k] for k in keys if isinstance(d[k], (int, float, str, type(None)))})
