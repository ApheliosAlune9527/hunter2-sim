"""Remove isolated occupied fragments inside an area that is known to be open floor.

A fragment whose entire 1-cell surrounding ring is free is not a wall: real walls
connect to other walls or border unknown space.
"""
from collections import deque
import json
from pathlib import Path
import re

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'outputs/lab_map_compare_20261105'
MAP = SRC / 'lab_odom_06_filled.pgm'
YAML = SRC / 'lab_odom_06_filled.yaml'
PREVIEW = SRC / 'fragment_cleanup.png'
RES = 0.05
MIN_Y_M = 13.0


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
            for yy, xx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= yy < height and 0 <= xx < width and mask[yy, xx] and not labels[yy, xx]:
                    labels[yy, xx] = current
                    queue.append((yy, xx))
    return labels, current


def main():
    pixels = np.array(Image.open(MAP).convert('L'))
    origin = [float(v) for v in re.search(r'origin:\s*\[([^\]]+)\]',
                                          YAML.read_text(encoding='utf-8')).group(1).split(',')]
    height, width = pixels.shape
    world_y = origin[1] + (height - np.arange(height) - 0.5) * RES
    region = (world_y >= MIN_Y_M)[:, None]

    occupied = (pixels == 0) & region
    labels, count = label(occupied)
    free = pixels == 254
    remove = np.zeros_like(occupied)
    removed_components = 0
    for index in range(1, count + 1):
        ys, xs = np.nonzero(labels == index)
        y0, y1 = max(0, ys.min() - 1), min(height, ys.max() + 2)
        x0, x1 = max(0, xs.min() - 1), min(width, xs.max() + 2)
        patch = labels[y0:y1, x0:x1] == index
        ring = np.zeros_like(patch, dtype=bool)
        ring[1:-1, 1:-1] = patch[1:-1, 1:-1]
        grown = ring.copy()
        grown[1:, :] |= ring[:-1, :]
        grown[:-1, :] |= ring[1:, :]
        grown[:, 1:] |= ring[:, :-1]
        grown[:, :-1] |= ring[:, 1:]
        outside = grown & ~patch
        if outside.any() and free[y0:y1, x0:x1][outside].all():
            remove[labels == index] = True
            removed_components += 1

    cleaned = pixels.copy()
    cleaned[remove] = 254
    Image.fromarray(cleaned).save(MAP)

    rgb = np.stack([pixels] * 3, axis=-1).astype(np.uint8)
    rgb[remove] = [230, 120, 40]
    Image.fromarray(rgb).resize((width * 4, height * 4),
                                Image.Resampling.NEAREST).save(PREVIEW)

    receipt = {
        'rule': 'occupied component whose whole 1-cell ring is free -> not a wall',
        'region_y_min_m': MIN_Y_M,
        'components_removed': removed_components,
        'cells_removed': int(remove.sum()),
        'remaining_occupied': int((cleaned == 0).sum()),
        'preview': str(PREVIEW),
    }
    (SRC / 'fragment_cleanup_receipt.json').write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
