"""Send one nav goal and print what the controller actually commands.

Used to tell apart "the stack drives the wrong way" from "the vehicle cannot
follow the path": the timeline pairs each cmd_vel with the ground-truth pose.
"""
import sys
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node


class Diag(Node):
    def __init__(self):
        super().__init__('nav_diag')
        self.truth = None
        self.cmd = (0.0, 0.0)
        self.create_subscription(Odometry, '/ground_truth', self.on_truth, 30)
        self.create_subscription(Twist, '/cmd_vel', self.on_cmd, 30)
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

    def on_truth(self, msg):
        p = msg.pose.pose
        self.truth = (p.position.x, p.position.y)

    def on_cmd(self, msg):
        self.cmd = (msg.linear.x, msg.angular.z)


def main():
    x, y = float(sys.argv[1]), float(sys.argv[2])
    seconds = float(sys.argv[3]) if len(sys.argv) > 3 else 12.0
    rclpy.init()
    node = Diag()
    for _ in range(20):
        rclpy.spin_once(node, timeout_sec=0.1)
    if not node.client.wait_for_server(timeout_sec=10.0):
        print('action server unavailable', flush=True)
        return
    goal = NavigateToPose.Goal()
    goal.pose.header.frame_id = 'map'
    goal.pose.header.stamp = node.get_clock().now().to_msg()
    goal.pose.pose.position.x = x
    goal.pose.pose.position.y = y
    goal.pose.pose.orientation.w = 1.0
    fut = node.client.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, fut, timeout_sec=10.0)
    handle = fut.result()
    if handle is None or not handle.accepted:
        print('goal rejected', flush=True)
        return
    print('goal accepted -> (%.2f, %.2f)' % (x, y), flush=True)

    start = time.time()
    while time.time() - start < seconds:
        rclpy.spin_once(node, timeout_sec=0.05)
        if int((time.time() - start) * 2) != int((time.time() - start - 0.06) * 2):
            t = node.truth
            print('t=%5.1f truth=(%.2f, %.2f) cmd=(%+.3f, %+.3f)'
                  % (time.time() - start, t[0] if t else float('nan'),
                     t[1] if t else float('nan'), node.cmd[0], node.cmd[1]), flush=True)
    node.client.server_is_ready()


if __name__ == '__main__':
    main()
