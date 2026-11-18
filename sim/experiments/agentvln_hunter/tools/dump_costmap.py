#!/usr/bin/env python3
"""Dump one Nav2 costmap snapshot to npz/png and report values at points."""
import sys
import json
import numpy as np
from PIL import Image, ImageDraw
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from nav_msgs.msg import OccupancyGrid

def main():
    topic = sys.argv[1]
    prefix = sys.argv[2]
    points = []
    for spec in sys.argv[3:]:
        name, x, y = spec.split(",")
        points.append((name, float(x), float(y)))
    rclpy.init()
    node = Node("costmap_dump")
    qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                     reliability=ReliabilityPolicy.RELIABLE)
    box = {}
    def cb(msg):
        box["msg"] = msg
    node.create_subscription(OccupancyGrid, topic, cb, qos)
    while "msg" not in box:
        rclpy.spin_once(node, timeout_sec=1.0)
    msg = box["msg"]
    info = msg.info
    W, H, res = info.width, info.height, info.resolution
    ox, oy = info.origin.position.x, info.origin.position.y
    data = np.array(msg.data, dtype=np.int16).reshape(H, W)
    np.savez(prefix + ".npz", data=data, origin=np.array([ox, oy]), resolution=res)
    # OccupancyGrid row 0 is at origin.y (south), so flip only for a north-up image.
    gray = np.full((H, W), 205, dtype=np.uint8)
    gray[data == 0] = 254
    gray[(data > 0) & (data < 100)] = 128
    gray[data >= 100] = 0
    gray = np.flipud(gray)
    img = Image.fromarray(gray, mode="L").convert("RGB")
    dr = ImageDraw.Draw(img)
    report = {"topic": topic, "frame": msg.header.frame_id, "width": W, "height": H,
              "resolution": res, "origin": [ox, oy], "points": {}}
    def to_px(x, y):
        c = (x - ox) / res
        r = (y - oy) / res
        return c, r
    for name, x, y in points:
        c, r = to_px(x, y)
        ci, ri = int(round(c)), int(round(r))
        val = int(data[ri, ci]) if 0 <= ri < H and 0 <= ci < W else None
        report["points"][name] = {"xy": [x, y], "cell": [ci, ri], "value": val}
        ir = H - 1 - r
        dr.ellipse([c - 4, ir - 4, c + 4, ir + 4], outline=(255, 0, 0), width=2)
        dr.text((c + 6, ir - 6), name, fill=(255, 0, 0))
    img.save(prefix + ".png")
    with open(prefix + ".json", "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report, indent=1))
    rclpy.shutdown()

if __name__ == "__main__":
    main()
