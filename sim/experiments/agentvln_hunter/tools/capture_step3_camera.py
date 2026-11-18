#!/usr/bin/env python3
"""Capture one synchronized RGB-D frame and project the step-3 props."""
import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import PointStamped
from message_filters import ApproximateTimeSynchronizer, Subscriber
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CameraInfo, Image
from tf2_geometry_msgs import do_transform_point

class Capture(Node):
    def __init__(self, layout):
        super().__init__("capture_step3_camera")
        self.layout = layout
        self.bridge = CvBridge()
        self.frames = []
        self.ready_at = time.monotonic() + 3.0
        self.tf_buffer = None
        from tf2_ros import Buffer, TransformListener
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.clock_ns = None
        self.create_subscription(Clock, "/clock", self.on_clock, 10)
        self.subs = [
            Subscriber(self, Image, "/hz_sim/agentvln/camera/image", qos_profile=qos_profile_sensor_data),
            Subscriber(self, Image, "/hz_sim/agentvln/camera/depth_image", qos_profile=qos_profile_sensor_data),
            Subscriber(self, CameraInfo, "/hz_sim/agentvln/camera/camera_info", qos_profile=qos_profile_sensor_data),
        ]
        self.sync = ApproximateTimeSynchronizer(self.subs, queue_size=10, slop=0.10)
        self.sync.registerCallback(self.cb)
        import tf2_ros
        self.clock = self.get_clock()

    def on_clock(self, msg):
        self.clock_ns = msg.clock.sec * 1_000_000_000 + msg.clock.nanosec

    def cb(self, rgb_msg, depth_msg, info_msg):
        if time.monotonic() < self.ready_at or self.clock_ns is None:
            return
        stamp = rgb_msg.header.stamp
        stamp_ns = stamp.sec * 1_000_000_000 + stamp.nanosec
        age = (self.clock_ns - stamp_ns) / 1e9
        if age < 0 or age > 1.5:
            return
        try:
            tf = self.tf_buffer.lookup_transform("agentvln_camera_optical_frame", "map", stamp)
        except Exception:
            return
        rgb = self.bridge.imgmsg_to_cv2(rgb_msg, desired_encoding="rgb8")
        depth = self.bridge.imgmsg_to_cv2(depth_msg, desired_encoding="32FC1")
        self.frames.append((stamp, age, rgb, depth, info_msg, tf))

def project(tf, x, y, z):
    p = PointStamped()
    p.header.frame_id = "map"
    p.point.x, p.point.y, p.point.z = x, y, z
    q = do_transform_point(p, tf)
    return q.point

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", type=int, default=3)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    layout = json.loads(Path("/mnt/d/rob-memory/sim/experiments/agentvln_hunter/config/target_layout.json").read_text())
    rclpy.init()
    n = Capture(layout)
    end = time.monotonic() + 30.0
    while len(n.frames) < args.frames and time.monotonic() < end:
        rclpy.spin_once(n, timeout_sec=0.05)
    if not n.frames:
        print(json.dumps({"error": "no synchronized frame"}))
        return 1
    stamp, age, rgb, depth, info, tf = n.frames[-1]
    K = [float(v) for v in info.k]
    fx, fy, cx, cy = K[0], K[4], K[2], K[5]
    targets = [("red_sign", layout["red_sign"]["x"], layout["red_sign"]["y"], layout["red_sign"]["z"])]
    targets += [(b["name"], b["x"], b["y"], b["z"]) for b in layout["blue_boxes"]]
    rows = []
    vis = rgb.copy()
    for name, x, y, z in targets:
        p = project(tf, x, y, z)
        in_frame = p.z > 0.2
        u = fx * p.x / p.z + cx if in_frame else None
        v = fy * p.y / p.z + cy if in_frame else None
        in_frame = bool(in_frame and 0 <= u < rgb.shape[1] and 0 <= v < rgb.shape[0])
        med = None
        if in_frame:
            u0, v0 = int(round(u)), int(round(v))
            patch = depth[max(0, v0-3):v0+4, max(0, u0-3):u0+4]
            valid = patch[np.isfinite(patch) & (patch > 0)]
            med = float(np.median(valid)) if valid.size else None
            colour = (255, 255, 0) if name != "red_sign" else (0, 255, 255)
            cv2.circle(vis, (u0, v0), 12, colour, 2)
            cv2.putText(vis, name, (u0+14, v0-8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, colour, 1, cv2.LINE_AA)
        rows.append({
            "name": name, "xyz": [x, y, z],
            "optical": [round(p.x, 4), round(p.y, 4), round(p.z, 4)],
            "u": round(float(u), 2) if u is not None else None,
            "v": round(float(v), 2) if v is not None else None,
            "in_frame": in_frame,
            "depth_median_m": round(med, 4) if med is not None else None,
        })
    cv2.imwrite(str(out / "rgb.png"), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    cv2.imwrite(str(out / "annotated.png"), cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))
    np.save(str(out / "depth.npy"), depth)
    report = {
        "stamp_s": float(stamp.sec) + float(stamp.nanosec) / 1e9,
        "age_s": round(age, 4),
        "rgb_size": list(rgb.shape),
        "K": K,
        "targets": rows,
        "frames": len(n.frames),
    }
    (out / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    rclpy.shutdown()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
