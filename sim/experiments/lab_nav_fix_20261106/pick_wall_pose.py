"""Pick a pose for a deliberate wall contact, using the map rather than a guess.

Earlier the wall pose was guessed from a wall list and put the vehicle inside a wall,
which looked exactly like a broken drive plugin.  Here the pose is derived: free cell,
at least 1.2 m of free space behind it, an occupied cell 0.6-1.2 m ahead along +x, and
a heading of 0 (facing +x).
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path('/mnt/d/rob-memory')
MAP_YAML = ROOT / 'outputs/lab_nav_20261105/lab_nav_map.yaml'
OUT = ROOT / 'outputs/lab_nav_fix_20261106'


def load():
    meta = {}
    for line in MAP_YAML.read_text().splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            meta[k.strip()] = v.strip()
    res = float(meta['resolution'])
    ox, oy, _ = [float(x) for x in meta['origin'].strip('[]').split(',')]
    img = np.array(Image.open(MAP_YAML.parent / meta['image']))
    return img, res, ox, oy


def main():
    img, res, ox, oy = load()
    rows, cols = img.shape
    free = img == 254
    occupied = img == 0
    behind_cells = int(round(1.2 / res))
    best = None
    for row in range(int(3.0 / res), rows - int(3.0 / res)):
        for col in range(behind_cells + 2, cols - int(1.5 / res)):
            if not free[row, col] or not free[row, col - 1] or not free[row, col - 2]:
                continue
            if not all(free[row, col - k] for k in range(1, behind_cells + 1)):
                continue
            ahead = None
            for k in range(1, int(1.5 / res)):
                if col + k >= cols:
                    break
                if occupied[row, col + k]:
                    ahead = k * res
                    break
            if ahead is None or not (0.6 <= ahead <= 1.2):
                continue
            x = ox + (col + 0.5) * res
            y = oy + (rows - row - 0.5) * res
            # prefer the middle of the room, away from map edges
            score = abs(x - 1.0) + abs(y - 3.0)
            if best is None or score < best[0]:
                best = (score, x, y, ahead, row, col)
    if best is None:
        raise SystemExit('no wall approach found')
    _, x, y, ahead, row, col = best
    doc = {'pose': {'x': round(x, 3), 'y': round(y, 3), 'yaw': 0.0, 'z': 0.165},
           'free_m_ahead': round(ahead, 3),
           'cells': {'row': row, 'col': col},
           'note': 'nose is 0.854 m ahead of the rear axle, so the bumper reaches the '
                   'wall after (free_ahead - 0.854) metres of travel'}
    (OUT / 'wall_contact_pose.json').write_text(json.dumps(doc, indent=1), encoding='utf-8')
    print(json.dumps(doc))


if __name__ == '__main__':
    main()
