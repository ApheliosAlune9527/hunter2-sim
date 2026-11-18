#!/usr/bin/env python3
"""AMCL accuracy on the corrected configuration: static, then a 2 m straight drive.

Section F of the correction plan asks for two numbers, both against the simulated truth
(which is observed only -- it never feeds the filter):

    static:      < 0.05 m position error while standing still
    after 2 m:   < 0.15 m position error at the end of a straight 2 m drive

The reset has to be deliberate: teleporting the model does not move the particle filter,
so the initial pose is published again after the teleport and the filter is given a few
seconds of scans before anything is measured.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'outputs' / 'lab_nav_fix_20261106'
SPAWN = (-0.21, -0.77, 0.0)
WORLD = 'hz_lab_2d'
MODEL = 'hz_hunter_full'


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class Probe(Node):
    def __init__(self):
        super().__init__('amcl_eval_fix')
        self.truth = None
        self.est = None
        self.create_subscription(Odometry, '/ground_truth', self._truth, 10)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self._est, 10)
        self.cmd = self.create_publisher(Twist, '/cmd_vel', 10)
        self.init = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)

    def _truth(self, msg):
        p = msg.pose.pose
        self.truth = (p.position.x, p.position.y, yaw_of(p.orientation))

    def _est(self, msg):
        p = msg.pose.pose
        self.est = (p.position.x, p.position.y, yaw_of(p.orientation))

    def sim(self):
        return self.get_clock().now().nanoseconds / 1e9

    def spin_sim(self, seconds):
        end = self.sim() + seconds
        while self.sim() < end:
            rclpy.spin_once(self, timeout_sec=0.02)

    def teleport(self):
        req = ('name: "%s", position: {x: %.6f, y: %.6f, z: 0.165}, '
               'orientation: {x: 0, y: 0, z: 0, w: 1}' % (MODEL, SPAWN[0], SPAWN[1]))
        subprocess.run(['ign', 'service', '-s', '/world/%s/set_pose' % WORLD,
                        '--reqtype', 'ignition.msgs.Pose', '--reptype', 'ignition.msgs.Boolean',
                        '--timeout', '4000', '--req', req],
                       capture_output=True, text=True, timeout=20)

    def seed(self, repeats=5):
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.pose.pose.position.x = SPAWN[0]
        msg.pose.pose.position.y = SPAWN[1]
        msg.pose.pose.orientation.w = 1.0
        msg.pose.covariance[0] = 0.25
        msg.pose.covariance[7] = 0.25
        msg.pose.covariance[35] = 0.0685
        for _ in range(repeats):
            msg.header.stamp = self.get_clock().now().to_msg()
            self.init.publish(msg)
            self.spin_sim(0.2)


def main():
    rclpy.init()
    node = Probe()
    node.set_parameters([rclpy.parameter.Parameter('use_sim_time', value=True)])
    while node.truth is None:
        rclpy.spin_once(node, timeout_sec=0.1)

    node.teleport()
    node.spin_sim(0.5)
    node.seed()
    node.spin_sim(4.0)          # let the filter settle on the new pose
    # AMCL publishes nothing until it has been seeded, so /amcl_pose only appears here.
    waited = 0.0
    while node.est is None and waited < 20.0:
        rclpy.spin_once(node, timeout_sec=0.1)
        waited += 0.1
    if node.est is None:
        print('no /amcl_pose after seeding; is the amcl node running?', flush=True)
        return 2

    # ---- static -------------------------------------------------------------------
    samples = []
    end = node.sim() + 12.0
    while node.sim() < end:
        rclpy.spin_once(node, timeout_sec=0.05)
        if node.truth and node.est:
            d = math.hypot(node.est[0] - node.truth[0], node.est[1] - node.truth[1])
            samples.append(d)
    static = {'samples': len(samples),
              'mean_error_m': round(sum(samples) / len(samples), 4),
              'max_error_m': round(max(samples), 4),
              'min_error_m': round(min(samples), 4)}

    # ---- straight 2 m -------------------------------------------------------------
    start_truth = node.truth
    v = 0.12
    twist = Twist()
    twist.linear.x = v
    travelled = 0.0
    last = start_truth
    while travelled < 2.0:
        node.cmd.publish(twist)
        rclpy.spin_once(node, timeout_sec=0.02)
        if node.truth and last:
            travelled += math.hypot(node.truth[0] - last[0], node.truth[1] - last[1])
            last = node.truth
    node.cmd.publish(Twist())
    node.spin_sim(1.5)

    err = math.hypot(node.est[0] - node.truth[0], node.est[1] - node.truth[1])
    head = abs(math.atan2(math.sin(node.est[2] - node.truth[2]),
                          math.cos(node.est[2] - node.truth[2])))
    straight = {'travelled_m': round(travelled, 3),
                'end_error_m': round(err, 4),
                'end_heading_error_rad': round(head, 4)}

    ok = static['max_error_m'] < 0.05 and straight['end_error_m'] < 0.15
    payload = {'static': static, 'straight': straight,
               'criteria': {'static_max_lt_m': 0.05, 'straight_end_lt_m': 0.15},
               'ok': ok,
               'notes': ('ground truth is observed only; the filter is seeded with '
                         '/initialpose after the teleport because a teleport does not '
                         'move the particles')}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'amcl_eval_fix.json').write_text(json.dumps(payload, indent=1))
    print(json.dumps(payload, indent=1), flush=True)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
