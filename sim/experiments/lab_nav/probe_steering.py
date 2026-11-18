"""Probe how the front steering joints respond to a steady angular command."""
import math
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState

NS = '/hz_sim/lab'
V = 0.10
W = 0.10          # delta = atan(L*w/v) = atan(0.65) -> clamped to steering_limit 0.4

rclpy.init()
node = Node('steer_probe')
pub = node.create_publisher(Twist, f'{NS}/cmd_vel', 10)
latest = {}
qos = QoSProfile(depth=20, reliability=ReliabilityPolicy.BEST_EFFORT)


def on_joints(msg):
    global latest
    latest = dict(zip(msg.name, msg.position))


node.create_subscription(JointState, f'{NS}/joint_states', on_joints, qos)

msg = Twist()
msg.linear.x = V
msg.angular.z = W
start = time.time()
rows = []
while time.time() - start < 25:
    pub.publish(msg)
    rclpy.spin_once(node, timeout_sec=0.02)
    if latest:
        rows.append((round(time.time() - start, 1),
                     round(latest.get('front_left_steering_joint', float('nan')), 4),
                     round(latest.get('front_right_steering_joint', float('nan')), 4)))
pub.publish(Twist())
for row in rows[::15]:
    print('t=%5.1f  left=%+.4f  right=%+.4f' % row)
print('expected outer=0.318 inner=0.400 (clamped) for R=1.669 m')
node.destroy_node()
rclpy.shutdown()
