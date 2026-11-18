#!/usr/bin/env python3
"""Build the step-3 scene: camera, a red sign and two blue boxes."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path("/mnt/d/rob-memory")
SRC_WORLD = ROOT / "outputs/lab_nav_20261105/lab_nav_world_drive.sdf"
DST_DIR = ROOT / "sim/experiments/agentvln_hunter"
DST_WORLD = DST_DIR / "scenes/lab_agentvln_targets.sdf"
LAYOUT = DST_DIR / "config/target_layout.json"

CAMERA = """<sensor name="agentvln_camera" type="rgbd_camera">
  <pose>0.644 0.015 0.475 0 0 0</pose>
  <always_on>true</always_on>
  <update_rate>5</update_rate>
  <visualize>false</visualize>
  <topic>/hz_sim/agentvln/camera</topic>
  <ignition_frame_id>agentvln_camera_optical_frame</ignition_frame_id>
  <camera>
    <horizontal_fov>0.9706402426459841</horizontal_fov>
    <image><width>640</width><height>480</height><format>R8G8B8</format></image>
    <clip><near>0.1</near><far>20</far></clip>
  </camera>
</sensor>"""

# The sign hangs above the 2-D lidar plane (world z = 0.165 + 0.62 = 0.785 m) so it
# stays a camera landmark without ever entering the Nav2 costmap.  A ground-mounted
# post at the old pose (1.45, -0.35) crossed the scan plane and made the planner
# report "no valid path found" on the re-observe route.
RED = (2.10, -0.35)
SIGN_Z = 1.05
SIGN_SIZE = (0.05, 0.55, 0.30)
# blue_near originally stood at (4.70, 1.15), directly between the observation
# pose and the far box.  Every straight-in docking ray to the far box then put
# the vehicle footprint on top of that box (pipeline_v7 rejected all 25
# candidates), and the only alternative - a dock north of it - needs a 0.5 rad
# turn in the last 0.6 m, which the 1.669 m Dubin radius cannot do.  Moved to
# (4.10, 2.60) it still reads as the nearer of the two boxes (1.98 m vs 2.92 m
# from the observation pose) and leaves the docking ray 0.92 m clear.
BOXES = [("blue_near", 4.10, 2.60), ("blue_far", 5.50, 2.05)]
# Observation pose.  Two constraints, both measured on this scene:
#   * view: both boxes fully inside the frame and separated (here a 48 px gap,
#     near box 1.78 m away); (3.185, 1.235) was 1.3 m from the near box, which
#     filled the frame and hid the far one (pipeline_v3 saw one component);
#   * plan shape: the goal yaw must equal the bearing from the current pose,
#     otherwise Smac has to plan an S-curve with the 1.669 m turning radius and
#     lose the path after a few centimetres (pipeline_v4 stalled at 0.3 m).
# atan2(0.5 + 0.77, 2.0 + 0.21) = 0.522 rad, so spawn -> here is a plain arc.
OBS = (2.0, 0.5, 0.522)
OBS_ROUTE = [OBS]
# Expected docking pose of the straight-in procedure: the vehicle stops
# DOCK_BACKOFF short of the target box's front face, on the line from the
# observation pose to that face.  Nav2 replans every second while following, so
# any dock that is not on that line asks for a turn in the last metre, which the
# 1.669 m Dubin radius cannot deliver (pipeline_v5/v6 both stalled ~0.6 m out).
FRONT_LENGTH = 0.834
DOCK_BACKOFF = 0.10
# The depth query lands on the visible silhouette centroid, which for a box seen
# from the south-west sits on its near corner, not on the face centre (measured
# 1.92 m against a face centre of 2.05 m).  The expected dock is therefore built
# from the same feature in ground truth: the box's front-south corner.
_FAR_X, _FAR_Y = [b[1:] for b in BOXES if b[0] == "blue_far"][0]
_FACE = (_FAR_X - 0.175, _FAR_Y - 0.175)
_APPROACH = math.atan2(_FACE[1] - OBS[1], _FACE[0] - OBS[0])
_DOCK_X = _FACE[0] - (FRONT_LENGTH + DOCK_BACKOFF) * math.cos(_APPROACH)
_DOCK_Y = _FACE[1] - (FRONT_LENGTH + DOCK_BACKOFF) * math.sin(_APPROACH)
DOCK = (round(_DOCK_X, 3), round(_DOCK_Y, 3),
        round(math.atan2(_FAR_Y - _DOCK_Y, _FAR_X - _DOCK_X), 3))

def material(rgb, emissive=0.25):
    r, g, b = rgb
    return f"""<material>
  <ambient>{r*0.45:.3f} {g*0.45:.3f} {b*0.45:.3f} 1</ambient>
  <diffuse>{r:.3f} {g:.3f} {b:.3f} 1</diffuse>
  <emissive>{r*emissive:.3f} {g*emissive:.3f} {b*emissive:.3f} 1</emissive>
