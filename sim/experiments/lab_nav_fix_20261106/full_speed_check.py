"""Drive at full speed for a fixed window and compare distance with the sim clock.

Expected distance is speed x (sim seconds elapsed), so the ratio distinguishes "the world
is slow" from "the wheels spin without traction".
"""
import subprocess
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

WORLD = 'hz_lab_2d'
MODEL = 'hz_hunter_full'
SPEED = 0.3
SECONDS = 20.0


def read_pose():
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


def sim_seconds():
    p = subprocess.run(['timeout', '2', 'ign', 'topic', '-e', '-t', '/clock'],
                       capture_output=True, text=True)
    lines = p.stdout.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == 'sim {':
            sec = int(lines[i + 1].split(':')[1])
            nsec = int(lines[i + 2].split(':')[1])
            return sec + nsec * 1e-9
    return None


def main():
    rclpy.init()
    node = Node('full_speed_probe')
    node.set_parameters([rclpy.parameter.Parameter('use_sim_time', value=True)])
    pub = node.create_publisher(Twist, '/cmd_vel', 10)

    before = read_pose()
    t0 = sim_seconds()
    cmd = Twist()
    cmd.linear.x = SPEED
    end = time.monotonic() + SECONDS
    while time.monotonic() < end:
        pub.publish(cmd)
        rclpy.spin_once(node, timeout_sec=0.02)
    pub.publish(Twist())
    time.sleep(1)
    after = read_pose()
    t1 = sim_seconds()

    moved = ((after[0] - before[0]) ** 2 + (after[1] - before[1]) ** 2) ** 0.5
    ds = (t1 - t0) if (t0 is not None and t1 is not None) else float('nan')
    print({'before': before, 'after': after,
           'moved_m': round(moved, 4),
           'sim_seconds': round(ds, 3),
           'expected_m': round(SPEED * ds, 4),
           'ratio': round(moved / (SPEED * ds), 4) if ds > 0 else None})
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
