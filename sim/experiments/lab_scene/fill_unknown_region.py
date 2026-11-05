"""Fill a rectangular unknown pocket as free, writing a NEW map (originals untouched).

The top-centre pocket of the 2026-11-01 map is connected to the outside unknown,
so it cannot be selected as a connected component; the user supplies its bounds.
"""
import json
from pathlib import Path
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'outputs/lab_map_compare_20261105'
MAP = SRC / 'lab_odom_06_new.pgm'
YAML = SRC / 'lab_odom_06_new.yaml'
FILLED = SRC / 'lab_odom_06_filled.pgm'
FILLED_YAML = SRC / 'lab_odom_06_filled.yaml'
RES = 0.05
# Area the user marked on the top of the map.
BOX = (1.30, 4.40, 14.80, 18.50)      # x_min, x_max, y_min, y_max in map metres
VIEW = (-1.4, 5.4, 12.2, 18.6)
SCALE = 16


def load():
    pixels = np.array(Image.open(MAP).convert('L'))
    origin = [float(v) for v in re.search(r'origin:\s*\[([^\]]+)\]',
                                          YAML.read_text(encoding='utf-8')).group(1).split(',')]
    return pixels, origin


def main():
    pixels, origin = load()
    height, width = pixels.shape
    filled = pixels.copy()
    xs = np.arange(width)
    ys = np.arange(height)
    world_x = origin[0] + (xs + 0.5) * RES
    world_y = origin[1] + (height - ys - 0.5) * RES
    in_x = (world_x >= BOX[0]) & (world_x <= BOX[1])
    in_y = (world_y >= BOX[2]) & (world_y <= BOX[3])
    region = in_y[:, None] & in_x[None, :]
    changed = int(((pixels == 205) & region).sum())
    filled[(pixels == 205) & region] = 254

    Image.fromarray(filled).save(FILLED)
    FILLED_YAML.write_text(
        YAML.read_text(encoding='utf-8').replace('image: lab_odom_06_new.pgm',
                                                 'image: lab_odom_06_filled.pgm'),
        encoding='utf-8')

    # Before / after crop with a metric grid.
    xmin, xmax, ymin, ymax = VIEW
    c0 = max(0, int((xmin - origin[0]) / RES))
    c1 = min(width, int((xmax - origin[0]) / RES))
    r0 = max(0, int(height - (ymax - origin[1]) / RES))
    r1 = min(height, int(height - (ymin - origin[1]) / RES))
    panels = []
    for label, data in (('before', pixels), ('after fill', filled)):
        crop = data[r0:r1, c0:c1]
        rgb = np.zeros((*crop.shape, 3), dtype=np.uint8)
        rgb[crop == 205] = [205, 205, 205]
        rgb[crop == 254] = [250, 250, 250]
        rgb[crop == 0] = [20, 20, 20]
        image = Image.fromarray(rgb).resize(((c1 - c0) * SCALE, (r1 - r0) * SCALE),
                                            Image.Resampling.NEAREST)
        box = Image.new('RGB', (image.width + 110, image.height + 60), 'white')
        box.paste(image, (85, 40))
        draw = ImageDraw.Draw(box)
        font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
        small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 13)
        draw.text((85, 10), '%s  (grid 1 m)' % label, fill='black', font=font)
        step = int(round(1.0 / RES))
        for col in range(c0 - c0 % step, c1, step):
            px = 85 + (col - c0) * SCALE
            draw.line([(px, 40), (px, 40 + image.height)], fill=(160, 200, 240), width=1)
            draw.text((px - 11, box.height - 20), '%.0f' % (origin[0] + col * RES),
                      fill='black', font=small)
        for row in range(r0 - r0 % step, r1, step):
            py = 40 + (row - r0) * SCALE
            draw.line([(85, py), (85 + image.width, py)], fill=(160, 200, 240), width=1)
            draw.text((40, py - 6), '%.0f' % (origin[1] + (height - row) * RES),
                      fill='black', font=small)
        # Outline the filled rectangle.
        bx0 = 85 + (int((BOX[0] - origin[0]) / RES) - c0) * SCALE
        bx1 = 85 + (int((BOX[1] - origin[0]) / RES) - c0) * SCALE
        by0 = 40 + (int(height - (BOX[3] - origin[1]) / RES) - r0) * SCALE
        by1 = 40 + (int(height - (BOX[2] - origin[1]) / RES) - r0) * SCALE
        draw.rectangle([bx0, by0, bx1, by1], outline=(220, 60, 60), width=3)
        panels.append(box)

    canvas = Image.new('RGB', (panels[0].width + panels[1].width + 20,
                              max(p.height for p in panels) + 40), 'white')
    canvas.paste(panels[0], (0, 40))
    canvas.paste(panels[1], (panels[0].width + 20, 40))
    ImageDraw.Draw(canvas).text(
        (10, 10),
        'fill unknown -> free inside x[%.1f,%.1f] y[%.1f,%.1f]: %d cells changed'
        % (BOX[0], BOX[1], BOX[2], BOX[3], changed), fill='black',
        font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18))
    out = SRC / 'lab_odom_06_fill_preview.png'
    canvas.save(out)

    (SRC / 'fill_receipt.json').write_text(json.dumps({
        'source_map': str(MAP), 'filled_map': str(FILLED),
        'box_m': BOX, 'cells_changed_unknown_to_free': changed,
        'note': ('Manual free-space annotation requested by the user for the top pocket; '
                 'the original map is unchanged. Only unknown cells inside the box changed.'),
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'cells_changed': changed, 'preview': str(out)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
