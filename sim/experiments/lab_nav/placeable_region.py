"""Where can the vehicle actually sit, and which goals are worth evaluating?

Two different questions, both answered from the same map:

* the *placeable* region: cells whose whole rotated footprint, plus a half-cell
  margin, stays on known-free map.  ``all_headings`` is the strict version used
  for goal selection, ``any_heading`` is the optimistic upper bound.
* goal candidates: one per distance band, chosen from the largest strictly
  placeable component with the most clearance, so a failure later means the
  navigation stack failed rather than the goal being inside furniture.

The output is deliberately conservative: unknown cells are treated as blocked,
because the localisation is truth-based and must not depend on guessed geometry.
"""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'sim/experiments/lab_scene'))
import traversability as T  # noqa: E402  (shares the footprint erosion maths)

NAV = ROOT / 'outputs/lab_nav_20261105'
MAP = NAV / 'lab_nav_map.pgm'
YAML = NAV / 'lab_nav_map.yaml'
GEOMETRY = ROOT / 'sim/hz_hunter_full_description/geometry_report.json'
HEADINGS = list(range(0, 360, 5))
SPAWN = (-0.21, -0.77)
BANDS = [
    ('short_straight', 2.0, (-30, 30)),
    ('mid_offset', 4.0, (30, 75)),
    ('long_run', 6.0, (-20, 40)),
    ('far_turn', 8.0, (45, 110)),
]


def load():
    pixels = np.array(Image.open(MAP).convert('L'))
    text = YAML.read_text(encoding='utf-8')
    origin = [float(v) for v in re.search(r'origin:\s*\[([^\]]+)\]', text).group(1).split(',')]
    res = float(re.search(r'resolution:\s*([\d.]+)', text).group(1))
    return pixels, pixels == 254, origin, res


def to_world(col, row, origin, res, rows):
    return origin[0] + (col + 0.5) * res, origin[1] + (rows - row - 0.5) * res


