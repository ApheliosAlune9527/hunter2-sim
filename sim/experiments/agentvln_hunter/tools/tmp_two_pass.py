
import json
from pathlib import Path
for tag in ('20261110_045651','20261110_060500'):
    p = Path('/mnt/d/rob-memory/outputs/agentvln_reverse_record_%s/report.json' % tag)
    d = json.loads(p.read_text())
    ev = d.get('evaluation') or {}
    print(tag, 'pass', d['pass'], 'checks', json.dumps(d.get('checks')))
    print('   lateral', round(ev.get('lateral_m', 0), 3), 'yaw_deg', round(ev.get('yaw_error_rad', 0)*57.2958, 2),
          'standoff', round(ev.get('front_standoff_m', 0), 3), 'min_clear', round(d['whole_episode_audit']['clearance_m'], 3),
          'model', d['model_decision']['model'], 'sel', d['model_decision']['raw'].strip()[:40])
