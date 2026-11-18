#!/usr/bin/env python3
"""Step-5 scene: two blue boxes sized so the FARTHER one looks BIGGER.

Selection rule under test: a plain area rule picks the box with the larger blue
blob, which on this scene is the farther box, while the depth query says it is
farther.  The pair therefore separates "looks big" from "is far" instead of the
step-3 scene where both cues agreed.

Camera, red sign and world source are the frozen step-3 ones.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import prepare_step3_scene as base

ROOT = Path("/mnt/d/rob-memory")
DST_WORLD = base.DST_DIR / "scenes/lab_agentvln_bigfar.sdf"
LAYOUT = base.DST_DIR / "config/target_layout_step5.json"

# name, x, y, size x, size y, size z, centre z
# Geometry chosen by an offline search over the four constraints (area
# inversion, both boxes fully in frame with a gap, straight final approach, and
# footprint clearance from the near box).  The v1 layout put the near box 0.80 m
# from the far dock and RPP refused to drive ("collision ahead"); here the near
# box sits south of the approach line and the dock has 0.68 m clearance.
BOXES = [
    ("blue_near", 4.20, 0.80, 0.25, 0.25, 0.70, 0.35),
    ("blue_far",  4.20, 2.50, 0.90, 0.90, 1.50, 0.75),
]
# Control scene: the two boxes exchange places, so the big box becomes the near
# one and the small box the far one.  The area proxy then happens to agree with
# depth; it is the check that the area rule follows appearance, not distance.
BOXES_SWAP = [
    ("blue_near", 4.20, 0.80, 0.90, 0.90, 1.50, 0.75),
    ("blue_far",  4.20, 2.50, 0.25, 0.25, 0.70, 0.35),
]
# On the spawn->observation ray (t = 2.0 m), so the first leg is a straight line.
OBS = (1.52, 0.23, 0.522)
FRONT_LENGTH = 0.834
DOCK_BACKOFF = 0.10


def box_xml(name, x, y, sx, sy, sz, zc):
    return f"""<model name="{name}" static="true">
  <static>true</static>
  <pose>{x} {y} {zc} 0 0 0</pose>
  <link name="link">
    <visual name="visual">
      <cast_shadows>false</cast_shadows>
      <geometry><box><size>{sx} {sy} {sz}</size></box></geometry>
      {base.material((0.03, 0.08, 0.95), 0.30)}
    </visual>
  </link>
</model>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--swap', action='store_true')
    args = ap.parse_args()
    global BOXES, DST_WORLD, LAYOUT
    if args.swap:
        BOXES = BOXES_SWAP
        DST_WORLD = base.DST_DIR / "scenes/lab_agentvln_bigfar_swap.sdf"
        LAYOUT = base.DST_DIR / "config/target_layout_step5_swap.json"
    s = base.SRC_WORLD.read_text()
    if "agentvln_camera" in s:
        raise SystemExit("camera already present; refusing to duplicate")
    old = "</lidar></sensor></link>"
    if s.count(old) != 1:
        raise SystemExit("expected one scan closing sequence")
    s = s.replace(old, "</lidar></sensor>" + base.CAMERA + "</link>")
    props = "\n".join([base.red_sign()] + [box_xml(*b) for b in BOXES])
    s = s.replace("</world>", props + "\n</world>")
    DST_WORLD.write_text(s)

    def dock_for(box):
        face = (box[1] - box[3] / 2, box[2] - box[4] / 2)
        approach = math.atan2(face[1] - OBS[1], face[0] - OBS[0])
        x = face[0] - (FRONT_LENGTH + DOCK_BACKOFF) * math.cos(approach)
        y = face[1] - (FRONT_LENGTH + DOCK_BACKOFF) * math.sin(approach)
        return face, x, y

    far = [b for b in BOXES if b[0] == "blue_far"][0]
    near = [b for b in BOXES if b[0] == "blue_near"][0]
    face, dock_x, dock_y = dock_for(far)
    _nface, near_x, near_y = dock_for(near)
    layout = {
        "frame": "map",
        "world": str(DST_WORLD),
        "red_sign": {"x": base.RED[0], "y": base.RED[1], "z": base.SIGN_Z,
                     "size": list(base.SIGN_SIZE), "bottom_z": round(base.SIGN_Z - base.SIGN_SIZE[2] / 2, 3),
                     "lidar_plane_z": 0.785},
        "blue_boxes": [{"name": n, "x": x, "y": y, "z": zc, "size": [sx, sy, sz]}
                       for n, x, y, sx, sy, sz, zc in BOXES],
        "observation_pose": {"x": OBS[0], "y": OBS[1], "yaw": OBS[2]},
        "observation_route": [{"x": OBS[0], "y": OBS[1], "yaw": OBS[2]}],
        "expected_dock": {"x": round(dock_x, 3), "y": round(dock_y, 3),
                          "yaw": round(math.atan2(far[2] - dock_y, far[1] - dock_x), 3)},
        "parking_zone": {"x": round(dock_x, 3), "y": round(dock_y, 3), "radius_m": 0.30,
                         "yaw": round(math.atan2(far[2] - dock_y, far[1] - dock_x), 3),
                         "yaw_tol_rad": 0.50},
        # The "near" instruction needs its own zone, otherwise a correct stop in
        # front of the near box would be scored against the far box's zone.
        "expected_dock_near": {"x": round(near_x, 3), "y": round(near_y, 3),
                               "yaw": round(math.atan2(near[2] - near_y, near[1] - near_x), 3)},
        "parking_zone_near": {"x": round(near_x, 3), "y": round(near_y, 3), "radius_m": 0.30,
                              "yaw": round(math.atan2(near[2] - near_y, near[1] - near_x), 3),
                              "yaw_tol_rad": 0.50},
        "instruction": "经过红牌，停在较远的那个蓝箱前方",
        "instruction_near": "经过红牌，停在较近的那个蓝箱前方",
        "target_box": "blue_far",
    }
    LAYOUT.write_text(json.dumps(layout, indent=2) + "\n")
    print(DST_WORLD, "sha256", hashlib.sha256(DST_WORLD.read_bytes()).hexdigest(),
          "bytes", DST_WORLD.stat().st_size)
    print(LAYOUT, "sha256", hashlib.sha256(LAYOUT.read_bytes()).hexdigest())
    print(json.dumps(layout["blue_boxes"], ensure_ascii=False))


if __name__ == "__main__":
    main()
