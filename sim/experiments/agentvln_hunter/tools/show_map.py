#!/usr/bin/env python3
"""ASCII occupancy slice with configurable bounds; stdlib + numpy/PIL/yaml."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
import yaml

ROOT = Path('/mnt/d/rob-memory')
YAML = ROOT / 'outputs/lab_nav_fix_20261106/lab_nav_map_fix.yaml'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--x0', type=float, default=-1.0)
    ap.add_argument('--x1', type=float, default=5.0)
    ap.add_argument('--y0', type=float, default=-3.0)
    ap.add_argument('--y1', type=float, default=4.0)
    ap.add_argument('--step', type=float, default=0.1)
    a = ap.parse_args()
    meta = yaml.safe_load(YAML.read_text())
    img = np.array(Image.open(YAML.parent / meta['image']))
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

    xs = np.arange(a.x0, a.x1 + 1e-9, a.step)
    ys = np.arange(a.y0, a.y1 + 1e-9, a.step)
    print('x %.1f..%.1f y %.1f..%.1f step %.2f' % (a.x0, a.x1, a.y0, a.y1, a.step))
    print('     ' + ''.join(str(int(round(x * 10)) % 10) for x in xs))
    for y in ys[::-1]:
        print('%5.2f %s' % (y, ''.join(cell(x, y) for x in xs)))


if __name__ == '__main__':
    main()
