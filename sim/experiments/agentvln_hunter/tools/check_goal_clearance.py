#!/usr/bin/env python3
"""Check static-map clearance for a HUNTER goal pose.

Reads a Nav2 map YAML/PGM, samples the chassis footprint at the goal,
and reports distance to the nearest occupied / unknown map cell.
"""
import sys
import math
import numpy as np
from PIL import Image

HUNTER_FOOTPRINT = [(-0.184, -0.393), (0.834, -0.393), (0.834, 0.393), (-0.184, 0.393)]

def parse_yaml(path):
    meta = {}
    with open(path, "r") as f:
        for line in f:
            if ":" not in line or line.lstrip().startswith("#"):
                continue
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.split("#", 1)[0].strip()
            if k in ("image", "mode"):
                meta[k] = v
            elif k in ("resolution", "occupied_thresh", "free_thresh", "negate"):
                meta[k] = float(v)
            elif k == "origin":
                meta[k] = [float(x) for x in v.strip("[]").split(",")]
    return meta

def sample_footprint(yaw, step=0.02):
    c, s = math.cos(yaw), math.sin(yaw)
    pts = []
    # boundary + interior grid in local frame
    xs = np.arange(-0.184, 0.834 + 1e-9, step)
    ys = np.arange(-0.393, 0.393 + 1e-9, step)
    for x in xs:
        for y in (ys[0], ys[-1]):
            pts.append((x, y))
    for y in ys:
        for x in (xs[0], xs[-1]):
            pts.append((x, y))
    for x in xs:
        for y in ys:
            pts.append((x, y))
    out = np.array([(c * x - s * y, s * x + c * y) for x, y in pts])
    return out

def main():
    yaml_path = sys.argv[1]
    goals = []
    for spec in sys.argv[2:]:
        name, x, y, yaw = spec.split(",")
        goals.append((name, float(x), float(y), float(yaw)))
    meta = parse_yaml(yaml_path)
    image_path = meta["image"]
    if not image_path.startswith("/"):
        image_path = "/".join(yaml_path.split("/")[:-1] + [image_path])
    img = np.array(Image.open(image_path).convert("L"))
    H, W = img.shape
    res = meta["resolution"]
    ox, oy, _ = meta["origin"]
    print("map", image_path, "size", W, H, "res", res, "origin", (ox, oy))
    vals, counts = np.unique(img, return_counts=True)
    print("hist", list(zip(vals.tolist(), counts.tolist()))[:20])
    occupied = img < 65
    unknown = (img >= 65) & (img < 240)
    print("occupied px", int(occupied.sum()), "unknown px", int(unknown.sum()))
    occ_pts = np.argwhere(occupied)
    occ_xy = np.column_stack((ox + (occ_pts[:, 1] + 0.5) * res,
                              oy + (H - occ_pts[:, 0] - 0.5) * res))
    unk_pts = np.argwhere(unknown)
    unk_xy = np.column_stack((ox + (unk_pts[:, 1] + 0.5) * res,
                              oy + (H - unk_pts[:, 0] - 0.5) * res)) if len(unk_pts) else np.zeros((0, 2))
    for name, gx, gy, yaw in goals:
        foot = sample_footprint(yaw)
        world = foot + np.array([gx, gy])
        d_occ = np.sqrt(((world[:, None, :] - occ_xy[None, :, :]) ** 2).sum(axis=2)).min()
        d_unk = np.sqrt(((world[:, None, :] - unk_xy[None, :, :]) ** 2).sum(axis=2)).min() if len(unk_xy) else float("inf")
        col = int((gx - ox) / res)
        row = int(H - 1 - (gy - oy) / res)
        center_val = int(img[row, col]) if 0 <= row < H and 0 <= col < W else -1
        print(f"{name}: goal=({gx:.3f},{gy:.3f},{yaw:.3f}) center_px=({col},{row}) val={center_val} "
              f"min_dist_occupied={d_occ:.3f}m min_dist_unknown={d_unk:.3f}m")

if __name__ == "__main__":
    main()
