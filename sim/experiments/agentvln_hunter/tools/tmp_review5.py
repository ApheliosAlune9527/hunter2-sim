
import json
from pathlib import Path
D = Path('/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy')
v = json.loads((D/'validation_summary.json').read_text())
print('keys', list(v))
print(json.dumps({k: v[k] for k in list(v)[:6]}, ensure_ascii=False)[:900])
trials = v.get('trials') or v.get('runs') or []
print('trials', len(trials))
for t in trials:
    print(' -', {k: t.get(k) for k in ('name','label','mode','status','success','parking_distance_m','parking_ok','final_truth','model_calls','tool_calls','docked')})
