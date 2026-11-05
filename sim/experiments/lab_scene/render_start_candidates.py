"""Render a 2-D occupancy map with a metric grid and candidate start poses.

Candidates are free cells with the largest clearance to any obstacle/unknown
cell, restricted to a quadrant of the map. Output is a labelled PNG plus JSON so
a human can pick a start cell without guessing coordinates.
"""
from collections import deque
import json
from pathlib import Path
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
MAP = ROOT / 'outputs/lab_map_compare_20261105/lab_odom_06_new.pgm'
YAML = ROOT / 'outputs/lab_map_compare_20261105/lab_odom_06_new.yaml'
OUT = ROOT / 'outputs/lab_map_compare_20261105'
SCALE = 5
RES = 0.05


def load():
    pixels = np.array(Image.open(MAP).convert('L'))
    text = YAML.read_text(encoding='utf-8')
    origin = [float(v) for v in re.search(r'origin:\s*\[([^\]]+)\]', text).group(1).split(',')]
    return pixels, origin


def clearance(free, blocked):
    """BFS distance (in cells) from every free cell to the nearest blocked cell."""
    height, width = free.shape
    dist = np.full((height, width), -1, dtype=np.int32)
    queue = deque()
    for y, x in zip(*np.nonzero(blocked)):
        dist[y, x] = 0
        queue.append((int(y), int(x)))
    while queue:
        cy, cx = queue.popleft()
        for yy, xx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
            if 0 <= yy < height and 0 <= xx < width and dist[yy, xx] < 0:
                dist[yy, xx] = dist[cy, cx] + 1
                queue.append((yy, xx))
    return np.where(free, dist, -1)


def pick_candidates(free, dist, origin, height, top=3):
    """Largest-clearance cells in the lower-left quadrant, kept apart."""
    rows, cols = np.nonzero(free)
    world_x = origin[0] + (cols + 0.5) * RES
    world_y = origin[1] + (height - rows - 0.5) * RES
    mid_x = origin[0] + free.shape[1] * RES * 0.55
    mid_y = origin[1] + height * RES * 0.5
    mask = (world_x < mid_x) & (world_y < mid_y)
    if not mask.any():
        mask = np.ones_like(world_x, dtype=bool)
    score = dist[rows, cols][mask]
    order = np.argsort(-score)
    rows, cols = rows[mask][order], cols[mask][order]
    world_x, world_y, score = world_x[mask][order], world_y[mask][order], score[order]
    chosen = []
    for row, col, x, y, s in zip(rows, cols, world_x, world_y, score):
        if any(abs(row - c['row']) + abs(col - c['col']) < 30 for c in chosen):
            continue
        chosen.append({'row': int(row), 'col': int(col),
                       'x_m': round(float(x), 3), 'y_m': round(float(y), 3),
                       'clearance_m': round(float(s) * RES, 2),
                       'label': chr(ord('A') + len(chosen))})
        if len(chosen) == top:
            break
    return chosen


def main():
    pixels, origin = load()
    free = pixels == 254
    blocked = ~free
    dist = clearance(free, blocked)
    height, width = pixels.shape
    candidates = pick_candidates(free, dist, origin, height)

    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    rgb[pixels == 205] = [205, 205, 205]
    rgb[pixels == 254] = [248, 248, 248]
    rgb[pixels == 0] = [20, 20, 20]
    image = Image.fromarray(rgb).resize((width * SCALE, height * SCALE), Image.Resampling.NEAREST)
    canvas = Image.new('RGB', (image.width + 150, image.height + 90), 'white')
    canvas.paste(image, (110, 60))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 16)
    big = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 20)

    # Metric grid: 1 m lines with labels in map coordinates.
    step = int(round(1.0 / RES))
    for col in range(0, width, step):
        px = 110 + col * SCALE
        draw.line([(px, 60), (px, 60 + image.height)], fill=(120, 170, 230), width=1)
        xw = origin[0] + col * RES
        if col % (step * 5) == 0:
            draw.text((px - 12, canvas.height - 28), '%.0f' % xw, fill='black', font=font)
    for row in range(0, height, step):
        py = 60 + row * SCALE
        draw.line([(110, py), (110 + image.width, py)], fill=(120, 170, 230), width=1)
        yw = origin[1] + (height - row) * RES
        if row % (step * 5) == 0:
            draw.text((52, py - 8), '%.0f' % yw, fill='black', font=font)

    for cand in candidates:
        cx = 110 + cand['col'] * SCALE
        cy = 60 + cand['row'] * SCALE
        draw.ellipse([cx - 11, cy - 11, cx + 11, cy + 11], outline=(200, 30, 30), width=3)
        draw.text((cx + 14, cy - 10), cand['label'], fill=(200, 30, 30), font=big)

    draw.text((110, 14), 'lab_odom_06 (2026-11-01) - grid 1 m, x horizontally, y vertically (map frame)',
              fill='black', font=big)
    draw.text((110, 38), 'red circles = candidate start poses in the lower-left quadrant '
                         '(clearance shown in the JSON)', fill=(90, 90, 90), font=font)
    out = OUT / 'lab_odom_06_start_candidates.png'
    canvas.save(out)
    (OUT / 'start_candidates.json').write_text(
        json.dumps({'map': str(MAP), 'origin': origin, 'resolution': RES,
                    'candidates': candidates}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(candidates, ensure_ascii=False))


if __name__ == '__main__':
    main()
