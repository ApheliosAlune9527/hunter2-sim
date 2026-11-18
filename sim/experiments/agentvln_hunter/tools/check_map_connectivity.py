#!/usr/bin/env python3
import os, sys
import numpy as np
from PIL import Image
from scipy import ndimage

yaml_path = sys.argv[1]
meta = {}
for line in open(yaml_path):
    if ":" in line and not line.lstrip().startswith("#"):
        k, v = line.split(":", 1)
        meta[k.strip()] = v.split("#", 1)[0].strip()
image_path = meta["image"]
if not os.path.isabs(image_path):
    image_path = os.path.join(os.path.dirname(os.path.abspath(yaml_path)), image_path)
img = np.array(Image.open(image_path).convert("L"))
H, W = img.shape
res = float(meta["resolution"])
ox, oy = [float(v) for v in meta["origin"].strip("[]").split(",")[:2]]
free = img >= 240
lbl, n = ndimage.label(free, structure=np.ones((3, 3)))
print("map", image_path, "shape", (H, W), "res", res, "origin", (ox, oy))
print("free components", n, "free px", int(free.sum()))
for spec in sys.argv[2:]:
    name, x, y = spec.split(",")
    c = int(round((float(x) - ox) / res))
    r = int(round(H - 1 - (float(y) - oy) / res))
    v = int(img[r, c])
    lab = int(lbl[r, c])
    print(f"{name:12s} xy=({float(x):.3f},{float(y):.3f}) cell=({c},{r}) val={v} label={lab} component_px={int((lbl==lab).sum()) if lab else 0}")
