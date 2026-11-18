#!/usr/bin/env python3
import sys, heapq
import numpy as np
from PIL import Image
from scipy import ndimage

meta = {}
for line in open(sys.argv[1]):
    if ":" in line and not line.lstrip().startswith("#"):
        k, v = line.split(":", 1)
        meta[k.strip()] = v.split("#", 1)[0].strip()
import os
p = meta["image"]
if not os.path.isabs(p):
    p = os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), p)
img = np.array(Image.open(p).convert("L"))
H, W = img.shape
res = float(meta["resolution"])
ox, oy = [float(v) for v in meta["origin"].strip("[]").split(",")[:2]]
free = img >= 240
dist = ndimage.distance_transform_edt(free) * res

def cell(x, y):
    return int(round((x - ox) / res)), int(round(H - 1 - (y - oy) / res))

def max_bottleneck(a, b, step=0.01):
    # largest clearance threshold at which a and b remain connected
    lo, hi = 0.0, float(dist.max()) + step
    best = 0.0
    while hi - lo > step:
        mid = (lo + hi) / 2
        mask = dist >= mid
        lbl, n = ndimage.label(mask, structure=np.ones((3, 3)))
        if lbl[a[1], a[0]] and lbl[a[1], a[0]] == lbl[b[1], b[0]]:
            best = mid; lo = mid
        else:
            hi = mid
    return best

robot = cell(0.31, -0.72)
for name, x, y in [("short", 1.885, 0.435), ("short_east", 2.100, 0.435),
                   ("short_south", 1.885, 0.135), ("mid", 3.185, 1.235),
                   ("long", 4.285, 2.535)]:
    g = cell(x, y)
    b = max_bottleneck(robot, g)
    print(f"{name:12s} cell={g} clearance_at_goal={dist[g[1],g[0]]:.3f}m "
          f"max_bottleneck_from_robot={b:.2f}m")
    # locate cells near the bottleneck that block at b+0.02
    mask = dist >= b + 0.02
    lbl, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if lbl[robot[1], robot[0]] != 0 and lbl[g[1], g[0]] != 0 and lbl[robot[1], robot[0]] != lbl[g[1], g[0]]:
        pass
print("robot_clearance", dist[robot[1], robot[0]])
