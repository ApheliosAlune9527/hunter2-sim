#!/usr/bin/env python3
"""Why the reverse-dock parking leg was cancelled: clearance profile of the plan."""
import json
import sys
from pathlib import Path

sys.path.insert(0, '/mnt/d/rob-memory/sim/experiments/agentvln_reverse_dock')
from clearance import SceneClearance  # noqa: E402

rep = json.loads(Path('/mnt/d/rob-memory/outputs/agentvln_reverse_record_20261110_042000/report.json').read_text())
sdf = '/mnt/d/rob-memory/sim/experiments/agentvln_hunter/scenes/lab_agentvln_bigfar_straight.sdf'
sc = SceneClearance(sdf)

def profile(poses, label):
    worst = None
    for p in poses:
        d, obstacle, kind = sc.at(p)
        if worst is None or d < worst[0]:
            worst = (d, obstacle, kind, [round(v, 3) for v in p])
    print('%-28s min %.3f m  at %s  obstacle %s' % (label, worst[0], worst[3], worst[1]))
    return worst

leg = rep['legs'][3]
path = [list(p) for p in leg['path']]
profile(path, 'planned parking path')
profile([[2.486837286110067, 2.1470780105468257, 0.7227317401212451]], 'pose where it cancelled')

dock = rep['measured_dock']
print('dock', [round(v, 3) for v in dock])
profile([dock], 'dock pose')

# straight approach along the dock line, from L metres west
for L in (1.0, 1.5, 2.0, 2.5):
    poses = []
    for i in range(21):
        t = i / 20.0
        poses.append([dock[0] - L * (1 - t), dock[1], dock[2]])
    profile(poses, 'straight-in L=%.1f m' % L)

# lateral shift of the dock line away from the wall
face_y = rep['face']['centre'][1]
for dy in (0.0, -0.15, -0.30):
    poses = [[dock[0] - 2.0 * (1 - i / 20.0), dock[1] + dy, dock[2]] for i in range(21)]
    profile(poses, 'straight-in dy=%+.2f' % dy)

# where is the north wall along this corridor
for x in (2.0, 2.5, 3.0, 3.5, 4.0):
    d, obstacle, kind = sc.at([x, 2.38, 0.019])
    print('pose y=2.38 x=%.1f clearance %.3f  %s' % (x, d, obstacle))
