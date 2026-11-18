
import json
from pathlib import Path
for tag in ('20261110_044500', '20261110_043800'):
    d = json.loads(Path('/mnt/d/rob-memory/outputs/agentvln_reverse_record_%s/report.json' % tag).read_text())
    ev = d.get('evaluation') or {}
    print('==', tag, 'pass', d['pass'], '| error', str(d.get('error'))[:60])
    print('   face', [round(v,3) for v in d['face']['centre']], 'heading', round(d['face']['heading'],3), 'span', round(d['face']['span_m'],3))
    print('   dock', [round(v,3) for v in d['measured_dock']])
    if ev: print('   eval', {k: (round(ev[k],3) if isinstance(ev[k], float) else ev[k]) for k in ('lateral_m','yaw_error_rad','front_standoff_m','final_truth')})
    for i, leg in enumerate(d['legs']):
        print('   leg', i, leg['phase'], 'status', leg['status'], 'clear', round(leg['audit']['clearance_m'],3), leg['audit']['obstacle'])
