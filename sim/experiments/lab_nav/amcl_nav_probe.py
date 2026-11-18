#!/usr/bin/env python3
"""Why did an AMCL-driven run miss?  Reset, re-init, send one goal, then print
ground truth next to what AMCL believes, the command actually issued, and where
the planner thinks the path starts.  Cancels after N simulated seconds.
"""
import json
import math
import subprocess
import sys

import rclpy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, Twist
from nav_msgs.msg import Odometry, Path as PathMsg
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

WORLD, MODEL, SPAWN = 'hz_lab_2d', 'hz_hunter_full', (-0.21, -0.77, 0.0)
GOALS = {'short_straight': (1.885, 0.435, 0.4495), 'mid_offset': (3.185, 1.235, 0.3193)}


def yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


class P(Node):
    def __init__(self):
        super().__init__('amcl_nav_probe')
        self.truth = self.amcl = self.cmd = self.plan = None
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.pub_cmd = self.create_publisher(Twist, '/cmd_vel', 10)
        self.pub_init = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
        self.create_subscription(Odometry, '/ground_truth', self.t_truth, qos_profile_sensor_data)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self.t_amcl, 10)
        self.create_subscription(Twist, '/cmd_vel', self.t_cmd, 10)
        self.create_subscription(PathMsg, '/plan', self.t_plan, 10)

    def t_truth(self, m):
        p = m.pose.pose.position
        self.truth = (p.x, p.y, yaw_of(m.pose.pose.orientation))

    def t_amcl(self, m):
        p = m.pose.pose.position
        self.amcl = (p.x, p.y, yaw_of(m.pose.pose.orientation))

    def t_cmd(self, m):
        self.cmd = (m.linear.x, m.angular.z)

    def t_plan(self, m):
        if m.poses:
            self.plan = (m.poses[0].pose.position.x, m.poses[0].pose.position.y, len(m.poses))


def spin(n, s):
    import time
    end = time.time() + s
    while time.time() < end:
        rclpy.spin_once(n, timeout_sec=0.05)


def main():
    goal = GOALS[sys.argv[1] if len(sys.argv) > 1 else 'short_straight']
    rclpy.init()
    n = P()
    subprocess.run(['ign', 'service', '-s', f'/world/{WORLD}/set_pose',
                    '--reqtype', 'ignition.msgs.Pose', '--reptype', 'ignition.msgs.Boolean',
                    '--timeout', '5000', '--req',
                    f'name: "{MODEL}", position: {{x: {SPAWN[0]}, y: {SPAWN[1]}, z: 0.165}}, '
                    f'orientation: {{x: 0, y: 0, z: 0, w: 1}}'],
                   capture_output=True, text=True, timeout=20)
    spin(n, 1.0)
    init = PoseWithCovarianceStamped()
    init.header.frame_id = 'map'
    init.pose.pose.position.x, init.pose.pose.position.y = SPAWN[0], SPAWN[1]
    init.pose.pose.orientation.w = 1.0
    init.pose.covariance[0] = 0.25
    init.pose.covariance[7] = 0.25
    init.pose.covariance[35] = 0.0685
    for _ in range(3):
        init.header.stamp = n.get_clock().now().to_msg()
        n.pub_init.publish(init)
        spin(n, 0.4)
    spin(n, 1.5)
    print('after re-init: truth=%s amcl=%s' % (n.truth, n.amcl))

    g = NavigateToPose.Goal()
    g.pose = PoseStamped()
    g.pose.header.frame_id = 'map'
    g.pose.header.stamp = n.get_clock().now().to_msg()
    g.pose.pose.position.x, g.pose.pose.position.y = goal[0], goal[1]
    g.pose.pose.orientation.z = math.sin(goal[2] / 2)
    g.pose.pose.orientation.w = math.cos(goal[2] / 2)
    n.client.wait_for_server(timeout_sec=10)
    f = n.client.send_goal_async(g)
    rclpy.spin_until_future_complete(n, f, timeout_sec=10)
    h = f.result()
    print('accepted:', h is not None and h.accepted)
    res = h.get_result_async()

    t0 = n.get_clock().now().nanoseconds * 1e-9
    while not res.done():
        rclpy.spin_once(n, timeout_sec=0.05)
        if n.get_clock().now().nanoseconds * 1e-9 - t0 > 18:
            break
    for i in range(18):
        rclpy.spin_once(n, timeout_sec=0.05)
        spin(n, 1.0)
        e = None
        if n.truth and n.amcl:
            e = math.hypot(n.truth[0] - n.amcl[0], n.truth[1] - n.amcl[1])
        print('t=%4.1f truth=(%+6.2f,%+6.2f,%+5.2f) amcl=(%s) err=%s cmd=%s plan0=%s'
              % (i, *(n.truth or (0, 0, 0)),
                 'n/a' if not n.amcl else '%+6.2f,%+6.2f,%+5.2f' % n.amcl,
                 'n/a' if e is None else '%.2f' % e, n.cmd, n.plan))
    h.cancel_goal_async()
    spin(n, 0.5)
    n.pub_cmd.publish(Twist())
    print(json.dumps({'done': res.done()}))
    n.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
