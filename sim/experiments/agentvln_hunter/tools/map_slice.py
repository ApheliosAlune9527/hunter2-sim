#!/usr/bin/env python3
"""Print an ASCII occupancy slice around known points (no ROS needed)."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
import yaml

root = Path('/mnt/d/rob-memory')
yaml_path = root / 'outputs/lab_nav_fix_20261106/lab_nav_map_fix.yaml'
meta = yaml.safe_load(yaml_path.read_text())
img = np.array(Image.open(yaml_path.parent / meta['image']))
h, w = img.shape
ox, oy = meta['origin'][0], meta['origin'][1]
res = meta['resolution']

def cell(x, y):
    c = int((x - ox) / res)
    r = int((y - oy) / res)
    if 0 <= r < h and 0 <= c < w:
        v = img[r, c]
        if v <= 50:
            return '#'
        if v >= 250:
            return '.'
        return '?'
    return ' '

xs = np.arange(0.0, 3.21, 0.1)
ys = np.arange(-1.3, 0.61, 0.1)
print('x from 0.0 to 3.2, y from -1.3 to 0.6 (row 0 = y=0.6)')
for y in ys[::-1]:
    row = ''
    for x in xs:
        ch = cell(x, y)
        if abs(x - (-0.21)) < 0.05 and abs(y - (-0.77)) < 0.05:
            ch = 'R'
        for name, mx, my in [('A', 2.5, -1.05), ('B', 2.5, -0.75), ('C', 2.5, -0.45)]:
            if abs(x - mx) < 0.05 and abs(y - my) < 0.05:
                ch = name
        row += ch
    print(f'{y:5.2f} {row}')
print('     ' + ''.join(str(int(x * 10) % 10) for x in xs))
