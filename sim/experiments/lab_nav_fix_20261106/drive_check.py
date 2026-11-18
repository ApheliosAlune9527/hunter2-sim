"""Does the vehicle move under /cmd_vel in this world, and does the sensor stay silent?

Small diagnostic used while wiring the contact sensor: it drives toward a wall for a
few seconds and prints the true pose before and after, so a silent sensor can be told
apart from a vehicle that never moved.
"""
import math
import subprocess
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from ros_gz_interfaces.msg import Contacts

WORLD = 'hz_lab_2d'
MODEL = 'hz_hunter_full'


def sh(args, timeout=10):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout).stdout


def set_pose(x, y, yaw, z=0.165):
    req = (f'name: "{MODEL}", position: {{x: {x}, y: {y}, z: {z}}}, '
           f'orientation: {{x: 0, y: 0, z: {math.sin(yaw / 2)}, w: {math.cos(yaw / 2)}}}')
    return sh(['ign', 'service', '-s', f'/world/{WORLD}/set_pose',
               '--reqtype', 'ignition.msgs.Pose', '--reptype', 'ignition.msgs.Boolean',
               '--timeout', '5000', '--req', req]).strip()


def pose():
    out = sh(['ign', 'topic', '-e', '-t', f'/world/{WORLD}/pose/info'], timeout=5)
    out = out  # single buffered read is unreliable; use one-shot echo with timeout
    return out


def read_pose_via_timeout():
    p = subprocess.run(['timeout', '3', 'ign', 'topic', '-e', '-t', f'/world/{WORLD}/pose/info'],
                       capture_output=True, text=True)
    text = p.stdout
    marker = f'name: "{MODEL}"'
    idx = text.find(marker)
    while idx != -1:
        block = text[idx:idx + 400]
        if 'position {' in block:
            xs = block.split('x: ')[1].split()[0]
            ys = block.split('y: ')[1].split()[0]
            return float(xs), float(ys)
        idx = text.find(marker, idx + 1)
    return None


def main():
    rclpy.init()
    node = Node('drive_check')
    node.set_parameters([rclpy.parameter.Parameter('use_sim_time', value=True)])
    pub = node.create_publisher(Twist, '/cmd_vel', 10)
    hits = []
    node.create_subscription(Contacts, '/chassis_contact',
                             lambda m: hits.append(len(m.contacts)), 10)

    set_pose(4.60, -1.565, 0.0)
    time.sleep(3)
    before = read_pose_via_timeout()

    cmd = Twist()
    cmd.linear.x = 0.15
    end = time.monotonic() + 6.0
    sent = 0
    while time.monotonic() < end:
        pub.publish(cmd)
        rclpy.spin_once(node, timeout_sec=0.02)
        sent += 1
    pub.publish(Twist())
    for _ in range(60):
        rclpy.spin_once(node, timeout_sec=0.02)

    after = read_pose_via_timeout()
    print({'before': before, 'after': after, 'cmd_publishes': sent,
           'contact_messages': len(hits), 'contact_first': hits[:5]})
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
