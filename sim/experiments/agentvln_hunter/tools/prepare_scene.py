#!/usr/bin/env python3
"""Build the AgentVLN lab scene copy: RGB-D camera + three colour markers.

The source world is the validated 2-D lab map with the HUNTER model inlined.  This
script only adds an rgbd_camera sensor inside base_link and three static visual
markers at known world poses; it does not move the vehicle, the map or Nav2.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path("/mnt/d/rob-memory")
SRC_WORLD = ROOT / "outputs/lab_nav_20261105/lab_nav_world_drive.sdf"
SRC_BRIDGE = ROOT / "sim/experiments/lab_nav_fix_20261106/lab_bridge_fix.yaml"
DST_DIR = ROOT / "sim/experiments/agentvln_hunter"
DST_WORLD = DST_DIR / "scenes/lab_agentvln_world.sdf"
DST_BRIDGE = DST_DIR / "config/agentvln_bridge.yaml"
MARKERS_JSON = DST_DIR / "config/scene_markers.json"

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

# The gallery ahead of the spawn is free only up to x ~= 2.2 in the fixed map;
# x=2.5 is unknown/wall and was occluded in the first camera frame.  These three
# markers sit in free space 1.07 m ahead of the camera, at z=1.0, so all three
# are visible in the 640x480 view without changing the vehicle pose.
MARKERS = [
    ("red", 1.5, -1.05, 0.90, "0.90 0.05 0.05 1", "1.00 0.02 0.02 1", "0.30 0.00 0.00 1"),
    ("green", 1.5, -0.75, 0.90, "0.05 0.85 0.05 1", "0.02 1.00 0.02 1", "0.00 0.30 0.00 1"),
    ("blue", 1.5, -0.45, 0.90, "0.05 0.05 0.90 1", "0.02 0.02 1.00 1", "0.00 0.00 0.30 1"),
]

def marker_xml(name, x, y, z, ambient, diffuse, emissive):
    return f"""<model name="marker_{name}" static="true">
  <static>true</static>
  <pose>{x} {y} {z} 0 0 0</pose>
  <link name="link">
    <visual name="visual">
      <cast_shadows>false</cast_shadows>
      <geometry><box><size>0.12 0.12 0.12</size></box></geometry>
      <material>
        <ambient>{ambient}</ambient>
        <diffuse>{diffuse}</diffuse>
        <emissive>{emissive}</emissive>
      </material>
    </visual>
  </link>
</model>"""

def main():
    DST_WORLD.parent.mkdir(parents=True, exist_ok=True)
    DST_BRIDGE.parent.mkdir(parents=True, exist_ok=True)
    s = SRC_WORLD.read_text()
    if "agentvln_camera" in s:
        raise SystemExit("camera already present in destination source; refusing to duplicate")
    old = "</lidar></sensor></link>"
    if s.count(old) != 1:
        raise SystemExit(f"expected one scan closing sequence, found {s.count(old)}")
    s = s.replace(old, "</lidar></sensor>" + CAMERA + "</link>")
    marker_blocks = "\n".join(marker_xml(*m) for m in MARKERS)
    if "</world>" not in s:
        raise SystemExit("no </world>")
    s = s.replace("</world>", marker_blocks + "\n</world>")
    DST_WORLD.write_text(s)
    markers = []
    for name, x, y, z, *_ in MARKERS:
        markers.append({"name": name, "xyz": [x, y, z], "size": 0.12})
    MARKERS_JSON.write_text(json.dumps({"markers": markers, "frame": "map"}, indent=2) + "\n")
    bridge = json.loads(SRC_BRIDGE.read_text())
    for suffix, ros_type in [("image", "sensor_msgs/msg/Image"),
                             ("depth_image", "sensor_msgs/msg/Image"),
                             ("camera_info", "sensor_msgs/msg/CameraInfo")]:
        bridge.append({
            "ros_topic_name": f"/hz_sim/agentvln/camera/{suffix}",
            "gz_topic_name": f"/hz_sim/agentvln/camera/{suffix}",
            "ros_type_name": ros_type,
            "gz_type_name": "ignition.msgs.Image" if suffix != "camera_info" else "ignition.msgs.CameraInfo",
            "direction": "GZ_TO_ROS",
            "lazy": False,
            "publisher_queue": 2,
            "subscriber_queue": 2,
        })
    DST_BRIDGE.write_text(json.dumps(bridge, indent=2) + "\n")
    for p in (DST_WORLD, DST_BRIDGE):
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        print(p, "sha256", h, "bytes", p.stat().st_size)
    print("markers", json.dumps(markers))

if __name__ == "__main__":
    main()
