#!/usr/bin/env python3
import math, sys, time
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from nav_msgs.msg import OccupancyGrid

FOOT = [(-0.184, -0.393), (0.834, -0.393), (0.834, 0.393), (-0.184, 0.393)]

class Q(Node):
    def __init__(self):
        super().__init__("check_pose_footprint")
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                         reliability=ReliabilityPolicy.RELIABLE)
        self.msg = None
        self.create_subscription(OccupancyGrid, "/global_costmap/costmap", self.cb, qos)
    def cb(self, m):
        self.msg = m

def sample(data, ox, oy, res, x, y):
    h, w = data.shape
    c = int(round((x - ox) / res))
    r = int(round((y - oy) / res))
    if 0 <= r < h and 0 <= c < w:
        return int(data[r, c])
    return None

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
    occ = data >= 99
    # distance to nearest occupied cell center
    from scipy import ndimage
    dist = ndimage.distance_transform_edt(~occ) * res
    for spec in sys.argv[1:]:
        name, xs, ys, yaws = spec.split(",")
        x, y, yaw = float(xs), float(ys), float(yaws)
        vals = []
        pts = []
        for px, py in FOOT:
            wx = x + math.cos(yaw) * px - math.sin(yaw) * py
            wy = y + math.sin(yaw) * px + math.cos(yaw) * py
            pts.append((wx, wy))
            vals.append(sample(data, ox, oy, res, wx, wy))
        # interior grid
        for fx in np.linspace(-0.184, 0.834, 21):
            for fy in np.linspace(-0.393, 0.393, 17):
                wx = x + math.cos(yaw) * fx - math.sin(yaw) * fy
                wy = y + math.sin(yaw) * fx + math.cos(yaw) * fy
                vals.append(sample(data, ox, oy, res, wx, wy))
        bad = [v for v in vals if v is None or v >= 99]
        c = int(round((x - ox) / res)); r = int(round((y - oy) / res))
        print(f"--- {name} pose=({x:.3f},{y:.3f},{yaw:.3f}) center_cost={int(data[r,c])} "
              f"center_obst_dist={dist[r,c]:.3f}m max_footprint_cost={max([v for v in vals if v is not None], default=-1)} "
              f"bad_samples={len(bad)}/{len(vals)}")
        print("   vertices", [(round(px,2), round(py,2), v) for (px,py),v in zip(pts,vals[:4])])
    rclpy.shutdown()

if __name__ == "__main__":
    main()
