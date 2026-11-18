#!/usr/bin/env python3
"""Draw the task-4 evaluation summary: goal map, tracks, and a results table.

Reads what run_nav_eval.py wrote (nav_eval_runs.json + the raw tracks staging
file) and produces two PNGs next to them:

  nav_eval_goals.png    map + spawn + every candidate/goal, labelled with the
                        measured result per goal
  nav_eval_tracks.png   truth trajectory of every successful round, overlaid

No ROS involved: this only reads JSON and the map PGM.
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

WS = Path(__file__).resolve().parents[3]
OUT = WS / 'outputs' / 'lab_nav_20261105'
MAP = OUT / 'lab_nav_map.pgm'

COLORS = [(20, 90, 200), (0, 140, 90), (200, 110, 0), (150, 40, 150), (0, 0, 0)]


def load_map():
    img = np.array(Image.open(MAP).convert('L'))
    yaml = {}
    for line in (OUT / 'lab_nav_map.yaml').read_text().splitlines():
        if ':' in line and not line.strip().startswith('#'):
            k, v = line.split(':', 1)
            yaml[k.strip()] = v.strip()
    res = float(yaml['resolution'])
    origin = [float(s) for s in yaml['origin'].strip('[]').split(',')]
    return img, res, origin


def w2p(x, y, rows, res, origin):
    """Map metres to pixels of the *resampled* canvas.

    rows must be the pixel height of the canvas the line is drawn on, not the
    height of the source grid: passing the source height while res is already
    scaled puts every mark half a canvas too high, which mirrors the whole
    picture about its middle.  That is exactly what happened in the first
    version of these figures.
    """
    return ((x - origin[0]) / res, rows - (y - origin[1]) / res)


def base_map(img, res):
    # free=255 -> near white, occupied -> black, unknown -> mid grey
    rgb = np.zeros(img.shape + (3,), dtype=np.uint8)
    rgb[:] = (235, 235, 235)
    rgb[img >= 250] = (255, 255, 255)
    rgb[img <= 10] = (40, 40, 40)
    rgb[(img > 10) & (img < 250)] = (196, 196, 196)
    pil = Image.fromarray(rgb)
    pil = pil.resize((pil.width * 2, pil.height * 2), Image.NEAREST)
    res *= 0.5
    return pil, res


def main():
    import sys
    tag = sys.argv[1] if len(sys.argv) > 1 else ''
    suffix = f'_{tag}' if tag else ''
    runs_doc = json.loads((OUT / f'nav_eval_runs{suffix}.json').read_text())
    runs = runs_doc['runs']
    tracks = json.loads((OUT / f'nav_eval_tracks{suffix}.json').read_text())
    for r in runs:
        r['track'] = [p for p in tracks.get(f"{r['goal']}_{r['round']}", [])]
    img, res, origin = load_map()
    pil, res2 = base_map(img, res)
    rows2 = pil.height
    d = ImageDraw.Draw(pil)
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18)
    except Exception:
        font = ImageFont.load_default()

    spawn = runs_doc.get('spawn', {}) or {}
    sx, sy = spawn.get('x', -0.21), spawn.get('y', -0.77)
    px, py = w2p(sx, sy, rows2, res2, origin)
    d.ellipse([px - 7, py - 7, px + 7, py + 7], outline=(0, 0, 0), width=3)
    d.text((px + 10, py - 8), 'spawn', fill=(0, 0, 0), font=font)

    goals = {}
    for r in runs:
        goals.setdefault(r['goal'], []).append(r)
    for i, (name, rs) in enumerate(goals.items()):
        g = rs[0]['target']
        col = COLORS[i % len(COLORS)]
        gx, gy = w2p(g[0], g[1], rows2, res2, origin)
        ok = sum(1 for r in rs if r['success'])
        d.ellipse([gx - 9, gy - 9, gx + 9, gy + 9], outline=col, width=4)
        d.text((gx + 12, gy - 26), f'{name} {ok}/{len(rs)}', fill=col, font=font)

    for r in runs:
        if not r['success']:
            continue
        col = COLORS[list(goals).index(r['goal']) % len(COLORS)]
        pts = [w2p(p['x'], p['y'], rows2, res2, origin) for p in r['track']]
        if len(pts) > 1:
            d.line(pts, fill=col, width=2, joint='curve')

    loc = runs_doc.get('localisation', 'truth')
    title = (f"task 4 goals and truth tracks - {loc} localisation - "
             f"{sum(1 for r in runs if r['success'])}/{len(runs)} successful")
    out = Image.new('RGB', (pil.width, pil.height + 34), (255, 255, 255))
    out.paste(pil, (0, 34))
    ImageDraw.Draw(out).text((12, 8), title, fill=(0, 0, 0), font=font)
    path = OUT / f'nav_eval_tracks{suffix}.png'
    out.save(path)

    # same picture without tracks, for the goal-set figure
    pil2, res3 = base_map(img, res)
    d2 = ImageDraw.Draw(pil2)
    px, py = w2p(sx, sy, pil2.height, res3, origin)
    d2.ellipse([px - 7, py - 7, px + 7, py + 7], outline=(0, 0, 0), width=3)
    d2.text((px + 10, py - 8), 'spawn', fill=(0, 0, 0), font=font)
    for i, (name, rs) in enumerate(goals.items()):
        g = rs[0]['target']
        col = COLORS[i % len(COLORS)]
        gx, gy = w2p(g[0], g[1], pil2.height, res3, origin)
        ok = sum(1 for r in rs if r['success'])
        errs = [r['final_error_m'] for r in rs if r['final_error_m'] is not None]
        label = f'{name}  {ok}/{len(rs)}' + (f'  err {np.mean(errs):.2f} m' if errs else '')
        d2.ellipse([gx - 9, gy - 9, gx + 9, gy + 9], outline=col, width=4)
        d2.text((gx + 12, gy - 26), label, fill=col, font=font)
    out2 = Image.new('RGB', (pil2.width, pil2.height + 34), (255, 255, 255))
    out2.paste(pil2, (0, 34))
    ImageDraw.Draw(out2).text((12, 8), 'task 4 goal set', fill=(0, 0, 0), font=font)
    out2.save(OUT / f'nav_eval_goals{suffix}.png')

    print(json.dumps({'tracks': str(path), 'goals': str(OUT / f'nav_eval_goals{suffix}.png')}))


if __name__ == '__main__':
    main()

