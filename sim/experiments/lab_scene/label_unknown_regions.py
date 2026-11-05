"""Label the connected unknown regions of the 2026-11-01 map so a human can point at one."""
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
MIN_CELLS = 200
SCALE = 26
VIEW_TOP = 0.55          # show the top 55 % of the map


def load():
    pixels = np.array(Image.open(MAP).convert('L'))
    origin = [float(v) for v in re.search(r'origin:\s*\[([^\]]+)\]',
                                          YAML.read_text(encoding='utf-8')).group(1).split(',')]
    return pixels, origin


def label_components(mask):
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
    pixels, origin = load()
    unknown = pixels == 205
    labels, count = label_components(unknown)
    height, width = pixels.shape
    rows = []
    for index in range(1, count + 1):
        ys, xs = np.nonzero(labels == index)
        cells = len(ys)
        if cells < MIN_CELLS:
            continue
        rows.append({
            'label': 'U%d' % index, 'id': index, 'cells': int(cells),
            'bbox_cells': [int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())],
            'bbox_m': [round(origin[0] + xs.min() * RES, 2), round(origin[0] + (xs.max() + 1) * RES, 2),
                       round(origin[1] + (height - ys.max() - 1) * RES, 2),
                       round(origin[1] + (height - ys.min()) * RES, 2)],
            'touches_map_border': bool(xs.min() == 0 or ys.min() == 0
                                       or xs.max() == width - 1 or ys.max() == height - 1),
        })
    rows.sort(key=lambda r: -r['cells'])

    keep = {r['id'] for r in rows[:12]}
    r1 = int(height * (1 - VIEW_TOP))
    crop_pixels = pixels[r1:, :]
    crop_labels = labels[r1:, :]
    rgb = np.zeros((*crop_pixels.shape, 3), dtype=np.uint8)
    rgb[crop_pixels == 205] = [210, 210, 210]
    rgb[crop_pixels == 254] = [250, 250, 250]
    rgb[crop_pixels == 0] = [20, 20, 20]
    for index in keep:
        rgb[crop_labels == index] = [255, 214, 160]
    image = Image.fromarray(rgb).resize((crop_pixels.shape[1] * SCALE, crop_pixels.shape[0] * SCALE),
                                        Image.Resampling.NEAREST)
    canvas = Image.new('RGB', (image.width + 130, image.height + 70), 'white')
    canvas.paste(image, (100, 45))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 14)
    step = int(round(1.0 / RES))
    for col in range(0, crop_pixels.shape[1], step):
        px = 100 + col * SCALE
        draw.line([(px, 45), (px, 45 + image.height)], fill=(150, 190, 235), width=1)
        if col % (step * 2) == 0:
            draw.text((px - 12, canvas.height - 22),
                      '%.0f' % (origin[0] + col * RES), fill='black', font=small)
    for row in range(0, crop_pixels.shape[0], step):
        py = 45 + row * SCALE
        draw.line([(100, py), (100 + image.width, py)], fill=(150, 190, 235), width=1)
        if row % (step * 2) == 0:
            draw.text((48, py - 7), '%.0f' % (origin[1] + (height - (row + r1)) * RES),
                      fill='black', font=small)
    for item in rows[:12]:
        ys, xs = np.nonzero(labels == item['id'])
        cy = int(ys.mean()) - r1
        cx = int(xs.mean())
        if 0 <= cy < crop_pixels.shape[0]:
            draw.text((100 + cx * SCALE - 12, 45 + cy * SCALE - 9), item['label'],
                      fill=(180, 40, 40) if item['label'] == 'U1' else (30, 30, 160), font=font)
    draw.text((100, 10), 'unknown regions highlighted (top %.0f%% of map); labels = connected components'
              % (VIEW_TOP * 100), fill='black', font=font)
    out = OUT / 'lab_odom_06_unknown_components.png'
    canvas.save(out)
    (OUT / 'unknown_components.json').write_text(
        json.dumps({'map': str(MAP), 'min_cells': MIN_CELLS, 'components': rows},
                   ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(rows[:12], ensure_ascii=False))


if __name__ == '__main__':
    main()
