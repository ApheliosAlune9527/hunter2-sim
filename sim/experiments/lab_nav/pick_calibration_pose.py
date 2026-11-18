"""Pick a wide-open calibration pose for drivetrain tests.

Chooses the free cell with the largest distance to any obstacle, then the heading
with the longest free run, so a straight-line test never ends against a wall.
"""
import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'outputs/lab_nav_20261105'
MAP = OUT / 'lab_nav_map.pgm'
YAML = OUT / 'lab_nav_map.yaml'

text = YAML.read_text(encoding='utf-8')
res = float(re.search(r'resolution:\s*([\d.]+)', text).group(1))
origin = [float(v) for v in re.search(r'origin:\s*\[([^\]]+)\]', text).group(1).split(',')]

pixels = np.array(Image.open(MAP).convert('L'))
occupied = pixels == 0
unknown = pixels == 205
blocked = occupied | unknown

# Distance transform without scipy: iterative chamfer on the blocked mask.
dist = np.where(blocked, 0.0, 1e6)
h, w = dist.shape
for _ in range(400):
    prev = dist.copy()
    pad = np.pad(dist, 1, constant_values=0.0)
    dist = np.minimum(dist, np.minimum.reduce([
        pad[:-2, 1:-1] + 1.0, pad[2:, 1:-1] + 1.0,
        pad[1:-1, :-2] + 1.0, pad[1:-1, 2:] + 1.0,
        pad[:-2, :-2] + 1.4142, pad[:-2, 2:] + 1.4142,
        pad[2:, :-2] + 1.4142, pad[2:, 2:] + 1.4142]))
    if np.allclose(prev, dist):
        break

# Ignore the outer unknown sea: only consider cells inside the scanned room.
dist[unknown] = 0.0
best = np.unravel_index(int(np.argmax(dist)), dist.shape)
row, col = int(best[0]), int(best[1])
x = origin[0] + (col + 0.5) * res
y = origin[1] + (row + 0.5) * res
clearance = float(dist[row, col]) * res


def free_run(angle, max_m=20.0):
    step = res / 2.0
    n = int(max_m / step)
    for i in range(1, n):
        px = x + math.cos(angle) * i * step
        py = y + math.sin(angle) * i * step
        c = int((px - origin[0]) / res)
        r = int((py - origin[1]) / res)
        if not (0 <= r < h and 0 <= c < w) or blocked[r, c]:
            return i * step
    return max_m


best_heading, best_run = 0.0, 0.0
for deg in range(0, 360, 5):
    ang = math.radians(deg)
    run = free_run(ang)
    if run > best_run:
        best_heading, best_run = ang, run
# Prefer a cardinal-aligned heading when it is nearly as good.
for deg in (0, 90, 180, 270):
    ang = math.radians(deg)
    run = free_run(ang)
    if run >= best_run - 0.1:
        best_heading, best_run = ang, run

result = {
    'x': round(x, 3), 'y': round(y, 3), 'yaw_rad': round(best_heading, 4),
    'yaw_deg': round(math.degrees(best_heading), 1),
    'clearance_m': round(clearance, 3),
    'free_run_m': round(best_run, 3),
    'cell': {'col': col, 'row': row},
}
(OUT / 'calibration_pose.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
