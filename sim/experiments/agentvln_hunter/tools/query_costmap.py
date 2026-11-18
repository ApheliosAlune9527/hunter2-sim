#!/usr/bin/env python3
import sys, time
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from nav_msgs.msg import OccupancyGrid

class Q(Node):
    def __init__(self):
        super().__init__("query_costmap")
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                         reliability=ReliabilityPolicy.RELIABLE)
        self.msg = None
        self.create_subscription(OccupancyGrid, "/global_costmap/costmap", self.cb, qos)
    def cb(self, m):
        self.msg = m

def main():
    rclpy.init()
    n = Q()
    t0 = time.time()
    while n.msg is None and time.time() - t0 < 10:
        rclpy.spin_once(n, timeout_sec=0.2)
    m = n.msg
    if m is None:
        print("NO_COSTMAP")
        return
    info = m.info
    w, h = info.width, info.height
    res = info.resolution
    ox, oy = info.origin.position.x, info.origin.position.y
    data = np.array(m.data, dtype=np.int16).reshape(h, w)
    print("frame", m.header.frame_id, "size", (w, h), "res", res, "origin", (ox, oy))
    print("hist", dict(zip(*[x.tolist() for x in np.unique(data, return_counts=True)])))
    for spec in sys.argv[1:]:
        name, xs, ys = spec.split(",")
        x, y = float(xs), float(ys)
        c = int(round((x - ox) / res))
        r = int(round((y - oy) / res))
        print("---", name, "xy", (x, y), "cell", (c, r), "value", int(data[r, c]) if 0 <= r < h and 0 <= c < w else "OOB")
        for rr in range(r + 5, r - 6, -1):
            row = []
            for cc in range(c - 5, c + 6):
                if 0 <= rr < h and 0 <= cc < w:
                    v = int(data[rr, cc])
                    row.append("##" if v == 100 else ("??" if v < 0 else (".." if v == 0 else f"{v:2d}")))
                else:
                    row.append("  ")
            print("y=%+.2f " % (oy + rr * res) + " ".join(row))
    rclpy.shutdown()

if __name__ == "__main__":
    main()
