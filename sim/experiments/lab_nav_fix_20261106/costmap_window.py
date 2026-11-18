"""Coarse picture of the global costmap around a point, plus a value histogram.

The planner's view is not the map's view: inflation, unknown handling and the obstacle
layer all rewrite the costs.  Printing the histogram first stops guesswork about which
layer produced a value.
"""
import sys
from collections import Counter

import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


class Probe(Node):
    def __init__(self):
        super().__init__('costmap_window')
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                         reliability=ReliabilityPolicy.RELIABLE)
        self.grid = None
        self.create_subscription(OccupancyGrid, '/global_costmap/costmap', self.cb, qos)
        self.create_timer(3.0, self.report)

    def cb(self, msg):
        self.grid = msg

    def report(self):
        g = self.grid
        if g is None:
            print('no costmap')
            return
        info = g.info
        res, ox, oy = info.resolution, info.origin.position.x, info.origin.position.y
        w, h, data = info.width, info.height, g.data

        hist = Counter(data)
        print('histogram (top 8):', hist.most_common(8))
        print('cells', w * h, 'sum>=253', sum(v for k, v in hist.items() if k >= 253),
              'unknown(-1)', hist.get(-1, 0), 'free(0)', hist.get(0, 0))

        x0, y0, step = 1.60, 0.30, 2  # 2 cells = 0.10 m per character
        rows = []
        for rr in range(-12, 13):
            line = ''
            for cc in range(-18, 19):
                x = x0 + cc * step * res
                y = y0 - rr * step * res
                c = int((x - ox) / res)
                r = int(h - 1 - (y - oy) / res)
                if not (0 <= r < h and 0 <= c < w):
                    line += '?'
                    continue
                v = data[r * w + c]
                if v < 0:
                    line += '#'
                elif v == 0:
                    line += '.'
                elif v < 99:
                    line += ':'
                elif v < 253:
                    line += '+'
                else:
                    line += 'X'
            rows.append(line)
        print('\nwindow 3.8 x 2.5 m, robot at the middle character '
              '(. free  : low  + high  X lethal  # unknown)')
        for line in rows:
            print(line)


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
    sys.exit(main())
