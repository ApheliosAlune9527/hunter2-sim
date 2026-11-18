
import json, math, subprocess
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped

class N(Node):
    def __init__(self):
        super().__init__('pose_probe')
        self.p = None
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self.cb, 10)
    def cb(self, m):
        self.p = m

rclpy.init()
n = N()
import time
t0 = time.time()
while n.p is None and time.time() - t0 < 10:
    rclpy.spin_once(n, timeout_sec=0.2)
if n.p is None:
    print('NO_AMCL_POSE')
else:
    q = n.p.pose.pose.orientation
    yaw = math.atan2(2*(q.w*q.z + q.x*q.y), 1 - 2*(q.y*q.y + q.z*q.z))
    print('amcl', round(n.p.pose.pose.position.x,4), round(n.p.pose.pose.position.y,4), round(yaw,4))
out = subprocess.run(['ign','model','-m','hz_hunter_full','-p'], capture_output=True, text=True).stdout
print(out.strip()[:400])
rclpy.shutdown()
