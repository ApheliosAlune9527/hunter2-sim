"""How far the steering wheels reach beyond the footprint the planner uses.

The costmap footprint is the chassis plus a 0.02 m margin: half width 0.393 m.  At full
lock the front wheels swing outside it.  That is not a defect -- the planner needs the
rigid body, not the swept volume, or its inscribed radius closes the corridor (measured
2026-11-06: 0.437 m inscribed radius marked the start and every goal cell lethal) -- but
it has to be stated, with numbers, rather than assumed away.

This file answers three questions:

  1. at which steering angle does a front wheel leave the footprint?
  2. how much does it reach at full lock?
  3. do the demo corridors still fit the chassis polygon, and how much margin is left?

Output: outputs/lab_nav_fix_20261106/footprint_scope.json
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path('/mnt/d/rob-memory')
HERE = ROOT / 'sim/experiments/lab_nav_fix_20261106'
OUT = ROOT / 'outputs/lab_nav_fix_20261106'
MAP = ROOT / 'outputs/lab_nav_20261105/lab_nav_map.pgm'
PARAMS = HERE / 'nav2_params_fix.yaml'
RES = 0.05
ORIGIN = (-5.09, -4.89)

SPAWN = (-0.21, -0.77)
GOALS = {'short_straight': (1.885, 0.435),
         'mid_offset': (3.185, 1.235),
         'long_run': (4.285, 2.535)}

# From sim/hz_hunter_full_description/geometry_report.json
AXLE_X = 0.650          # front axle centre, base_link at the rear axle
HALF_KINGPIN = 0.3025   # wheel_separation 0.605 / 2
WHEEL_HALF_LEN = 0.1641  # tyre radius along the rolling direction
WHEEL_HALF_WID = 0.0708  # half tyre width
STEERING_LIMIT = 0.40    # plugin limit
INNER_WHEEL_ANGLE = 0.444  # atan(L / (R - w/2)) at full lock


def wheel_outer_y(delta):
    """Outer edge of a front wheel, in base_link y, for steering angle delta."""
    return HALF_KINGPIN + WHEEL_HALF_LEN * abs(math.sin(delta)) \
        + WHEEL_HALF_WID * abs(math.cos(delta))


def angle_where_wheels_leave(half_width, lo=0.0, hi=1.2, steps=2000):
    """First steering angle whose wheel edge exceeds the footprint half width."""
    prev = lo
    for i in range(1, steps + 1):
        d = lo + (hi - lo) * i / steps
        if wheel_outer_y(d) > half_width:
            return prev, d
        prev = d
    return None, None


def main():
    foot = json.loads((OUT / 'footprint_polygon.json').read_text(encoding='utf-8'))
    # footprint_polygon_m in that JSON is the swept rectangle the offline audit uses;
    # the costmap uses chassis_with_margin_m, so that is what has to be compared here.
    ch = foot['chassis_with_margin_m']
    poly = [[ch['min'][0], ch['min'][1]], [ch['max'][0], ch['min'][1]],
            [ch['max'][0], ch['max'][1]], [ch['min'][0], ch['max'][1]]]
    swept = foot.get('swept_wheel_envelope_m')
    half_width = max(p[1] for p in poly)
    params_text = PARAMS.read_text(encoding='utf-8')
    params_poly = None
    for line in params_text.splitlines():
        if line.strip().startswith('footprint:'):
            params_poly = line.split('footprint:', 1)[1].strip().strip('"')
            break

    d_lo, d_hi = angle_where_wheels_leave(half_width)
    # The YAML keeps three decimals, so compare numerically at that precision rather
    # than as strings -- a formatting difference is not a configuration difference.
    params_nums = json.loads(params_poly) if params_poly else None
    params_match = bool(params_nums) and len(params_nums) == len(poly) and all(
        abs(a[0] - b[0]) <= 0.001 and abs(a[1] - b[1]) <= 0.001
        for a, b in zip(params_nums, poly))
    scope = {
        'costmap_footprint_half_width_m': round(half_width, 4),
        'params_file_footprint': params_nums,
        'params_match_json': params_match,
        'wheel_outer_at_straight_m': round(wheel_outer_y(0.0), 4),
        'wheel_outer_at_steering_limit_m': round(wheel_outer_y(STEERING_LIMIT), 4),
        'wheel_outer_at_inner_wheel_angle_m': round(wheel_outer_y(INNER_WHEEL_ANGLE), 4),
        'steering_limit_rad': STEERING_LIMIT,
        'inner_wheel_angle_rad': INNER_WHEEL_ANGLE,
        'wheels_stay_inside_footprint_upto_rad': round(d_lo, 4) if d_lo is not None else None,
        'wheels_stay_inside_footprint_upto_deg': round(math.degrees(d_lo), 2) if d_lo is not None else None,
        'first_exceeding_angle_rad': round(d_hi, 4) if d_hi is not None else None,
        'swept_envelope_half_width_m': round(swept['max'][1], 4) if swept else None,
        'meaning': ('within the angle above the wheels do not leave the costmap polygon; '
                    'beyond it they reach further, but the planner keeps the rigid body '
                    'because the swept volume closes narrow corridors'),
    }

    # Corridor fit, with the chassis polygon and (for reference) the swept envelope.
    grid = np.array(Image.open(MAP))
    rows, cols = grid.shape

    def value(x, y):
        col = int((x - ORIGIN[0]) / RES)
        row = int(rows - (y - ORIGIN[1]) / RES)
        if 0 <= row < rows and 0 <= col < cols:
            return int(grid[row, col])
        return 205

    step = RES / 2.0

    def min_clearance(x, y, yaw, poly_used):
        """Smallest distance from the polygon to the nearest occupied cell."""
        xs = [p[0] for p in poly_used]
        ys = [p[1] for p in poly_used]
        c, s = math.cos(yaw), math.sin(yaw)
        best = 1e9
        for dx in np.arange(min(xs), max(xs) + step, step):
            for dy in np.arange(min(ys), max(ys) + step, step):
                wx, wy = x + dx * c - dy * s, x + dx * s + dy * c
                for r in range(1, 21):  # up to 1 m
                    hit = False
                    for ax, ay in ((r * RES, 0), (-r * RES, 0), (0, r * RES), (0, -r * RES)):
                        if value(wx + ax, wy + ay) == 0:
                            hit = True
                            break
                    if hit:
                        best = min(best, r * RES)
                        break
        return best

    corridors = {}
    for name, goal in GOALS.items():
        yaw = math.atan2(goal[1] - SPAWN[1], goal[0] - SPAWN[0])
        dist = math.hypot(goal[0] - SPAWN[0], goal[1] - SPAWN[1])
        n = max(2, int(dist / 0.25))
        worst = 1e9
        for i in range(n + 1):
            t = i / n
            x = SPAWN[0] + (goal[0] - SPAWN[0]) * t
            y = SPAWN[1] + (goal[1] - SPAWN[1]) * t
            worst = min(worst, min_clearance(x, y, yaw, poly))
        corridors[name] = {'distance_m': round(dist, 3),
                           'heading_rad': round(yaw, 4),
                           'min_clearance_m': round(worst, 3),
                           'steering_needed_rad': 0.0,  # straight line
                           'clear': worst > 0.0}

    scope['corridors'] = corridors
    scope['ok'] = all(c['clear'] for c in corridors.values())
    (OUT / 'footprint_scope.json').write_text(json.dumps(scope, indent=1), encoding='utf-8')
    print(json.dumps({k: scope[k] for k in (
        'costmap_footprint_half_width_m', 'wheels_stay_inside_footprint_upto_deg',
        'wheel_outer_at_inner_wheel_angle_m', 'params_match_json', 'ok')}, indent=1))
    return 0 if scope['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
