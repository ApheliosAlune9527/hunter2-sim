#!/usr/bin/env python3
"""Teleport the simulated HUNTER to a known pose and seed AMCL with a tight prior."""
import math, subprocess, sys, time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry

WORLD = "hz_lab_2d"
MODEL = "hz_hunter_full"

def yaw_of(q):
    return math.atan2(2.0*(q.w*q.z+q.x*q.y), 1.0-2.0*(q.y*q.y+q.z*q.z))

class N(Node):
    def __init__(self):
        super().__init__("reset_and_seed")
        self.pub = self.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)
        self.amcl = None; self.truth = None; self.cov = None
        self.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self.a_cb, 10)
        self.create_subscription(Odometry, "/ground_truth", self.t_cb, 10)
    def a_cb(self, m):
        p = m.pose.pose
        self.amcl = (p.position.x, p.position.y, yaw_of(p.orientation)); self.cov = m.pose.covariance
    def t_cb(self, m):
        p = m.pose.pose
        self.truth = (p.position.x, p.position.y, yaw_of(p.orientation))

def main():
    x, y, yaw = map(float, sys.argv[1:4])
    cov = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0025
    req = ('name: "%s", position: {x: %.6f, y: %.6f, z: 0.165}, '
           'orientation: {x: 0, y: 0, z: %.6f, w: %.6f}' % (MODEL, x, y, math.sin(yaw/2), math.cos(yaw/2)))
    r = subprocess.run(["ign", "service", "-s", "/world/%s/set_pose" % WORLD,
                        "--reqtype", "ignition.msgs.Pose", "--reptype", "ignition.msgs.Boolean",
                        "--timeout", "4000", "--req", req], capture_output=True, text=True, timeout=20)
    print("teleport rc", r.returncode, r.stdout.strip(), r.stderr.strip()[:200])
    rclpy.init()
    n = N()
    for _ in range(20):
        rclpy.spin_once(n, timeout_sec=0.05)
    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = "map"
    msg.pose.pose.position.x = x; msg.pose.pose.position.y = y
    msg.pose.pose.orientation.z = math.sin(yaw/2); msg.pose.pose.orientation.w = math.cos(yaw/2)
    msg.pose.covariance[0] = cov; msg.pose.covariance[7] = cov; msg.pose.covariance[35] = cov
    # A single publish can be dropped while AMCL is still transforming its
    # previous estimate: pipeline_v9 then ran with the pose from the run before
    # it and every plan failed from the wrong start.  Verify and retry.
    ok = False
    for attempt in range(1, 4):
        for _ in range(5):
            msg.header.stamp = n.get_clock().now().to_msg()
            n.pub.publish(msg)
            end = time.time() + 0.2
            while time.time() < end:
                rclpy.spin_once(n, timeout_sec=0.02)
        end = time.time() + 4.0
        while time.time() < end:
            rclpy.spin_once(n, timeout_sec=0.05)
        if n.amcl and n.truth:
            dx = n.amcl[0]-n.truth[0]; dy = n.amcl[1]-n.truth[1]
            err = math.hypot(dx, dy)
            print("attempt", attempt, "amcl", [round(v,4) for v in n.amcl],
                  "truth", [round(v,4) for v in n.truth])
            print("error_m", round(err,4), "dxy", round(dx,4), round(dy,4),
                  "cov_xy", round(n.cov[0],5), round(n.cov[7],5), "cov_yaw", round(n.cov[35],5))
            if err <= 0.05:
                ok = True
                break
        else:
            print("attempt", attempt, "no amcl/truth pose")
    print("seed_ok", ok)
    rclpy.shutdown()
    if not ok:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
