"""Find the leftmost feasible start poses (largest -x) in the 2026-11-01 map."""
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
SCALE = 22
MIN_CLEARANCE_M = 1.20
TIERS = (1.20, 1.00, 0.80, 0.60)
VIEW = (-3.0, 2.4, -3.2, 2.2)


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


def main():
    pixels, origin = load()
    free = pixels == 254
    dist = clearance(free, ~free)
    height, width = pixels.shape
    picks = []
    for tier in TIERS:
        need = int(round(tier / RES))
        rows, cols = np.nonzero(free & (dist >= need))
        if len(rows) == 0:
            continue
        world_x = origin[0] + (cols + 0.5) * RES
        world_y = origin[1] + (height - rows - 0.5) * RES
        order = np.lexsort((world_y, world_x))
        for index in order:
            x, y = float(world_x[index]), float(world_y[index])
            if any(abs(x - p['x_m']) < 0.30 and abs(y - p['y_m']) < 0.30 for p in picks):
                continue
            picks.append({'label': 'T%.1f' % tier,
                          'row': int(rows[index]), 'col': int(cols[index]),
                          'x_m': round(x, 3), 'y_m': round(y, 3),
                          'clearance_m': round(float(dist[rows[index], cols[index]]) * RES, 2)})
            break

    # Free-space profile: how far left does free space reach at each y.
    profile = []
    for metres in np.arange(-3.0, 2.0, 0.25):
        row = int(round(height - (metres - origin[1]) / RES - 0.5))
        if not (0 <= row < height):
            continue
        cols_here = np.nonzero(free[row])[0]
        if len(cols_here) == 0:
            continue
        profile.append({'y_m': round(float(metres), 2),
                        'free_x_min_m': round(origin[0] + (cols_here.min() + 0.5) * RES, 2),
                        'free_x_max_m': round(origin[0] + (cols_here.max() + 0.5) * RES, 2)})

    xmin, xmax, ymin, ymax = VIEW
    c0 = max(0, int((xmin - origin[0]) / RES))
    c1 = min(width, int((xmax - origin[0]) / RES))
    r0 = max(0, int(height - (ymax - origin[1]) / RES))
    r1 = min(height, int(height - (ymin - origin[1]) / RES))
    crop = pixels[r0:r1, c0:c1]
    rgb = np.zeros((*crop.shape, 3), dtype=np.uint8)
    rgb[crop == 205] = [205, 205, 205]
    rgb[crop == 254] = [250, 250, 250]
    rgb[crop == 0] = [20, 20, 20]
    image = Image.fromarray(rgb).resize(((c1 - c0) * SCALE, (r1 - r0) * SCALE),
                                        Image.Resampling.NEAREST)
    canvas = Image.new('RGB', (image.width + 130, image.height + 80), 'white')
    canvas.paste(image, (100, 50))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 15)
    big = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
    step = int(round(0.5 / RES))
    for col in range(c0 - c0 % step, c1, step):
        px = 100 + (col - c0) * SCALE
        draw.line([(px, 50), (px, 50 + image.height)], fill=(150, 190, 235), width=1)
        draw.text((px - 14, canvas.height - 26),
                  '%.1f' % (origin[0] + (col + 0.5) * RES), fill='black', font=font)
    for row in range(r0 - r0 % step, r1, step):
        py = 50 + (row - r0) * SCALE
        draw.line([(100, py), (100 + image.width, py)], fill=(150, 190, 235), width=1)
        draw.text((45, py - 7), '%.1f' % (origin[1] + (height - row - 0.5) * RES),
                  fill='black', font=font)
    for pick in picks:
        cx = 100 + (pick['col'] - c0) * SCALE
        cy = 50 + (pick['row'] - r0) * SCALE
        draw.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], outline=(200, 30, 30), width=3)
        draw.text((cx + 12, cy - 9), '%s %.2fm' % (pick['label'], pick['clearance_m']),
                  fill=(200, 30, 30), font=big)
    draw.text((100, 12), 'leftmost feasible start poses (clearance >= %.1f m)' % MIN_CLEARANCE_M,
              fill='black', font=big)
    out = OUT / 'lab_odom_06_leftmost.png'
    canvas.save(out)
    (OUT / 'leftmost_poses.json').write_text(
        json.dumps({'map': str(MAP), 'origin': origin, 'min_clearance_m': MIN_CLEARANCE_M,
                    'candidates': picks, 'free_space_profile': profile},
                   ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'candidates': picks}, ensure_ascii=False))


if __name__ == '__main__':
    main()
