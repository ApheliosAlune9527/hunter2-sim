"""Score how well the live scan lies on the map's walls.

Beam endpoints are expressed in the scan frame, so they must be carried into the map
frame through TF before they can be compared with the map.  Forgetting that step makes
a perfectly aligned laser look almost entirely wrong (13% on-wall instead of ~85%),
because the offsets of the robot pose are being treated as if they were wall positions.
"""
import math
import sys

import numpy as np
import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from rclpy.time import Time
from sensor_msgs.msg import LaserScan
import tf2_ros


class Probe(Node):
    def __init__(self):
        super().__init__('scan_map_check')
        self.map = None
        self.scan = None
        self.buffer = tf2_ros.Buffer()
        self.listener = tf2_ros.TransformListener(self.buffer, self)
        latched = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(OccupancyGrid, '/map', self.on_map, latched)
        self.create_subscription(LaserScan, '/scan', self.on_scan, 10)

    def on_map(self, msg):
        self.map = msg

    def on_scan(self, msg):
        self.scan = msg

    def map_to_scan(self):
        """Return (tx, ty, yaw) taking points in the scan frame into the map frame."""
        for _ in range(50):
            try:
                tr = self.buffer.lookup_transform('map', self.scan.header.frame_id,
                                                  Time(), Duration(seconds=1.0))
            except Exception:
                rclpy.spin_once(self, timeout_sec=0.1)
                continue
            t = tr.transform.translation
            q = tr.transform.rotation
            yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                             1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            return t.x, t.y, yaw
        return None


def occupied(msg):
    w, h = msg.info.width, msg.info.height
    data = np.asarray(msg.data, dtype=np.int16).reshape(h, w)
    return data == 100


def score(scan, grid, info, pose):
    res = info.resolution
    ox, oy = info.origin.position.x, info.origin.position.y
    rows, cols = grid.shape
    tx, ty, yaw = pose
    hits = 0
    misses = 0
    n = len(scan.ranges)
    for i, r in enumerate(scan.ranges):
        if not math.isfinite(r) or r <= scan.range_min + 1e-6 or r >= scan.range_max:
            continue
        theta = scan.angle_min + i * scan.angle_increment
        lx, ly = r * math.cos(theta), r * math.sin(theta)
        x = tx + lx * math.cos(yaw) - ly * math.sin(yaw)
        y = ty + lx * math.sin(yaw) + ly * math.cos(yaw)
        c = int((x - ox) / res)
        rr = int((y - oy) / res)
        if not (0 <= rr < rows and 0 <= c < cols):
            misses += 1
            continue
        window = grid[max(0, rr - 2):rr + 3, max(0, c - 2):c + 3]
        if window.any():
            hits += 1
        else:
            misses += 1
    return hits, misses


def main():
    rclpy.init()
    node = Probe()
    for _ in range(300):
        rclpy.spin_once(node, timeout_sec=0.1)
        if node.map is not None and node.scan is not None:
            break
    if node.map is None or node.scan is None:
        print('missing map or scan')
        node.destroy_node()
        rclpy.shutdown()
        return 2
    pose = node.map_to_scan()
    if pose is None:
        print('no map -> laser transform')
        node.destroy_node()
        rclpy.shutdown()
        return 2
    grid = occupied(node.map)
    hits, misses = score(node.scan, grid, node.map.info, pose)
    total = hits + misses
    frac = hits / total if total else 0.0
    print(f'pose_x={pose[0]:.3f} pose_y={pose[1]:.3f} pose_yaw={pose[2]:.3f} '
          f'beams_used={total} on_wall={hits} off_wall={misses} fraction_on_wall={frac:.3f}')
    node.destroy_node()
    rclpy.shutdown()
    return 0 if frac >= 0.75 else 1


if __name__ == '__main__':
    sys.exit(main())
