
import json
from pathlib import Path
U = Path('/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_step5_unblock')
print('== step5_unblock files:', sorted(p.name for p in U.iterdir())[:20])
g = json.loads((U/'geometry_check.json').read_text()) if (U/'geometry_check.json').exists() else None
print('== geometry_check keys:', list(g) if g else 'MISSING')
if g:
    print(json.dumps(g, ensure_ascii=False)[:1800])
