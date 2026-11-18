#!/usr/bin/env python3
"""Build variant B of the task scene: the target box moves.

Variant A has the far box at (5.50, 2.05); variant B moves it to (4.90, 1.90)
while the near box stays at (4.10, 2.60).  The instruction is unchanged, so the
agent has to pick the other box and the docking zone moves with it.  Merely
exchanging the two boxes' names was rejected: the observation pose is always
closer to (4.10, 2.60) (2.35 m against 3.19 m), so the image and the answer would
not change, and inverting the depth order would need a box inside the docking
footprint.

Outputs go to *_b files so the frozen step-3 scene is untouched.
"""
import math

import prepare_step3_scene as base

base.BOXES = [("blue_near", 4.10, 2.60), ("blue_far", 4.90, 1.90)]
base.DST_WORLD = base.DST_DIR / "scenes/lab_agentvln_targets_b.sdf"
base.LAYOUT = base.DST_DIR / "config/target_layout_b.json"

# DOCK and its derived fields were computed at import time from the original
# box order, so they have to be rebuilt for the exchanged arrangement.
_far_x, _far_y = [b[1:] for b in base.BOXES if b[0] == "blue_far"][0]
_face = (_far_x - 0.175, _far_y - 0.175)
_approach = math.atan2(_face[1] - base.OBS[1], _face[0] - base.OBS[0])
_dock_x = _face[0] - (base.FRONT_LENGTH + base.DOCK_BACKOFF) * math.cos(_approach)
_dock_y = _face[1] - (base.FRONT_LENGTH + base.DOCK_BACKOFF) * math.sin(_approach)
base.DOCK = (round(_dock_x, 3), round(_dock_y, 3),
             round(math.atan2(_far_y - _dock_y, _far_x - _dock_x), 3))

if __name__ == "__main__":
    base.main()
