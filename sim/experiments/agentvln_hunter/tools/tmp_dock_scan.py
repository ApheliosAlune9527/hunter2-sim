
import sys, math, json
sys.path.insert(0, '/mnt/d/rob-memory/sim/experiments/agentvln_hunter/tools')
from target_dock import footprint_clear_boxes, FRONT_LENGTH
from pathlib import Path
layout = json.loads(Path('/mnt/d/rob-memory/sim/experiments/agentvln_hunter/config/target_layout.json').read_text())
boxes = [{'name': b['name'], 'x': b['x'], 'y': b['y']} for b in layout['blue_boxes']]
print('boxes', boxes)
target = (5.307, 1.921)
ok_rows = []
x = 4.00
while x <= 4.70:
    y = 1.35
    while y <= 2.15:
        yaw = round(math.atan2(target[1]-y, target[0]-x), 3)
        ok, hit = footprint_clear_boxes(round(x,2), round(y,2), yaw, boxes)
        if ok:
            ok_rows.append((round(x,2), round(y,2), yaw, round(math.hypot(target[0]-x, target[1]-y)-FRONT_LENGTH, 3)))
        y += 0.05
    x += 0.05
print('clear poses:', len(ok_rows))
for r in ok_rows[:40]:
    print(r)
