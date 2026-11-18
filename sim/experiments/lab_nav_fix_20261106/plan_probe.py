"""Print the first and last pose of the plan on /plan, plus its length.

RViz keeps drawing the last path it received; without looking at the message itself it
is impossible to tell a stale plan from a live one.
"""
import math

import rclpy
from nav_msgs.msg import Path
from rclpy.node import Node


def yaw(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


class Probe(Node):
    def __init__(self):
        super().__init__('plan_probe')
        self.create_subscription(Path, '/plan', self.cb, 1)

    def cb(self, msg):
        p = msg.poses
        if not p:
            print('plan is empty')
            raise SystemExit(0)
        length = 0.0
        for a, b in zip(p, p[1:]):
            length += math.hypot(b.pose.position.x - a.pose.position.x,
                                 b.pose.position.y - a.pose.position.y)
        a, b = p[0].pose, p[-1].pose
        print(f'poses={len(p)} length={length:.3f} m')
        print(f'start=({a.position.x:.3f}, {a.position.y:.3f}) yaw={yaw(a.orientation):.3f}')
        print(f'end  =({b.position.x:.3f}, {b.position.y:.3f}) yaw={yaw(b.orientation):.3f}')
        print(f'stamp={msg.header.stamp.sec}.{msg.header.stamp.nanosec:09d} '
              f'frame={msg.header.frame_id}')
        raise SystemExit(0)


def main():
    rclpy.init()
    node = Probe()
    try:
        rclpy.spin(node)
    except (SystemExit, KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
