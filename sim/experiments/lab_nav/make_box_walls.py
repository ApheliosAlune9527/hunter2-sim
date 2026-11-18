"""Replace the triangle-mesh wall collision with one box per merged map rectangle.

The mesh collision makes ODE pay for the whole 1.3 MB trimesh every step; boxes
let the broadphase prune. Visual mesh is kept.
"""
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path('/mnt/d/rob-memory')
OUT = ROOT / 'outputs/lab_nav_20261105'
MAP = OUT / 'lab_nav_map.pgm'
YAML = OUT / 'lab_nav_map.yaml'
SRC = OUT / 'lab_nav_world_drive.sdf'
HEIGHT = 2.4


def runs(mask):
    boxes = []
    for y, row in enumerate(mask):
        edges = np.diff(np.r_[False, row, False].astype(np.int8))
        starts = np.flatnonzero(edges == 1)
        ends = np.flatnonzero(edges == -1)
        for x0, x1 in zip(starts, ends):
            boxes.append([int(x0), int(x1), int(y), int(y) + 1])
    return boxes


def merge_vertical(boxes):
    """Grow each run downward while the next row has the identical span."""
    boxes.sort(key=lambda b: (b[0], b[1], b[2]))
    merged = []
    active = {}
    for x0, x1, y0, y1 in boxes:
        key = (x0, x1)
        last = active.get(key)
        if last is not None and last[3] == y0:
            last[3] = y1
        else:
            new = [x0, x1, y0, y1]
            active[key] = new
            merged.append(new)
    return merged


pixels = np.array(Image.open(MAP).convert('L'))
origin = [float(v) for v in re.search(r'origin:\s*\[([^\]]+)\]',
                                      YAML.read_text(encoding='utf-8')).group(1).split(',')]
res = float(re.search(r'resolution:\s*([\d.]+)',
                      YAML.read_text(encoding='utf-8')).group(1))

occupied = pixels == 0
row_runs = runs(occupied)
rects = merge_vertical(row_runs)

tree = ET.parse(SRC)
world = tree.getroot().find('world')
link = world.find("model[@name='walls']").find("link[@name='walls_link']")
for collision in link.findall('collision'):
    link.remove(collision)

for x0, x1, y0, y1 in rects:
    cx = origin[0] + (x0 + x1) / 2.0 * res
    cy = origin[1] + (y0 + y1) / 2.0 * res
    sx = (x1 - x0) * res
    sy = (y1 - y0) * res
    coll = ET.SubElement(link, 'collision', {'name': f'w_{x0}_{y0}'})
    ET.SubElement(coll, 'pose').text = f'{cx:.4f} {cy:.4f} {HEIGHT / 2:.3f} 0 0 0'
    geom = ET.SubElement(coll, 'geometry')
    box = ET.SubElement(geom, 'box')
    ET.SubElement(box, 'size').text = f'{sx:.4f} {sy:.4f} {HEIGHT}'

dst = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / 'probe_boxes.sdf'
tree.write(dst, encoding='utf-8', xml_declaration=True)
print(f'rects={len(rects)} from row_runs={len(row_runs)} -> {dst}')
