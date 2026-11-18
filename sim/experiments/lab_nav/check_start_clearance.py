#!/usr/bin/env python3
"""Footprint-aware clearance check for a candidate start pose on the nav map.

Clearance is the Euclidean distance (metres) from a cell to the nearest cell that
is *not* free.  Writes a JSON report next to the map package.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

INF = 1e9


def chamfer(mask_blocked, res):
    """Distance (metres) from every cell to the nearest blocked cell.

    Two-pass 8-neighbour chamfer transform, implemented with array shifts so each
    pass is vectorised over the whole image.
    """
    h, w = mask_blocked.shape
    d = np.where(mask_blocked, 0.0, INF)
    shifted = {}

    def nbr(minimum, arr, dy, dx, step):
        out = np.full_like(arr, INF)
        ys = slice(max(0, dy), h + min(0, dy))
        yd = slice(max(0, -dy), h + min(0, -dy))
        xs = slice(max(0, dx), w + min(0, dx))
        xd = slice(max(0, -dx), w + min(0, -dx))
        out[yd, xd] = arr[ys, xs] + step
        return np.minimum(minimum, out)

    # forward pass: neighbours from the top-left half
    for r in range(1, h):
        d[r] = np.minimum(d[r], d[r - 1] + 1.0)
        d[r, 1:] = np.minimum(d[r, 1:], d[r - 1, :-1] + 1.41421356)
        d[r, 1:] = np.minimum(d[r, 1:], d[r, :-1] + 1.0)
        d[r, :-1] = np.minimum(d[r, :-1], d[r - 1, 1:] + 1.41421356)
    # backward pass: neighbours from the bottom-right half
    for r in range(h - 2, -1, -1):
        d[r] = np.minimum(d[r], d[r + 1] + 1.0)
        d[r, :-1] = np.minimum(d[r, :-1], d[r + 1, 1:] + 1.41421356)
        d[r, :-1] = np.minimum(d[r, :-1], d[r, 1:] + 1.0)
        d[r, 1:] = np.minimum(d[r, 1:], d[r + 1, :-1] + 1.41421356)
    del shifted
    return d * res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True)
    ap.add_argument("--x", type=float, required=True)
    ap.add_argument("--y", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--thresholds", default="0.55,0.65,0.80,1.00")
    args = ap.parse_args()

    img = np.array(Image.open(args.map).convert("L"))
    h, w = img.shape
    res, ox, oy = 0.05, -5.09, -4.89

    occ = img == 0
    free = img == 254
    unknown = ~occ & ~free

    clear_occ = chamfer(occ, res)
    clear_all = chamfer(~free, res)  # unknown counts as blocked

    def to_cell(x, y):
        return h - 1 - int(round((y - oy) / res)), int(round((x - ox) / res))

    def to_world(r, c):
        return (c + 0.5) * res + ox, (h - 1 - r - 0.5) * res + oy

    r0, c0 = to_cell(args.x, args.y)
    report = {
        "map": args.map,
        "spawn": {"x": args.x, "y": args.y, "row": int(r0), "col": int(c0),
                  "value": int(img[r0, c0])},
        "clearance_occupied_only_m": round(float(clear_occ[r0, c0]), 3),
        "clearance_including_unknown_m": round(float(clear_all[r0, c0]), 3),
        "candidates": [],
    }

    for thr in [float(t) for t in args.thresholds.split(",")]:
        ok = clear_all >= thr
        ys, xs = np.where(ok)
        if len(ys) == 0:
            continue
        dd = (xs - c0) ** 2 + (ys - r0) ** 2
        b = int(np.argmin(dd))
        wx, wy = to_world(int(ys[b]), int(xs[b]))
        report["candidates"].append({
            "threshold_m": thr, "x": round(wx, 3), "y": round(wy, 3),
            "clearance_m": round(float(clear_all[ys[b], xs[b]]), 3),
            "distance_from_spawn_m": round(float(np.sqrt(dd[b])) * res, 3),
        })

    report["spawn_is_usable"] = bool(clear_all[r0, c0] >= 0.55)
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
