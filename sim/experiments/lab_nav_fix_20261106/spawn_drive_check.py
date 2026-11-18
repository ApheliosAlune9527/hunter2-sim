"""Drive from wherever the model currently is; no teleport.

Teleporting first hid the question: a pose inside a wall jams the vehicle and looks
identical to a broken plugin.
"""
import subprocess
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

WORLD = 'hz_lab_2d'
MODEL = 'hz_hunter_full'


def read_xy():
    p = subprocess.run(['timeout', '3', 'ign', 'topic', '-e', '-t',
                        f'/world/{WORLD}/pose/info'], capture_output=True, text=True)
    text = p.stdout
    idx = text.find(f'name: "{MODEL}"')
    while idx != -1:
        block = text[idx:idx + 500]
        if 'position {' in block:
            return (float(block.split('x: ')[1].split()[0]),
                    float(block.split('y: ')[1].split()[0]))
        idx = text.find(f'name: "{MODEL}"', idx + 1)
    return None


def main():
    rclpy.init()
    node = Node('spawn_drive')
    node.set_parameters([rclpy.parameter.Parameter('use_sim_time', value=True)])
    pub = node.create_publisher(Twist, '/cmd_vel', 10)
    time.sleep(1)
    before = read_xy()
    cmd = Twist()
    cmd.linear.x = 0.15
    end = time.monotonic() + 5
    while time.monotonic() < end:
        pub.publish(cmd)
        rclpy.spin_once(node, timeout_sec=0.02)
    pub.publish(Twist())
    time.sleep(0.5)
    after = read_xy()
    dist = None
    if before and after:
        dist = ((after[0] - before[0]) ** 2 + (after[1] - before[1]) ** 2) ** 0.5
    print({'before': before, 'after': after, 'moved_m': None if dist is None else round(dist, 4)})
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
