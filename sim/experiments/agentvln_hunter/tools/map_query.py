#!/usr/bin/env python3
"""Print raw map pixel, occupancy and nearest-cell value for points."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
import yaml

YAML = Path('/mnt/d/rob-memory/outputs/lab_nav_fix_20261106/lab_nav_map_fix.yaml')
meta = yaml.safe_load(YAML.read_text())
img = np.array(Image.open(YAML.parent / meta['image']))
h, w = img.shape
res = meta['resolution']
ox, oy = meta['origin'][0], meta['origin'][1]

for s in sys.argv[1:]:
    x, y = map(float, s.split(','))
    c, r = int((x - ox) / res), int((y - oy) / res)
    v = int(img[r, c]) if 0 <= r < h and 0 <= c < w else None
    occ = None if v is None else (255 - v) / 255.0
    print('x=%.3f y=%.3f cell=(%d,%d) value=%s occupancy=%s' % (x, y, c, r, v, occ))
