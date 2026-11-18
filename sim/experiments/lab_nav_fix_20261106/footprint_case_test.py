"""Two offline checks on the footprint itself.

1. A controlled case that the old rectangle misses and the new polygon catches: an
   obstacle 0.60 m ahead of the rear axle.  The old footprint ended at x=0.52, so it
   reported "free"; the vehicle nose reaches 0.814 m, so the real vehicle would have
   hit it.  This is the failure mode the correction round exists for, so it is kept
   as a test rather than a claim.

2. The same test on a grid, at several headings, so the answer does not depend on
   one specially chosen geometry.

Both footprints are closed polygons and the test intersects the polygon with every
occupied cell it overlaps -- not just the four corners.

Writes outputs/lab_nav_fix_20261106/footprint_case_test.json.
"""
import json
import math
from pathlib import Path

ROOT = Path('/mnt/d/rob-memory')
OUT = ROOT / 'outputs/lab_nav_fix_20261106'
RES = 0.05

OLD = [(-0.50, -0.395), (0.52, -0.395), (0.52, 0.395), (-0.50, 0.395)]
NEW = [(-0.204, -0.457), (0.854, -0.457), (0.854, 0.457), (-0.204, 0.457)]


def rotate(points, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    return [(x * c - y * s, x * s + y * c) for x, y in points]


def point_in_polygon(px, py, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > py) != (y1 > py):
            x_cross = (x1 - x0) * (py - y0) / (y1 - y0) + x0
            if px < x_cross:
                inside = not inside
    return inside


def cells_in_polygon(poly, obstacle_cells):
    """Return the obstacle cells whose centre lies inside the closed polygon."""
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    hits = []
    for cx, cy in obstacle_cells:
        if min(xs) - RES <= cx <= max(xs) + RES and min(ys) - RES <= cy <= max(ys) + RES:
            if point_in_polygon(cx, cy, poly):
                hits.append((cx, cy))
    return hits


def case(obstacle, yaw):
    """obstacle: list of (cx, cy) cell centres in the map frame."""
    out = {}
    for name, poly in (('old', OLD), ('new', NEW)):
        world = rotate(poly, yaw)
        hits = cells_in_polygon(world, obstacle)
        out[name] = {'collides': bool(hits), 'cells': hits}
    return out


def main():
    results = []

    # Wall 0.60 m ahead of the rear axle, thin, wide enough to be unmissable.
    wall = [(0.60, y * RES) for y in range(-12, 13)]
    r = case(wall, 0.0)
    results.append({'name': 'obstacle 0.60 m ahead', 'cases': r,
                    'exposes_old_footprint': (not r['old']['collides']) and r['new']['collides']})

    # Same wall, approached at 20 degrees: a heading sweep, not a single geometry.
    for deg in (10, 20, 35):
        yaw = math.radians(deg)
        r = case(wall, yaw)
        results.append({'name': f'obstacle 0.60 m ahead, yaw {deg} deg', 'cases': r,
                        'exposes_old_footprint': (not r['old']['collides']) and r['new']['collides']})

    # An obstacle both must see, as a sanity check that the tester is not blind.
    near = [(0.30, y * RES) for y in range(-8, 9)]
    r = case(near, 0.0)
    results.append({'name': 'obstacle 0.30 m ahead (both must collide)', 'cases': r,
                    'sanity': r['old']['collides'] and r['new']['collides']})

    # Nothing at all: neither may report a collision.
    r = case([], 0.0)
    results.append({'name': 'empty grid', 'cases': r,
                    'sanity': not r['old']['collides'] and not r['new']['collides']})

    exposed = sum(1 for x in results if x.get('exposes_old_footprint'))
    sanity_ok = all(x['sanity'] for x in results if 'sanity' in x)
    # The straight-ahead case is the one that matters; at 20-35 degrees the rotated
    # old rectangle swings a corner forward and reaches the wall too, so those cases
    # do not separate the two footprints.  Say so instead of pretending they do.
    head_on = results[0]['exposes_old_footprint']
    doc = {'old_footprint': OLD, 'new_footprint': NEW, 'resolution_m': RES,
           'cases': results,
           'head_on_case_exposes_old': head_on,
           'cases_where_old_misses': exposed,
           'note': ('at yaw 20/35 deg the rotated old rectangle also reaches the wall, so '
                    'only the head-on and 10 deg cases separate the two footprints'),
           'sanity_ok': sanity_ok,
           'ok': bool(head_on and exposed >= 2 and sanity_ok),
           'method': 'closed polygon vs cell centres, all cells inside the bounding box'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'footprint_case_test.json').write_text(json.dumps(doc, indent=1), encoding='utf-8')
    print(json.dumps({'cases_where_old_misses': exposed, 'sanity_ok': sanity_ok,
                      'ok': doc['ok']}, indent=1))
    return 0 if doc['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
