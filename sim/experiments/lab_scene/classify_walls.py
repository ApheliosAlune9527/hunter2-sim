"""Classify occupied cells by connected-component size to separate walls from fragments."""
from collections import deque
import json
from pathlib import Path
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'outputs/lab_map_compare_20261105'
MAP = SRC / 'lab_odom_06_filled.pgm'
YAML = SRC / 'lab_odom_06_filled.yaml'
RES = 0.05
BIG = 200          # >= this many cells -> treated as a real structure


def load():
    pixels = np.array(Image.open(MAP).convert('L'))
    origin = [float(v) for v in re.search(r'origin:\s*\[([^\]]+)\]',
                                          YAML.read_text(encoding='utf-8')).group(1).split(',')]
    return pixels, origin


def label(mask):
    height, width = mask.shape
    labels = np.zeros((height, width), dtype=np.int32)
    current = 0
    for y, x in zip(*np.nonzero(mask)):
        if labels[y, x]:
            continue
        current += 1
        queue = deque([(int(y), int(x))])
        labels[y, x] = current
        while queue:
            cy, cx = queue.popleft()
            for yy, xx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1),
                           (cy - 1, cx - 1), (cy - 1, cx + 1), (cy + 1, cx - 1), (cy + 1, cx + 1)):
                if 0 <= yy < height and 0 <= xx < width and mask[yy, xx] and not labels[yy, xx]:
                    labels[yy, xx] = current
                    queue.append((yy, xx))
    return labels, current


def main():
    pixels, origin = load()
    occupied = pixels == 0
    height, width = pixels.shape
    labels, count = label(occupied)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    groups = {'big': [], 'mid': [], 'small': []}
    for index in range(1, count + 1):
        cell_count = int(sizes[index])
        if cell_count == 0:
            continue
        ys, xs = np.nonzero(labels == index)
        bbox = [int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())]
        entry = {'id': index, 'cells': cell_count, 'bbox_cells': bbox,
                 'width_m': round((bbox[1] - bbox[0] + 1) * RES, 2),
                 'height_m': round((bbox[3] - bbox[2] + 1) * RES, 2)}
        if cell_count >= BIG:
            groups['big'].append(entry)
        elif cell_count >= 20:
            groups['mid'].append(entry)
        else:
            groups['small'].append(entry)

    rgb = np.stack([pixels] * 3, axis=-1).astype(np.uint8)
    rgb[pixels == 254] = [250, 250, 250]
    rgb[pixels == 205] = [215, 215, 215]
    lut = np.zeros((count + 1, 3), dtype=np.uint8)
    for index in range(1, count + 1):
        cell_count = int(sizes[index])
        if cell_count == 0:
            continue
        if cell_count >= BIG:
            lut[index] = [20, 20, 20]
        elif cell_count >= 20:
            lut[index] = [235, 140, 20]
        else:
            lut[index] = [220, 40, 40]
    mask = labels > 0
    rgb[mask] = lut[labels[mask]]
    image = Image.fromarray(rgb).resize((width * 4, height * 4), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 22)
    for entry in sorted(groups['big'], key=lambda e: -e['cells'])[:8]:
        b = entry['bbox_cells']
        draw.text(((b[0] + (b[1] - b[0]) / 2) * 4 - 10, (b[2] + (b[3] - b[2]) / 2) * 4 - 10),
                  str(entry['cells']), fill=(0, 90, 200), font=font)
    out = SRC / 'occupied_components.png'
    image.save(out)
    summary = {
        'components_total': int(count),
        'big_cells': int(sum(e['cells'] for e in groups['big'])),
        'big_count': len(groups['big']),
        'mid_cells': int(sum(e['cells'] for e in groups['mid'])),
        'mid_count': len(groups['mid']),
        'small_cells': int(sum(e['cells'] for e in groups['small'])),
        'small_count': len(groups['small']),
        'big_examples': sorted(groups['big'], key=lambda e: -e['cells'])[:8],
    }
    (SRC / 'occupied_components.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'big_examples'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
