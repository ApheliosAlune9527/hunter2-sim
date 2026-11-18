#!/usr/bin/env python3
"""Draw the goals and the truth tracks of a run set on top of the map.

Kept next to the evaluator because the two have to agree on the map geometry: the map's
row 0 is the highest y, so the row used for drawing is (rows - 1 - row).  Getting that
wrong mirrors every track vertically, which is exactly the bug this file was written
after finding.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'outputs' / 'lab_nav_fix_20261106'
MAP = ROOT / 'outputs' / 'lab_nav_20261105' / 'lab_nav_map.pgm'
COLORS = [(214, 39, 40), (31, 119, 180), (44, 160, 44)]


def load_meta():
    y = (ROOT / 'outputs' / 'lab_nav_20261105' / 'lab_nav_map.yaml').read_text()
    res = float([l for l in y.splitlines() if l.startswith('resolution')][0].split(':')[1])
    origin = [float(v) for v in
              [l for l in y.splitlines() if l.startswith('origin')][0]
              .split('[')[1].split(']')[0].split(',')]
    return res, origin


def main(tag):
    runs_doc = json.loads((OUT / ('nav_eval_runs_%s.json' % tag)).read_text())
    img = Image.open(MAP).convert('RGB')
    scale = 3
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    res, origin = load_meta()
    rows = img.height // scale
    draw = ImageDraw.Draw(img)

    def w2p(x, y):
        col = (x - origin[0]) / res
        row = (y - origin[1]) / res
        return col * scale, (rows - 1 - row) * scale

    goals = runs_doc['goals']
    for i, (name, gx, gy, gyaw) in enumerate(goals):
        colour = COLORS[i % len(COLORS)]
        for run in runs_doc['runs']:
            if run['goal'] != name:
                continue
            pts = [w2p(p[1], p[2]) for p in run.get('track', [])]
            ok = run['success']
            if len(pts) > 1:
                draw.line(pts, fill=colour if ok else tuple(min(255, c + 60) for c in colour),
                          width=3 if ok else 2)
        gx_px, gy_px = w2p(gx, gy)
        draw.ellipse([gx_px - 7, gy_px - 7, gx_px + 7, gy_px + 7], outline=colour, width=3)
        draw.text((gx_px + 9, gy_px - 6), '%s %d/%d' % (
            name, sum(1 for r in runs_doc['runs'] if r['goal'] == name and r['success']),
            sum(1 for r in runs_doc['runs'] if r['goal'] == name)), fill=colour)

    sx, sy = w2p(-0.21, -0.77)
    draw.ellipse([sx - 6, sy - 6, sx + 6, sy + 6], fill=(0, 0, 0))
    draw.text((sx + 9, sy + 2), 'spawn', fill=(0, 0, 0))

    draw.text((8, 8), '%s localisation - truth tracks, %d/%d succeeded' % (
        runs_doc.get('localizer', 'truth'),
        sum(1 for r in runs_doc['runs'] if r['success']), len(runs_doc['runs'])),
        fill=(0, 0, 0))

    path = OUT / ('nav_eval_tracks_%s.png' % tag)
    img.save(path)
    print(path)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'truth3')
