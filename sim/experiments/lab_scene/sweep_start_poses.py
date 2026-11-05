"""Zoomed candidate sweep along the lower-left band of the 2026-11-01 map."""
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
RES = 0.05
SCALE = 22                      # pixels per metre in the zoom
TARGET_Y = -0.32                # keep the same row the user picked as C
XS = [0.70, 0.45, 0.20, -0.05, -0.30, -0.55, -0.80]
VIEW = (-2.6, 2.6, -3.0, 1.8)   # xmin, xmax, ymin, ymax (metres, map frame)


def load():
    pixels = np.array(Image.open(MAP).convert('L'))
    origin = [float(v) for v in re.search(r'origin:\s*\[([^\]]+)\]',
                                          YAML.read_text(encoding='utf-8')).group(1).split(',')]
    return pixels, origin


def clearance(free, blocked):
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


def cell_of(x, y, origin, height):
    col = int(round((x - origin[0]) / RES - 0.5))
    row = int(round(height - (y - origin[1]) / RES - 0.5))
    return row, col


def nearest_free(free, dist, row, col, radius=25):
    """Nearest free cell with the best clearance inside a small window."""
    best = None
    height, width = free.shape
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            r, c = row + dy, col + dx
            if not (0 <= r < height and 0 <= c < width) or not free[r, c]:
                continue
            score = dist[r, c] - 0.35 * (dy * dy + dx * dx) ** 0.5
            if best is None or score > best[0]:
                best = (score, r, c)
    return None if best is None else (best[1], best[2])


def main():
    pixels, origin = load()
    free = pixels == 254
    dist = clearance(free, ~free)
    height, width = pixels.shape
    picks = []
    for index, x in enumerate(XS, start=1):
        row, col = cell_of(x, TARGET_Y, origin, height)
        found = nearest_free(free, dist, row, col)
        if found is None:
            continue
        row, col = found
        picks.append({
            'label': 'P%d' % index,
            'row': int(row), 'col': int(col),
            'x_m': round(origin[0] + (col + 0.5) * RES, 3),
            'y_m': round(origin[1] + (height - row - 0.5) * RES, 3),
            'clearance_m': round(float(dist[row, col]) * RES, 2),
        })

    xmin, xmax, ymin, ymax = VIEW
    c0 = int((xmin - origin[0]) / RES)
    c1 = int((xmax - origin[0]) / RES)
    r0 = int(height - (ymax - origin[1]) / RES)
    r1 = int(height - (ymin - origin[1]) / RES)
    c0, c1 = max(0, c0), min(width, c1)
    r0, r1 = max(0, r0), min(height, r1)
    crop = pixels[r0:r1, c0:c1]
    rgb = np.zeros((*crop.shape, 3), dtype=np.uint8)
    rgb[crop == 205] = [205, 205, 205]
    rgb[crop == 254] = [250, 250, 250]
    rgb[crop == 0] = [20, 20, 20]
    image = Image.fromarray(rgb).resize(((c1 - c0) * SCALE, (r1 - r0) * SCALE),
                                        Image.Resampling.NEAREST)
    canvas = Image.new('RGB', (image.width + 120, image.height + 80), 'white')
    canvas.paste(image, (95, 50))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 15)
    big = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)

    step = int(round(0.5 / RES))
    for col in range(c0 - c0 % step, c1, step):
        px = 95 + (col - c0) * SCALE
        xw = origin[0] + (col + 0.5) * RES
        draw.line([(px, 50), (px, 50 + image.height)], fill=(150, 190, 235), width=1)
        draw.text((px - 14, canvas.height - 26), '%.1f' % xw, fill='black', font=font)
    for row in range(r0 - r0 % step, r1, step):
        py = 50 + (row - r0) * SCALE
        yw = origin[1] + (height - row - 0.5) * RES
        draw.line([(95, py), (95 + image.width, py)], fill=(150, 190, 235), width=1)
        draw.text((40, py - 7), '%.1f' % yw, fill='black', font=font)

    for pick in picks:
        cx = 95 + (pick['col'] - c0) * SCALE
        cy = 50 + (pick['row'] - r0) * SCALE
        draw.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], outline=(200, 30, 30), width=3)
        draw.text((cx + 12, cy - 9), '%s (%.2f m)' % (pick['label'], pick['clearance_m']),
                  fill=(200, 30, 30), font=big)

    draw.text((95, 12), 'lower-left band, y = %.2f m : sweep towards -x' % TARGET_Y,
              fill='black', font=big)
    draw.text((95, 32), 'grid 0.5 m; red circles = candidate start poses; '
                        'number in brackets = clearance to nearest obstacle',
              fill=(90, 90, 90), font=font)
    out = OUT / 'lab_odom_06_start_sweep.png'
    canvas.save(out)
    (OUT / 'start_sweep.json').write_text(
        json.dumps({'map': str(MAP), 'origin': origin, 'target_y_m': TARGET_Y,
                    'view': VIEW, 'candidates': picks}, ensure_ascii=False, indent=2),
        encoding='utf-8')
    print(json.dumps(picks, ensure_ascii=False))


if __name__ == '__main__':
    main()
