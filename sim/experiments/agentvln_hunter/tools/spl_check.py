#!/usr/bin/env python3
"""Lab SPL for the recorded VLM docking runs, with an explicit reference model.

The reference is an 8-connected A* over the frozen occupancy map, restricted to
cells whose distance to any occupied cell is at least the footprint inscribed
radius (0.393 m).  It is *not* a Dubin-feasible shortest path: the vehicle
cannot follow a grid path with 1.669 m turning radius, so the reference is a
lower bound on any real shortest path and the resulting SPL is an upper bound.
That is stated in the output and in the README; it is still the closest thing to
the plan's "same-constraint shortest reference" that can be computed offline.
"""
import argparse
import heapq
import json
import math
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

ROOT = Path('/mnt/d/rob-memory')
MAP_YAML = ROOT / 'sim/experiments/agentvln_hunter/config/straight_nav_map/lab_nav_map_fix.yaml'
LAYOUT = ROOT / 'sim/experiments/agentvln_hunter/config/target_layout_straight.json'
RUNS = ROOT / 'outputs/agentvln_hunter_20261108_vlm_deploy'
REPRO = ROOT / 'outputs/agentvln_hunter_20261109_repro_check'
CLEARANCE_M = 0.393


def load_map():
    meta = yaml.safe_load(MAP_YAML.read_text())
    img = np.array(Image.open(MAP_YAML.parent / meta['image']))
    h, w = img.shape
    res = meta['resolution']
    ox, oy = meta['origin'][0], meta['origin'][1]
    # value >= 250 is free on this map (occupancy below free_thresh)
    free = img >= 250
    return free, res, ox, oy, h, w


def clearance_mask(free, res, radius_m):
    r = int(math.ceil(radius_m / res))
    occ = ~free
    # distance transform without scipy: iterative dilation of obstacles
    blocked = occ.copy()
    for _ in range(r):
        b = blocked.copy()
        b[1:, :] |= blocked[:-1, :]
        b[:-1, :] |= blocked[1:, :]
        b[:, 1:] |= blocked[:, :-1]
        b[:, :-1] |= blocked[:, 1:]
        blocked = b
    return free & ~blocked


def astar(ok, res, ox, oy, start, goal):
    h, w = ok.shape

    def cell(x, y):
        c = int((x - ox) / res)
        r = h - 1 - int((y - oy) / res)
        return r, c

    sr, sc = cell(*start)
    gr, gc = cell(*goal)

    def nearest_free(r, c):
        if 0 <= r < h and 0 <= c < w and ok[r, c]:
            return r, c
        best = None
        for dr in range(-20, 21):
            for dc in range(-20, 21):
                rr, cc = r + dr, c + dc
                if 0 <= rr < h and 0 <= cc < w and ok[rr, cc]:
                    d = dr * dr + dc * dc
                    if best is None or d < best[0]:
                        best = (d, rr, cc)
        return (best[1], best[2]) if best else None

    s = nearest_free(sr, sc)
    g = nearest_free(gr, gc)
    if s is None or g is None:
        return None, None
    nbrs = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
            (-1, -1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (1, 1, 1.4142)]
    dist = {s: 0.0}
    prev = {}
    pq = [(0.0, 0.0, s)]
    while pq:
        _f, d, (r, c) = heapq.heappop(pq)
        if (r, c) == g:
            break
        if d > dist.get((r, c), 1e18):
            continue
        for dr, dc, cost in nbrs:
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w and ok[rr, cc]:
                nd = d + cost * res
                if nd < dist.get((rr, cc), 1e18):
                    dist[(rr, cc)] = nd
                    prev[(rr, cc)] = (r, c)
                    heapq.heappush(pq, (nd + res * math.hypot(rr - g[0], cc - g[1]), nd, (rr, cc)))
    if g not in dist:
        return None, None
    # reconstruct actual length
    length = 0.0
    cur = g
    while cur != s:
        p = prev[cur]
        length += math.hypot(cur[0] - p[0], cur[1] - p[1]) * res
        cur = p
    return length, (s, g)


def track_length(track):
    pts = [tuple(t['truth'][:2]) for t in track if t.get('truth')]
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])), pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    free, res, ox, oy, h, w = load_map()
    ok = clearance_mask(free, res, CLEARANCE_M)
    ok_free = free
    layout = json.loads(LAYOUT.read_text())
    zone = layout['parking_zone']
    goal = (zone['x'], zone['y'])

    cases = []
    summary = json.loads((RUNS / 'validation_summary.json').read_text())
    for name, r in summary['runs'].items():
        # Only the dock legs: their start is the observation pose and their goal
        # is the parking centre, so a single reference path is well defined.
        if r.get('mode') not in ('vlm', 'oracle'):
            continue
        p = RUNS / r['evidence']
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        nav = d.get('nav') or {}
        track = nav.get('track') or []
        if not track:
            continue
        length, pts = track_length(track)
        start = tuple(d.get('start_truth') or pts[0])[:2]
        # The recorded track starts on the first controller tick, a few cm after
        # the seeded pose; prepend the start pose so the length is not truncated.
        length += math.hypot(pts[0][0] - start[0], pts[0][1] - start[1])
        cases.append((name, start, length, p))
    p = REPRO / 'virtual_dock/report.json'
    if p.exists():
        d = json.loads(p.read_text())
        track = (d.get('nav') or {}).get('track') or []
        if track:
            length, pts = track_length(track)
            cases.append(('repro_virtual_dock', pts[0], length, p))

    rows = []
    for name, start, actual, path in cases:
        ref_free, _ = astar(ok_free, res, ox, oy, start, goal)
        ref_clear, _ = astar(ok, res, ox, oy, start, goal)
        row = {'run': name, 'start': [round(v, 3) for v in start],
               'goal': [round(zone['x'], 3), round(zone['y'], 3)],
               'reference_free_m': None if ref_free is None else round(ref_free, 3),
               'reference_clear_m': None if ref_clear is None else round(ref_clear, 3),
               'actual_m': round(actual, 3)}
        if ref_free and actual > 0:
            row['spl_free'] = round(min(1.0, ref_free / actual), 3)
        if ref_clear and actual > 0:
            row['spl_clear'] = round(min(1.0, ref_clear / actual), 3)
        rows.append(row)
    out = {'reference_model': 'astar_8conn_on_frozen_map',
           'clearance_m': CLEARANCE_M,
           'caveat': 'grid shortest path, not Dubin-feasible; SPL is an upper bound',
           'map': str(MAP_YAML), 'rows': rows}
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
