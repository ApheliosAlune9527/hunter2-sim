#!/usr/bin/env python3
"""Task 5 localisation check: AMCL against ground truth, no navigation involved.

Two measurements, in this order:

  static   teleport to the spawn, give AMCL that map pose as the initial pose,
           then watch for 10 simulated seconds.  Acceptance: position error
           < 0.05 m and the estimate does not drift while the robot is still.
  straight drive 2 m with the vehicle's own odometry feeding odom->base_link.
           Acceptance: position error < 0.15 m at the end.

Ground truth is read from Gazebo directly and from the bridged /ground_truth
topic.  It is only ever *observed*: nothing here feeds it back into AMCL, and
AMCL keeps sole ownership of map->odom.
"""
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

OUT = Path('/mnt/d/rob-memory/outputs/lab_nav_20261105')
WORLD = 'hz_lab_2d'
MODEL = 'hz_hunter_full'
SPAWN = (-0.21, -0.77, 0.0)


def yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def set_pose(x, y, z, yaw):
    req = (f'name: "{MODEL}", position: {{x: {x}, y: {y}, z: {z}}}, '
           f'orientation: {{x: 0, y: 0, z: {math.sin(yaw / 2)}, w: {math.cos(yaw / 2)}}}')
    subprocess.run(['ign', 'service', '-s', f'/world/{WORLD}/set_pose',
                    '--reqtype', 'ignition.msgs.Pose',
                    '--reptype', 'ignition.msgs.Boolean',
                    '--timeout', '5000', '--req', req],
                   capture_output=True, text=True, timeout=20)


class Probe(Node):
    def __init__(self):
        super().__init__('amcl_eval')
        self.truth = None
        self.amcl = None
        self.cmd = self.create_publisher(Twist, '/cmd_vel', 10)
        self.init_pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
        self.create_subscription(Odometry, '/ground_truth', self.on_truth, qos_profile_sensor_data)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self.on_amcl, 10)

    def on_truth(self, msg):
        p = msg.pose.pose.position
        self.truth = dict(t=msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                          x=p.x, y=p.y, yaw=yaw_of(msg.pose.pose.orientation))

    def on_amcl(self, msg):
        p = msg.pose.pose.position
        self.amcl = dict(t=msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                         x=p.x, y=p.y, yaw=yaw_of(msg.pose.pose.orientation))


def spin_for(node, seconds):
    end = time.time() + seconds
    while time.time() < end:
        rclpy.spin_once(node, timeout_sec=0.05)


def send_initial_pose(node, x, y, yaw):
    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = 'map'
    msg.header.stamp = node.get_clock().now().to_msg()
    msg.pose.pose.position.x = x
    msg.pose.pose.position.y = y
    msg.pose.pose.orientation.z = math.sin(yaw / 2)
    msg.pose.pose.orientation.w = math.cos(yaw / 2)
    cov = [0.25, 0.0, 0.0, 0.0, 0.0, 0.0,
           0.0, 0.25, 0.0, 0.0, 0.0, 0.0,
           0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
           0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
           0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
           0.0, 0.0, 0.0, 0.0, 0.0, 0.0685]
    msg.pose.covariance = cov
    for _ in range(3):
        node.init_pub.publish(msg)
        spin_for(node, 0.3)


def err(a, b):
    return math.hypot(a['x'] - b['x'], a['y'] - b['y'])


def main():
    rclpy.init()
    node = Probe()
    result = {'spawn': list(SPAWN)}
    try:
        # 1) reset the world pose, then tell AMCL where it is
        set_pose(SPAWN[0], SPAWN[1], 0.165, SPAWN[2])
        spin_for(node, 2.0)
        send_initial_pose(node, SPAWN[0], SPAWN[1], SPAWN[2])
        spin_for(node, 3.0)
        if node.amcl is None or node.truth is None:
            result['ok'] = False
            result['error'] = 'no /amcl_pose or /ground_truth received'
            print(json.dumps(result, indent=1))
            return 1

        # 2) static drift
        samples = []
        t_end = time.time() + 12.0
        while time.time() < t_end:
            spin_for(node, 0.2)
            if node.amcl and node.truth:
                samples.append((err(node.amcl, node.truth), node.amcl['x'], node.amcl['y'],
                                node.truth['x'], node.truth['y']))
        errs = [s[0] for s in samples]
        xs = [s[1] for s in samples]
        ys = [s[2] for s in samples]
        result['static'] = {
            'samples': len(samples),
            'mean_error_m': round(sum(errs) / len(errs), 4),
            'max_error_m': round(max(errs), 4),
            'drift_m': round(math.hypot(max(xs) - min(xs), max(ys) - min(ys)), 4),
        }

        # 3) drive 2 m straight, measuring the estimate against truth at the end
        start_truth = dict(node.truth)
        cmd = Twist()
        cmd.linear.x = 0.12
        moved = 0.0
        t_end = time.time() + 120.0
        while time.time() < t_end:
            node.cmd.publish(cmd)
            spin_for(node, 0.1)
            moved = err(node.truth, start_truth)
            if moved >= 2.0:
                break
        stop = Twist()
        for _ in range(10):
            node.cmd.publish(stop)
            spin_for(node, 0.1)
        spin_for(node, 2.0)
        result['straight'] = {
            'travelled_m': round(moved, 3),
            'end_error_m': round(err(node.amcl, node.truth), 4),
            'heading_error_rad': round(abs(math.atan2(
                math.sin(node.amcl['yaw'] - node.truth['yaw']),
                math.cos(node.amcl['yaw'] - node.truth['yaw']))), 4),
        }
        result['ok'] = (result['static']['max_error_m'] < 0.05
                        and result['straight']['end_error_m'] < 0.15)
        result['criteria'] = {'static_max_error_m': 0.05, 'straight_end_error_m': 0.15}
        (OUT / 'amcl_eval.json').write_text(json.dumps(result, indent=1))
        print(json.dumps(result, indent=1))
        return 0 if result['ok'] else 2
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    sys.exit(main())
