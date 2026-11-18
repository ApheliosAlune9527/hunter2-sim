"""Do the rear wheels physically rotate when a speed is commanded?

Reads the wheel link's orientation from pose/info twice while publishing /cmd_vel and
reports the angle change.  Wheels that turn while the body stays put mean the body is
jammed or slipping; wheels that stay still mean the joint command never reaches physics.
"""
import math
import subprocess
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

WORLD = 'hz_lab_2d'
LINK = 'rear_left_wheel_link'


def link_quat(name):
    p = subprocess.run(['timeout', '3', 'ign', 'topic', '-e', '-t',
                        f'/world/{WORLD}/pose/info'], capture_output=True, text=True)
    text = p.stdout
    idx = text.find(f'name: "{name}"')
    while idx != -1:
        block = text[idx:idx + 600]
        if 'orientation {' in block and 'position {' in block:
            o = block.split('orientation {')[1].split('}')[0]
            vals = {}
            for axis in ('x', 'y', 'z', 'w'):
                vals[axis] = float(o.split(f'{axis}: ')[1].split()[0])
            return vals
        idx = text.find(f'name: "{name}"', idx + 1)
    return None


def angle_between(a, b):
    dot = sum(a[k] * b[k] for k in 'xyzw')
    return 2 * math.acos(min(1.0, abs(dot)))


def main():
    rclpy.init()
    node = Node('wheel_turn_probe')
    node.set_parameters([rclpy.parameter.Parameter('use_sim_time', value=True)])
    pub = node.create_publisher(Twist, '/cmd_vel', 10)

    q0 = link_quat(LINK)
    cmd = Twist()
    cmd.linear.x = 0.3
    end = time.monotonic() + 6
    while time.monotonic() < end:
        pub.publish(cmd)
        rclpy.spin_once(node, timeout_sec=0.02)
    q1 = link_quat(LINK)
    pub.publish(Twist())

    print({'link': LINK, 'q0': q0, 'q1': q1,
           'rotation_rad': None if not (q0 and q1) else round(angle_between(q0, q1), 4)})
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
