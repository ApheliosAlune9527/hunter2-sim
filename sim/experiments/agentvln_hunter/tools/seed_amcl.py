#!/usr/bin/env python3
import math, sys, time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry

def yaw_of(q):
    return math.atan2(2.0*(q.w*q.z+q.x*q.y), 1.0-2.0*(q.y*q.y+q.z*q.z))

class Seed(Node):
    def __init__(self):
        super().__init__("seed_amcl")
        self.pub = self.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)
        self.amcl = None
        self.truth = None
        self.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self.a_cb, 10)
        self.create_subscription(Odometry, "/ground_truth", self.t_cb, 10)
    def a_cb(self, m):
        p = m.pose.pose
        self.amcl = (p.position.x, p.position.y, yaw_of(p.orientation), m.pose.covariance)
    def t_cb(self, m):
        p = m.pose.pose
        self.truth = (p.position.x, p.position.y, yaw_of(p.orientation))

def main():
    x, y, yaw = map(float, sys.argv[1:4])
    cov = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0025
    rclpy.init()
    n = Seed()
    # let subscriptions connect
    for _ in range(20):
        rclpy.spin_once(n, timeout_sec=0.05)
    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = "map"
    msg.header.stamp = n.get_clock().now().to_msg()
    msg.pose.pose.position.x = x
    msg.pose.pose.position.y = y
    msg.pose.pose.orientation.z = math.sin(yaw/2.0)
    msg.pose.pose.orientation.w = math.cos(yaw/2.0)
    msg.pose.covariance[0] = cov
    msg.pose.covariance[7] = cov
    msg.pose.covariance[35] = cov
    n.pub.publish(msg)
    print("seeded", x, y, yaw, "cov", cov)
    end = time.time() + 5.0
    while time.time() < end:
        rclpy.spin_once(n, timeout_sec=0.05)
    if n.amcl and n.truth:
        dx = n.amcl[0]-n.truth[0]; dy = n.amcl[1]-n.truth[1]
        print("amcl", [round(v,4) for v in n.amcl[:3]], "truth", [round(v,4) for v in n.truth])
        print("error_m", round(math.hypot(dx,dy),4), "dxy", round(dx,4), round(dy,4),
              "cov_xy", round(n.amcl[3][0],5), round(n.amcl[3][7],5), "cov_yaw", round(n.amcl[3][35],5))
    else:
        print("no pose", n.amcl is not None, n.truth is not None)
    rclpy.shutdown()

if __name__ == "__main__":
    main()
