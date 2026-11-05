"""Render the filled occupancy map with a labelled 1 m grid, for manual region picking."""
from pathlib import Path
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'outputs/lab_map_compare_20261105'
MAP = SRC / 'lab_odom_06_filled.pgm'
YAML = SRC / 'lab_odom_06_filled.yaml'
SCALE = 6
RES = 0.05


def main():
    pixels = np.array(Image.open(MAP).convert('L'))
    origin = [float(v) for v in re.search(r'origin:\s*\[([^\]]+)\]',
                                          YAML.read_text(encoding='utf-8')).group(1).split(',')]
    height, width = pixels.shape
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    rgb[pixels == 205] = [212, 212, 212]
    rgb[pixels == 254] = [250, 250, 250]
    rgb[pixels == 0] = [15, 15, 15]
    image = Image.fromarray(rgb).resize((width * SCALE, height * SCALE), Image.Resampling.NEAREST)
    canvas = Image.new('RGB', (image.width + 130, image.height + 80), 'white')
    canvas.paste(image, (100, 50))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 16)
    big = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 20)
    step = int(round(1.0 / RES))
    for col in range(0, width, step):
        px = 100 + col * SCALE
        draw.line([(px, 50), (px, 50 + image.height)], fill=(130, 175, 235), width=1 if col % (step * 5) else 2)
        draw.text((px - 12, canvas.height - 26), '%.0f' % (origin[0] + col * RES),
                  fill='black', font=font)
    for row in range(0, height, step):
        py = 50 + row * SCALE
        draw.line([(100, py), (100 + image.width, py)], fill=(130, 175, 235), width=1 if row % (step * 5) else 2)
        draw.text((46, py - 8), '%.0f' % (origin[1] + (height - row) * RES),
                  fill='black', font=font)
    draw.text((100, 12), 'lab_odom_06_filled - 1 m grid in map coordinates (x right, y up)',
              fill='black', font=big)
    out = SRC / 'lab_odom_06_filled_grid.png'
    canvas.save(out)
    print(out)


if __name__ == '__main__':
    main()
