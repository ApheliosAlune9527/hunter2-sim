"""Read /map once and print its metadata.

The point of the exercise: the map is latched (transient local) and large, so a
plain `ros2 topic echo` can sit there silently.  A subscriber that asks for the
latched sample with a reliable, transient-local QoS gets it immediately.
"""
import sys

import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


class MapProbe(Node):
    def __init__(self):
        super().__init__('map_probe')
        qos = QoSProfile(depth=1)
        qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
        qos.reliability = ReliabilityPolicy.RELIABLE
        self.msg = None
        self.sub = self.create_subscription(OccupancyGrid, '/map', self.cb, qos)

    def cb(self, msg):
        self.msg = msg


def main():
    rclpy.init()
    node = MapProbe()
    end = node.get_clock().now().nanoseconds + 20 * 10**9
    while rclpy.ok() and node.msg is None:
        rclpy.spin_once(node, timeout_sec=0.2)
        if node.get_clock().now().nanoseconds > end:
            break
    msg = node.msg
    if msg is None:
        print('no /map received in 20 s')
        node.destroy_node()
        rclpy.shutdown()
        return 1
    info = msg.info
    print(f'width={info.width} height={info.height} resolution={info.resolution}')
    print(f'origin=({info.origin.position.x:.3f}, {info.origin.position.y:.3f})')
    counts = {}
    for v in msg.data:
        counts[v] = counts.get(v, 0) + 1
    total = sum(counts.values())
    print('cell values:', {k: counts[k] for k in sorted(counts)})
    print(f'total={total}')
    unknown = counts.get(-1, 0)
    occupied = counts.get(100, 0)
    print(f'unknown={unknown} ({unknown / total:.1%}) occupied={occupied} '
          f'({occupied / total:.1%})')
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
