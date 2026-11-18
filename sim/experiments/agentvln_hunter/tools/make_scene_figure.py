#!/usr/bin/env python3
"""Top-down task figure: frozen map, props, spawn, observation pose, dock zone."""
import json
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw

ROOT = Path('/mnt/d/rob-memory')
MAP = ROOT / 'sim/experiments/agentvln_hunter/config/straight_nav_map/lab_nav_map_fix.yaml'
LAYOUT = ROOT / 'sim/experiments/agentvln_hunter/config/target_layout_straight.json'
OUT = ROOT / 'outputs/agentvln_hunter_20261109_slides'
SCALE = 110
PAD_X = (1.0, 1.1)
PAD_Y = (0.9, 0.7)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = yaml.safe_load(MAP.read_text())
    img = np.array(Image.open(MAP.parent / meta['image']).convert('L'))
    h, w = img.shape
    res = meta['resolution']
    ox, oy = meta['origin'][0], meta['origin'][1]
    layout = json.loads(LAYOUT.read_text())
    obs = layout['observation_pose']
    dock = layout['expected_dock']
    zone = layout['parking_zone']
    boxes = layout['blue_boxes']
    sign = layout['red_sign']
    spawn = (-0.21, -0.77, 0.0)

    xs = [b['x'] for b in boxes] + [obs['x'], dock['x'], spawn[0]]
    ys = [b['y'] for b in boxes] + [obs['y'], dock['y'], spawn[1]]
    x0, x1 = min(xs) - PAD_X[0], max(xs) + PAD_X[1]
    y0, y1 = min(ys) - PAD_Y[0], max(ys) + PAD_Y[1]
    W, H = int((x1 - x0) * SCALE), int((y1 - y0) * SCALE)

    def to_px(x, y):
        return (x - x0) * SCALE, (y1 - y) * SCALE

    canvas = Image.new('RGB', (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    for r in range(h):
        row = img[r]
        nz = np.flatnonzero(row < 250)
        for c in nz:
            x = ox + (c + 0.5) * res
            y = oy + (h - 1 - r + 0.5) * res
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                continue
            px, py = to_px(x, y)
            draw.rectangle([px - SCALE * res / 2, py - SCALE * res / 2,
                            px + SCALE * res / 2, py + SCALE * res / 2], fill=(120, 120, 120))

    for b in boxes:
        sx, sy = b['size'][0], b['size'][1]
        draw.rectangle([to_px(b['x'] - sx / 2, b['y'] + sy / 2),
                        to_px(b['x'] + sx / 2, b['y'] - sy / 2)], fill=(20, 40, 200))
    draw.rectangle([to_px(sign['x'] - sign['size'][0] / 2, sign['y'] + sign['size'][1] / 2),
                    to_px(sign['x'] + sign['size'][0] / 2, sign['y'] - sign['size'][1] / 2)],
                   fill=(200, 30, 30))
    cx, cy = to_px(zone['x'], zone['y'])
    r = zone['radius_m'] * SCALE
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 150, 90), width=3)
    draw.line([to_px(spawn[0], spawn[1]), to_px(obs['x'], obs['y'])], fill=(0, 130, 0), width=3)
    draw.line([to_px(obs['x'], obs['y']), to_px(dock['x'], dock['y'])], fill=(140, 0, 160), width=3)

    def arrow(x, y, yaw, colour, length=0.5):
        px, py = to_px(x, y)
        qx, qy = to_px(x + length * np.cos(yaw), y + length * np.sin(yaw))
        draw.line([px, py, qx, qy], fill=colour, width=4)
        ang = np.arctan2(-(qy - py), qx - px)
        for da in (2.6, -2.6):
            draw.line([qx, qy, qx + 0.16 * SCALE * np.cos(ang + da),
                       qy + 0.16 * SCALE * np.sin(ang + da)], fill=colour, width=4)
        draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=colour)

    arrow(*spawn, colour=(0, 130, 0))
    arrow(obs['x'], obs['y'], obs['yaw'], (140, 0, 160))
    arrow(dock['x'], dock['y'], dock['yaw'], (0, 150, 90))

    def label(x, y, text, colour, dx=10, dy=-30):
        px, py = to_px(x, y)
        draw.text((px + dx, py + dy), text, fill=colour)

    label(spawn[0], spawn[1], 'spawn', (0, 130, 0), 12, 8)
    label(obs['x'], obs['y'], 'observation', (140, 0, 160), 8, 14)
    label(dock['x'], dock['y'], 'dock + parking zone', (0, 150, 90), 10, -40)
    label(boxes[0]['x'], boxes[0]['y'], 'near box', (20, 40, 200), -70, -12)
    label(boxes[1]['x'], boxes[1]['y'], 'far box (target)', (20, 40, 200), -110, -14)

    # legend
    lx, ly = 12, 12
    rows = [((20, 40, 200), 'blue boxes'), ((200, 30, 30), 'red sign'),
            ((120, 120, 120), 'walls (2-D map)'), ((0, 150, 90), 'dock + 0.30 m zone')]
    draw.rectangle([lx - 6, ly - 6, lx + 186, ly + 16 * len(rows) + 6], outline=(180, 180, 180))
    for i, (colour, text) in enumerate(rows):
        yy = ly + 16 * i
        draw.rectangle([lx, yy + 3, lx + 10, yy + 11], fill=colour)
        draw.text((lx + 16, yy), text, fill=(0, 0, 0))
    # scale bar
    bx, by = 14, H - 22
    draw.line([bx, by, bx + SCALE, by], fill=(0, 0, 0), width=3)
    draw.line([bx, by - 4, bx, by + 4], fill=(0, 0, 0), width=2)
    draw.line([bx + SCALE, by - 4, bx + SCALE, by + 4], fill=(0, 0, 0), width=2)
    draw.text((bx + SCALE + 6, by - 7), '1 m', fill=(0, 0, 0))
    out = OUT / 'scene_topdown.png'
    canvas.save(out)
    print(out, canvas.size)


if __name__ == '__main__':
    main()
