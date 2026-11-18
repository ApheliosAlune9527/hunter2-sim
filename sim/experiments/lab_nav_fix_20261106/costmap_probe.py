"""Print the global costmap neighbourhood around the robot.

Planner failures are usually visible here before they are visible anywhere else: either
the start cell is lethal (the vehicle is standing in inflated space) or the goal is.
"""
import math

import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


class Probe(Node):
    def __init__(self):
        super().__init__('costmap_probe')
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                         reliability=ReliabilityPolicy.RELIABLE)
        self.grid = None
        self.create_subscription(OccupancyGrid, '/global_costmap/costmap', self.cb, qos)
        self.create_timer(2.0, self.report)

    def cb(self, msg):
        self.grid = msg

    def report(self):
        g = self.grid
        if g is None:
            print('no costmap yet')
            return
        info = g.info
        res, ox, oy = info.resolution, info.origin.position.x, info.origin.position.y
        w, h = info.width, info.height
        data = g.data

        def cell(x, y):
            c = int((x - ox) / res)
            r = int(h - 1 - (y - oy) / res)
            if 0 <= r < h and 0 <= c < w:
                return data[r * w + c], r, c
            return None, r, c

        for name, (x, y) in {'robot': (1.60, 0.30), 'goal': (1.885, 0.435),
                             'spawn': (-0.21, -0.77)}.items():
            v, r, c = cell(x, y)
            print(f'{name:6s} ({x:+.2f},{y:+.2f}) value={v} row={r} col={c}')

        # the 11x11 neighbourhood around the robot
        v, r, c = cell(1.60, 0.30)
        rows = []
        for rr in range(max(0, r - 5), min(h, r + 6)):
            rows.append(''.join(
                f'{(data[rr * w + cc] if 0 <= cc < w else -9):4d}'
                for cc in range(max(0, c - 5), min(w, c + 6))))
        print('\nrobot neighbourhood (value, -1 = unknown, 100 = occupied, >=253 lethal):')
        for row in rows:
            print(row)

        lethal = sum(1 for x in data if x >= 253)
        unknown = sum(1 for x in data if x < 0)
        print(f'\ncells={w * h} lethal(>=253)={lethal} unknown={unknown} '
              f'free(0)={sum(1 for x in data if x == 0)}')


def main():
    rclpy.init()
    node = Probe()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
