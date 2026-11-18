"""Ask the global costmap for its grid and compare it with /map cell by cell.

The costmap does not publish on a timer in this configuration (measured: nothing on
/global_costmap/costmap in 8 s), so it is fetched through the get_costmap service
instead of by subscription.  The question is the same either way: at the cells where
the map says "unknown", what does the costmap say?
"""
import sys

import rclpy
from nav2_msgs.srv import GetCostmap
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


class Probe(Node):
    def __init__(self):
        super().__init__('costmap_unknown_probe')
        q = QoSProfile(depth=1)
        q.durability = DurabilityPolicy.TRANSIENT_LOCAL
        q.reliability = ReliabilityPolicy.RELIABLE
        self.map = None
        self.create_subscription(OccupancyGrid, '/map', self._on_map, q)

    def _on_map(self, msg):
        self.map = msg


def main():
    rclpy.init()
    node = Probe()
    deadline = node.get_clock().now().nanoseconds + 20 * 10**9
    while rclpy.ok() and node.map is None:
        rclpy.spin_once(node, timeout_sec=0.2)
        if node.get_clock().now().nanoseconds > deadline:
            print('/map not received')
            return 1

    client = node.create_client(GetCostmap, '/global_costmap/get_costmap')
    if not client.wait_for_service(timeout_sec=10.0):
        print('get_costmap service unavailable')
        return 2
    future = client.call_async(GetCostmap.Request())
    rclpy.spin_until_future_complete(node, future, timeout_sec=20.0)
    res = future.result()
    if res is None:
        print('get_costmap call returned nothing')
        return 3

    m = node.map
    meta = res.map.metadata          # nav2_msgs/Costmap carries metadata, not info
    data = res.map.data
    print(f'map  {m.info.width}x{m.info.height} @ {m.info.resolution} '
          f'origin ({m.info.origin.position.x:.2f}, {m.info.origin.position.y:.2f})')
    print(f'cost {meta.size_x}x{meta.size_y} @ {meta.resolution:.3f} '
          f'origin ({meta.origin.position.x:.2f}, {meta.origin.position.y:.2f})')

    # Costmap is in metres; build a lookup from map cell -> costmap value.
    def lookup(x, y):
        col = int((x - meta.origin.position.x) / meta.resolution)
        row = int((y - meta.origin.position.y) / meta.resolution)
        if 0 <= col < meta.size_x and 0 <= row < meta.size_y:
            return int(data[row * meta.size_x + col])
        return None

    res_m = m.info.resolution
    ox, oy = m.info.origin.position.x, m.info.origin.position.y
    pairs = {}
    for row in range(m.info.height):
        y = oy + (row + 0.5) * res_m
        for col in range(m.info.width):
            mv = m.data[row * m.info.width + col]
            if mv not in (-1, 100):
                continue
            x = ox + (col + 0.5) * res_m
            cv = lookup(x, y)
            pairs[(mv, cv)] = pairs.get((mv, cv), 0) + 1

    for mv, label in ((-1, 'unknown'), (100, 'occupied')):
        got = {k: v for k, v in pairs.items() if k[0] == mv}
        print(f'{label} map cell -> costmap value (top):')
        for (mvv, cv), n in sorted(got.items(), key=lambda kv: -kv[1])[:5]:
            print(f'  map {mvv} -> cost {cv}: {n}')
    cheap = sum(n for (mv, cv), n in pairs.items()
                if mv == -1 and cv is not None and cv < 250)
    outside = sum(n for (mv, cv), n in pairs.items() if mv == -1 and cv is None)
    print(f'unknown cells inside the costmap that stay cheap (<250): {cheap}')
    print(f'unknown cells outside the costmap window: {outside}')
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
