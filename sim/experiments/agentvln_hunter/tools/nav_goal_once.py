#!/usr/bin/env python3
"""Send one NavigateToPose goal, optionally cancel it, and report the terminal state.

Usage: nav_goal_once.py X Y YAW [--timeout 30] [--cancel-after 5]
"""
import argparse, math, time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from nav2_msgs.action import NavigateToPose

def yaw_of(q):
    return math.atan2(2.0*(q.w*q.z+q.x*q.y), 1.0-2.0*(q.y*q.y+q.z*q.z))

class G(Node):
    def __init__(self):
        super().__init__("nav_goal_once")
        self.truth = None
        self.amcl = None
        self.create_subscription(Odometry, "/ground_truth", self.t_cb, 10)
        self.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self.a_cb, 10)
        self.cmd = self.create_publisher(Twist, "/cmd_vel", 10)
        self.client = ActionClient(self, NavigateToPose, "navigate_to_pose")
    def t_cb(self, m):
        p = m.pose.pose
        self.truth = (p.position.x, p.position.y, yaw_of(p.orientation))
    def a_cb(self, m):
        p = m.pose.pose
        self.amcl = (p.position.x, p.position.y, yaw_of(p.orientation))

def spin_until(node, pred, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.02)
        if pred():
            return True
    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("x", type=float); ap.add_argument("y", type=float); ap.add_argument("yaw", type=float)
    ap.add_argument("--timeout", type=float, default=40.0)
    ap.add_argument("--cancel-after", type=float, default=0.0)
    a = ap.parse_args()
    rclpy.init()
    n = G()
    spin_until(n, lambda: n.truth is not None, 5.0)
    if not n.client.wait_for_server(timeout_sec=10.0):
        print("NO_SERVER"); return
    goal = NavigateToPose.Goal()
    goal.pose.header.frame_id = "map"
    goal.pose.header.stamp = n.get_clock().now().to_msg()
    goal.pose.pose.position.x = a.x
    goal.pose.pose.position.y = a.y
    goal.pose.pose.orientation.z = math.sin(a.yaw/2.0)
    goal.pose.pose.orientation.w = math.cos(a.yaw/2.0)
    t0 = time.monotonic()
    fut = n.client.send_goal_async(goal)
    rclpy.spin_until_future_complete(n, fut, timeout_sec=10.0)
    handle = fut.result()
    if handle is None or not handle.accepted:
        print("REJECTED"); return
    print("goal", a.x, a.y, a.yaw, "start_truth", [round(v,3) for v in n.truth] if n.truth else None)
    res_fut = handle.get_result_async()
    canceled = False
    while not res_fut.done():
        rclpy.spin_once(n, timeout_sec=0.02)
        if a.cancel_after > 0 and not canceled and time.monotonic() - t0 >= a.cancel_after:
            print("cancel_requested_after", round(time.monotonic()-t0, 2))
            cf = handle.cancel_goal_async()
            rclpy.spin_until_future_complete(n, cf, timeout_sec=5.0)
            cr = cf.result()
            print("cancel_ack", cr is not None and len(cr.goals_canceling) > 0)
            canceled = True
        if time.monotonic() - t0 > a.timeout:
            print("TIMEOUT"); break
    status = res_fut.result().status if res_fut.done() else None
    wall = time.monotonic() - t0
    truth = n.truth
    err = math.hypot(truth[0]-a.x, truth[1]-a.y) if truth else None
    herr = abs(math.atan2(math.sin(truth[2]-a.yaw), math.cos(truth[2]-a.yaw))) if truth else None
    amcl_err = None
    if n.amcl and truth:
        amcl_err = math.hypot(n.amcl[0]-truth[0], n.amcl[1]-truth[1])
    print("status", status, "wall_s", round(wall,2), "truth", [round(v,3) for v in truth] if truth else None,
          "err_m", round(err,3) if err is not None else None, "heading_err", round(herr,3) if herr is not None else None,
          "amcl_err", round(amcl_err,3) if amcl_err is not None else None)
    # hold zero for one second and check truth motion
    z = Twist()
    t1 = n.truth
    end = time.monotonic() + 1.0
    while time.monotonic() < end:
        n.cmd.publish(z)
        rclpy.spin_once(n, timeout_sec=0.02)
    if t1 and n.truth:
        print("stop_displacement_m", round(math.hypot(n.truth[0]-t1[0], n.truth[1]-t1[1]), 4))
    rclpy.shutdown()

if __name__ == "__main__":
    main()
