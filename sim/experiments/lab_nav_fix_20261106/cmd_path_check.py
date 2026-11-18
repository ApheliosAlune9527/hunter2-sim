"""Where does the command stop: ROS /cmd_vel, the gz topic, or the plugin?"""
import math
import subprocess
import threading
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

WORLD = 'hz_lab_2d'
MODEL = 'hz_hunter_full'


def set_pose(x, y, yaw, z=0.165):
    req = (f'name: "{MODEL}", position: {{x: {x}, y: {y}, z: {z}}}, '
           f'orientation: {{x: 0, y: 0, z: {math.sin(yaw / 2)}, w: {math.cos(yaw / 2)}}}')
    return subprocess.run(['ign', 'service', '-s', f'/world/{WORLD}/set_pose',
                           '--reqtype', 'ignition.msgs.Pose',
                           '--reptype', 'ignition.msgs.Boolean', '--timeout', '5000',
                           '--req', req], capture_output=True, text=True).stdout.strip()


def read_pose():
    p = subprocess.run(['timeout', '3', 'ign', 'topic', '-e', '-t',
                        f'/world/{WORLD}/pose/info'], capture_output=True, text=True)
    text = p.stdout
    idx = text.find(f'name: "{MODEL}"')
    while idx != -1:
        block = text[idx:idx + 400]
        if 'position {' in block:
            xs = float(block.split('x: ')[1].split()[0])
            ys = float(block.split('y: ')[1].split()[0])
            return xs, ys
        idx = text.find(f'name: "{MODEL}"', idx + 1)
    return None


def main():
    rclpy.init()
    node = Node('cmd_probe')
    node.set_parameters([rclpy.parameter.Parameter('use_sim_time', value=True)])
    pub = node.create_publisher(Twist, '/cmd_vel', 10)

    # capture the gz-side topic while publishing
    gz = subprocess.Popen(['ign', 'topic', '-e', '-t', '/hz_sim/lab/cmd_vel'],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

    set_pose(2.535, 12.885, 2.7053)   # the calibrated open-floor pose
    time.sleep(3)
    before = read_pose()

    cmd = Twist()
    cmd.linear.x = 0.15
    end = time.monotonic() + 4.0
    while time.monotonic() < end:
        pub.publish(cmd)
        rclpy.spin_once(node, timeout_sec=0.02)
    pub.publish(Twist())
    time.sleep(0.5)

    gz.terminate()
    out = gz.stdout.read() if gz.stdout else ''
    after = read_pose()
    print({'before': before, 'after': after,
           'gz_topic_bytes': len(out), 'gz_snippet': out[:120].replace('\n', ' ')})
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