def main():
    pixels, free, origin, res = load()
    rows, cols = pixels.shape
    # The costmap footprint is the senior's, not the CAD envelope: the region must
    # agree with the shape Nav2 actually plans with, otherwise "placeable" and
    # "plannable" disagree and goals are rejected for the wrong reason.
    geometry = json.loads(GEOMETRY.read_text(encoding='utf-8'))
    bounds = geometry['bare_chassis_bounds_m']
    xmin, xmax = -0.50, 0.52
    ymin, ymax = -0.395, 0.395
    geometry['cad_envelope_m'] = bounds

    any_heading = np.zeros_like(free)
    all_headings = free.copy()
    masks = {}
    for heading in HEADINGS:
        safe = T.erode(free, T.rectangle_offsets(xmin, xmax, ymin, ymax, heading))
        masks[heading] = safe
        any_heading |= safe
        all_headings &= safe

    any_size, any_points = T.largest_component(any_heading)
    loose = np.zeros_like(free)
    for y, x in any_points:
        loose[y, x] = True
    strict_size, strict_points = T.largest_component(all_headings)
    strict = np.zeros_like(free)
    for y, x in strict_points:
        strict[y, x] = True

    # Clearance inside the strict region: BFS from every non-placeable cell.
    from collections import deque
    dist = np.full(free.shape, -1, dtype=int)
    queue = deque()
    for y, x in np.argwhere(~strict):
        dist[y, x] = 0
        queue.append((int(y), int(x)))
    while queue:
        cy, cx = queue.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < rows and 0 <= nx < cols and dist[ny, nx] < 0:
                dist[ny, nx] = dist[cy, cx] + 1
                queue.append((ny, nx))
    clearance = np.maximum(dist, 0) * res

    area = res * res
    candidates, used = [], []

    def straight_corridor_free(wx, wy, heading):
        """True when a straight run from the spawn to the goal keeps the
        footprint clear at the driving heading.

        A forward-only Ackermann vehicle cannot rotate in place, so a goal that
        is placeable but cut off by a narrow gap is not a fair navigation target.
        """
        mask = masks[int(round(heading / 5.0)) % 72 * 5]
        steps = max(8, int(math.hypot(wx - SPAWN[0], wy - SPAWN[1]) / (res * 0.5)))
        for i in range(steps + 1):
            f = i / steps
            px = SPAWN[0] + (wx - SPAWN[0]) * f
            py = SPAWN[1] + (wy - SPAWN[1]) * f
            col = int((px - origin[0]) / res)
            row = int(rows - (py - origin[1]) / res)
            if not (0 <= row < rows and 0 <= col < cols) or not mask[row, col]:
                return False
        return True

    for name, distance, sector in BANDS:
        options = []
        for y, x in any_points:
            wx, wy = to_world(x, y, origin, res, rows)
            r = math.hypot(wx - SPAWN[0], wy - SPAWN[1])
            if abs(r - distance) > 0.45:
                continue
            bearing = math.degrees(math.atan2(wy - SPAWN[1], wx - SPAWN[0]))
            if not (sector[0] <= bearing <= sector[1]):
                continue
            if any(math.hypot(wx - u[0], wy - u[1]) < 1.5 for u in used):
                continue
            options.append((clearance[y, x], wx, wy, int(x), int(y), r, bearing))
        options.sort(key=lambda o: o[0], reverse=True)
        chosen = None
        for score, wx, wy, col, row, r, bearing in options[:400]:
            if straight_corridor_free(wx, wy, bearing):
                chosen = (score, wx, wy, col, row, r, bearing)
                break
        if chosen is None:
            candidates.append({'name': name, 'feasible': False,
                               'reason': 'no placeable cell with a free straight corridor'})
            continue
        score, wx, wy, col, row, r, bearing = chosen
        used.append((wx, wy))
        candidates.append({'name': name, 'feasible': True, 'x': round(wx, 3),
                           'y': round(wy, 3), 'yaw': round(math.radians(bearing), 4),
                           'clearance_m': round(float(score), 3),
                           'distance_from_spawn_m': round(r, 3),
                           'bearing_deg': round(bearing, 1),
                           'straight_corridor_free': True,
                           'col': col, 'row': row})

    image = Image.open(MAP).convert('RGB')
    draw = ImageDraw.Draw(image)
    for y, x in np.argwhere(any_heading):
        image.putpixel((int(x), int(y)), (120, 190, 150))
    for y, x in np.argwhere(strict):
        image.putpixel((int(x), int(y)), (40, 120, 220))
    sx = int(round((SPAWN[0] - origin[0]) / res))
    sy = int(round(rows - (SPAWN[1] - origin[1]) / res))
    draw.ellipse([sx - 4, sy - 4, sx + 4, sy + 4], outline=(200, 0, 0), width=2)
    for c in candidates:
        if not c.get('feasible'):
            continue
        cx = int(round((c['x'] - origin[0]) / res))
        cy = int(round(rows - (c['y'] - origin[1]) / res))
        draw.line([sx, sy, cx, cy], fill=(200, 0, 0), width=1)
        draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], outline=(200, 0, 0), width=3)
        draw.text((cx + 7, cy - 6), c['name'], fill=(200, 0, 0))
    out_png = NAV / 'placeable_region.png'
    image.save(out_png)

    result = {
        'map': str(MAP),
        'resolution_m': res,
        'origin_m': origin,
        'footprint_m': {'x': [xmin, xmax], 'y': [ymin, ymax]},
        'headings_deg': HEADINGS,
        'spawn': {'x': SPAWN[0], 'y': SPAWN[1], 'yaw': 0.0},
        'any_heading': {'cells': int(any_heading.sum()),
                        'area_m2': round(float(any_heading.sum()) * area, 2),
                        'note': 'upper bound: admits at least one heading, an Ackermann vehicle cannot rotate in place'},
        'all_headings': {'cells': int(all_headings.sum()),
                         'area_m2': round(float(all_headings.sum()) * area, 2)},
        'strict_largest_component': {'cells': int(strict_size),
                                     'area_m2': round(strict_size * area, 2)},
        'spawn_placeable_all_headings': bool(all_headings[
            int(round(rows - (SPAWN[1] - origin[1]) / res)),
            int(round((SPAWN[0] - origin[0]) / res))]),
        'goals': candidates,
        'preview': str(out_png),
    }
    (NAV / 'placeable_region.json').write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                               encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('any_heading', 'all_headings',
                                             'strict_largest_component',
                                             'spawn_placeable_all_headings')}, indent=1))
    for c in candidates:
        print(c['name'], '->', c.get('x'), c.get('y'),
              'clearance', c.get('clearance_m'), 'dist', c.get('distance_from_spawn_m'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
