"""Does the corrected footprint still fit the corridor the teaching demo uses?

The footprint grew from 0.79 x 1.02 m to 0.914 x 1.058 m, so a corridor that was
comfortable before may now be marginal.  This checks the straight line from the spawn
pose to the first teaching goal against the map's occupied cells, with the polygon
rotated to the heading of travel, and reports where -- if anywhere -- it overlaps.
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path('/mnt/d/rob-memory')
OUT = ROOT / 'outputs/lab_nav_fix_20261106'
MAP = ROOT / 'outputs/lab_nav_20261105/lab_nav_map.pgm'
RES = 0.05
ORIGIN = (-5.09, -4.89)

SPAWN = (-0.21, -0.77)
GOALS = {'short_straight': (1.885, 0.435),
         'mid_offset': (3.185, 1.235),
         'long_run': (4.285, 2.535)}


def main():
    poly = json.loads((OUT / 'footprint_polygon.json').read_text())['footprint_polygon_m']
    grid = np.array(Image.open(MAP))
    rows, cols = grid.shape

    def value(x, y):
        col = int((x - ORIGIN[0]) / RES)
        row = int(rows - (y - ORIGIN[1]) / RES)
        if 0 <= row < rows and 0 <= col < cols:
            return int(grid[row, col])
        return 205

    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    reach = max(max(map(abs, xs)), max(map(abs, ys)))
    step = RES / 2.0

    def overlap(x, y, yaw):
        c, s = math.cos(yaw), math.sin(yaw)
        for dx in np.arange(min(xs), max(xs) + step, step):
            for dy in np.arange(min(ys), max(ys) + step, step):
                wx, wy = x + dx * c - dy * s, y + dx * s + dy * c
                if value(wx, wy) == 0:
                    return (round(wx, 2), round(wy, 2))
        return None

    report = {'footprint_m': poly, 'spawn': SPAWN, 'goals': {}}
    for name, goal in GOALS.items():
        yaw = math.atan2(goal[1] - SPAWN[1], goal[0] - SPAWN[0])
        dist = math.hypot(goal[0] - SPAWN[0], goal[1] - SPAWN[1])
        n = max(2, int(dist / RES))
        hits = []
        for i in range(n + 1):
            t = i / n
            x = SPAWN[0] + (goal[0] - SPAWN[0]) * t
            y = SPAWN[1] + (goal[1] - SPAWN[1]) * t
            hit = overlap(x, y, yaw)
            if hit:
                hits.append({'at': [round(x, 2), round(y, 2)], 'overlap': list(hit)})
        report['goals'][name] = {'distance_m': round(dist, 3),
                                 'heading_rad': round(yaw, 4),
                                 'overlaps': len(hits), 'first': hits[:3],
                                 'clear': not hits}

    # The spawn pose itself has to be legal, otherwise the demo starts inside a wall.
    report['spawn_clear'] = overlap(SPAWN[0], SPAWN[1], 0.0) is None
    report['ok'] = report['spawn_clear'] and all(g['clear'] for g in report['goals'].values())
    (OUT / 'corridor_check.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    print(json.dumps({'spawn_clear': report['spawn_clear'],
                      'goals': {k: v['overlaps'] for k, v in report['goals'].items()},
                      'ok': report['ok']}, indent=1))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
