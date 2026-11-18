"""Did any recorded navigation run actually touch a wall?

The runs stored "0 collisions" from the Gazebo Contact topic.  That topic turns
out never to be advertised in this build, so the number was produced by a source
that carried nothing and it means "not measured", not "no contact".  This script
answers the weaker question the saved tracks *can* answer:

    did the recorded footprint ever overlap an occupied map cell?

It is a geometric check against the same 2D map the planner used, on the poses
sampled during the run.  It cannot see a contact that happened and resolved
between two samples, and it says nothing about force -- a vehicle can push
against a wall without the footprint ever entering an occupied cell.

``clearance_m`` below is the distance from the footprint edge to the nearest
occupied cell; a negative value means overlap.
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'sim/experiments/lab_nav'))
import placeable_region as P  # noqa: E402

NAV = ROOT / 'outputs/lab_nav_20261105'
# Senior's costmap footprint, the same rectangle the planner and the region use.
FOOT = (-0.50, 0.52, -0.395, 0.395)


def corners(x, y, yaw):
    c, s = np.cos(yaw), np.sin(yaw)
    pts = []
    for fx in (FOOT[0], FOOT[1]):
        for fy in (FOOT[2], FOOT[3]):
            pts.append((x + fx * c - fy * s, y + fx * s + fy * c))
    return np.array(pts)


def main():
    pixels, free, origin, res = P.load()
    rows, cols = pixels.shape
    occupied = pixels == 0
    # Distance from every cell centre to the nearest occupied cell.
    dist_to_wall = ndimage.distance_transform_edt(~occupied) * res

    report = {}
    for tag, name in (('truth', 'nav_eval_tracks.json'), ('amcl', 'nav_eval_tracks_amcl.json')):
        path = NAV / name
        if not path.exists():
            continue
        tracks = json.loads(path.read_text())
        per_run = {}
        for key, points in tracks.items():
            worst = None
            worst_point = None
            out_of_map = 0
            for p in points:
                inside = True
                for x, y in corners(p['x'], p['y'], p['yaw']):
                    col = int((x - origin[0]) / res)
                    row = int(rows - (y - origin[1]) / res)
                    if not (0 <= row < rows and 0 <= col < cols):
                        inside = False
                        break
                if not inside:
                    out_of_map += 1
                    continue
                # Sample the footprint edge densely, then take the smallest wall distance.
                poly = corners(p['x'], p['y'], p['yaw'])
                samples = []
                for i in range(4):
                    a, b = poly[i], poly[(i + 1) % 4]
                    for f in np.linspace(0.0, 1.0, 12):
                        samples.append(a + (b - a) * f)
                m = None
                for sx, sy in samples:
                    c = int((sx - origin[0]) / res)
                    r = int(rows - (sy - origin[1]) / res)
                    c = min(max(c, 0), cols - 1)
                    r = min(max(r, 0), rows - 1)
                    d = dist_to_wall[r, c]
                    m = d if m is None else min(m, d)
                if worst is None or m < worst:
                    worst = m
                    worst_point = {'x': round(p['x'], 3), 'y': round(p['y'], 3),
                                   't': round(p['t'], 2)}
            per_run[key] = {'min_edge_clearance_m': None if worst is None else round(float(worst), 3),
                            'at': worst_point,
                            'samples': len(points)}
            if out_of_map:
                per_run[key]['poses_outside_map'] = out_of_map
        overlaps = [k for k, v in per_run.items()
                    if v['min_edge_clearance_m'] is not None and v['min_edge_clearance_m'] <= 0.0]
        report[tag] = {
            'runs': per_run,
            'runs_with_footprint_overlap': overlaps,
            'how': 'footprint corners and edge samples tested against the occupancy '
                   'grid distance field, using the truth poses stored during the run',
            'limits': 'samples the run poses; a brief contact between samples is '
                      'invisible, and pushing against a wall without overlap is not '
                      'a contact in this test',
        }
    out = NAV / 'track_collision_audit.json'
    out.write_text(json.dumps(report, indent=1), encoding='utf-8')
    for tag, r in report.items():
        worst = min(v['min_edge_clearance_m'] for v in r['runs'].values()
                    if v['min_edge_clearance_m'] is not None)
        print(tag, 'runs', len(r['runs']), 'min clearance', worst,
              'overlaps', r['runs_with_footprint_overlap'])


if __name__ == '__main__':
    main()
