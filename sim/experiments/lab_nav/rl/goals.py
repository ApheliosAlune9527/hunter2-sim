"""Which goals the policy trains on, and which it is judged on.

Training and evaluation goals must not be the same points, or a policy that
memorised three coordinates looks like a policy that navigates.  Both sets come
from the same generator and satisfy the same filter, so the difference between a
train and an eval goal is *where* it is, not whether it is fair.

A candidate is kept only when a straight run from the spawn to it keeps the
rotated footprint on known-free map, i.e. the same test the navigation baseline
used.  That does not prove the goal is reachable by a forward-only Ackermann
vehicle -- the vehicle may still need a turn with radius 1.669 m -- it only
removes goals buried in furniture.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'sim/experiments/lab_nav'))
import placeable_region as P  # noqa: E402

EVAL_GOALS = [
    ('short_straight', 1.885, 0.435),
    ('mid_offset', 3.185, 1.235),
    ('long_run', 4.285, 2.535),
]
TRAIN_COUNT = 40


def _corridor_free(masks, free, origin, res, wx, wy, heading):
    rows, cols = free.shape
    mask = masks[int(round(heading / 5.0)) % 72 * 5]
    steps = max(8, int(math.hypot(wx - P.SPAWN[0], wy - P.SPAWN[1]) / (res * 0.5)))
    for i in range(steps + 1):
        f = i / steps
        px = P.SPAWN[0] + (wx - P.SPAWN[0]) * f
        py = P.SPAWN[1] + (wy - P.SPAWN[1]) * f
        col = int((px - origin[0]) / res)
        row = int(rows - (py - origin[1]) / res)
        if not (0 <= row < rows and 0 <= col < cols) or not mask[row, col]:
            return False
    return True


def build(seed=0, count=TRAIN_COUNT):
    pixels, free, origin, res = P.load()
    rows, cols = pixels.shape
    masks = {}
    for heading in P.HEADINGS:
        masks[heading] = P.T.erode(free, P.T.rectangle_offsets(-0.50, 0.52, -0.395, 0.395, heading))
    any_heading = np.zeros_like(free)
    for heading, mask in masks.items():
        any_heading |= mask

    rng = np.random.default_rng(seed)
    candidates = np.argwhere(any_heading)
    keep = []
    for row, col in candidates:
        wx, wy = P.to_world(int(col), int(row), origin, res, rows)
        distance = math.hypot(wx - P.SPAWN[0], wy - P.SPAWN[1])
        if not (1.6 <= distance <= 5.5):
            continue
        bearing = math.degrees(math.atan2(wy - P.SPAWN[1], wx - P.SPAWN[0]))
        if abs(bearing) > 55.0:
            continue
        if _corridor_free(masks, free, origin, res, wx, wy, bearing):
            keep.append((round(wx, 3), round(wy, 3), round(distance, 3), round(bearing, 1)))
    if len(keep) < count:
        raise RuntimeError(f'only {len(keep)} corridor-free goals; expected >= {count}')

    order = rng.permutation(len(keep))
    train = [keep[i] for i in order[:count]]
    rest = [keep[i] for i in order[count:]]
    # Held-out goals: far from every training point so generalisation means
    # something rather than nearest-neighbour recall.
    held = []
    for item in rest:
        if all(math.hypot(item[0] - t[0], item[1] - t[1]) > 0.75 for t in train):
            held.append(item)
        if len(held) >= 12:
            break
    return {'train': train, 'held_out': held, 'pool_size': len(keep), 'seed': seed}


def main():
    out = Path(__file__).resolve().parent
    goals = build(seed=int(sys.argv[1]) if len(sys.argv) > 1 else 0)
    goals['eval'] = [{'name': n, 'x': x, 'y': y} for n, x, y in EVAL_GOALS]
    (out / 'goals.json').write_text(json.dumps(goals, indent=1), encoding='utf-8')
    print(json.dumps({'pool': goals['pool_size'], 'train': len(goals['train']),
                      'held_out': len(goals['held_out'])}))


if __name__ == '__main__':
    main()