</material>"""

def red_sign():
    x, y = RED
    sx, sy, sz = SIGN_SIZE
    return f"""<model name="red_sign" static="true">
  <static>true</static>
  <pose>{x} {y} 0 0 0 0</pose>
  <link name="link">
    <visual name="panel">
      <cast_shadows>false</cast_shadows>
      <pose>0 0 {SIGN_Z} 0 0 0</pose>
      <geometry><box><size>{sx} {sy} {sz}</size></box></geometry>
      {material((0.95, 0.03, 0.03), 0.35)}
    </visual>
  </link>
</model>"""

def blue_box(name, x, y):
    return f"""<model name="{name}" static="true">
  <static>true</static>
  <pose>{x} {y} 0.45 0 0 0</pose>
  <link name="link">
    <visual name="visual">
      <cast_shadows>false</cast_shadows>
      <geometry><box><size>0.35 0.35 0.90</size></box></geometry>
      {material((0.03, 0.08, 0.95), 0.30)}
    </visual>
  </link>
</model>"""

def main():
    DST_WORLD.parent.mkdir(parents=True, exist_ok=True)
    s = SRC_WORLD.read_text()
    if "agentvln_camera" in s:
        raise SystemExit("camera already present; refusing to duplicate")
    old = "</lidar></sensor></link>"
    if s.count(old) != 1:
        raise SystemExit(f"expected one scan closing sequence, found {s.count(old)}")
    s = s.replace(old, "</lidar></sensor>" + CAMERA + "</link>")
    props = "\n".join([red_sign()] + [blue_box(n, x, y) for n, x, y in BOXES])
    if "</world>" not in s:
        raise SystemExit("no </world>")
    s = s.replace("</world>", props + "\n</world>")
    DST_WORLD.write_text(s)
    layout = {
        "frame": "map",
        "world": str(DST_WORLD),
        "red_sign": {
            "x": RED[0], "y": RED[1], "z": SIGN_Z, "size": list(SIGN_SIZE),
            "bottom_z": round(SIGN_Z - SIGN_SIZE[2] / 2, 3),
            "lidar_plane_z": 0.785,
        },
        "blue_boxes": [
            {"name": n, "x": x, "y": y, "z": 0.45, "size": [0.35, 0.35, 0.90]} for n, x, y in BOXES
        ],
        "observation_pose": {"x": OBS[0], "y": OBS[1], "yaw": OBS[2]},
        "observation_route": [{"x": x, "y": y, "yaw": yaw} for x, y, yaw in OBS_ROUTE],
        "expected_dock": {"x": DOCK[0], "y": DOCK[1], "yaw": DOCK[2]},
        "parking_zone": {"x": DOCK[0], "y": DOCK[1], "radius_m": 0.30, "yaw": DOCK[2], "yaw_tol_rad": 0.50},
        "instruction": "经过红牌，在两个蓝箱中较远的那个前方停下",
        "target_box": "blue_far",
    }
    LAYOUT.write_text(json.dumps(layout, indent=2) + "\n")
    h = hashlib.sha256(DST_WORLD.read_bytes()).hexdigest()
    print(DST_WORLD, "sha256", h, "bytes", DST_WORLD.stat().st_size)
    print(LAYOUT, "sha256", hashlib.sha256(LAYOUT.read_bytes()).hexdigest())
    print(json.dumps(layout, indent=2))

if __name__ == "__main__":
    main()
