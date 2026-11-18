
import json
from pathlib import Path
U = Path('/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_step5_unblock')
lay = json.loads((U/'target_layout_straight.json').read_text())
print('== layout keys', list(lay))
for b in lay.get('blue_boxes', []):
    print('  box', b)
print('  obs', lay.get('observation_pose'), 'dock', lay.get('expected_dock'), 'zone', lay.get('parking_zone'))
print('  instruction', lay.get('instruction'))
D = Path('/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy')
for name in ('straight_frame/report.json', 'natural_frame/report.json'):
    p = D/name
    if p.exists():
        r = json.loads(p.read_text())
        print('==', name, 'keys', list(r)[:10])
        for c in r.get('candidates', []):
            print('   id', c.get('id'), 'bbox', c.get('bbox_xywh'), 'area', c.get('area_px'), 'depth', c.get('depth_median_m'))
        print('   summary', {k: r.get(k) for k in ('horizontal_gap_px','far_to_near_area_ratio','robot_pose')})
    else:
        print(name, 'MISSING', [x.name for x in p.parent.iterdir()][:8])
