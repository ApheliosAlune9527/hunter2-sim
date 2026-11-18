"""Send one goal and watch the controller's own pose estimate against the truth.

Written because one evaluation round reported SUCCEEDED while the vehicle was
still 1.42 m from the goal.  A success that the truth does not confirm is either
a bookkeeping bug or a localisation offset, and the only way to tell them apart
is to print, at every step, where the controller thinks it is (TF map->base_link)
next to where it actually is (/ground_truth).
"""
import math
import sys
import time
from pathlib import Path

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, Twist
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_nav_eval import set_pose  # noqa: E402

SPAWN = (-0.21, -0.77, 0.165, 0.0)


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class Probe(Node):
    def __init__(self):
        super().__init__('probe_goal_tf')
        self.truth = None
        self.cmd = (0.0, 0.0)
        self.gt_count = 0
        self.gt_stamp = 0.0
        self.odom_pose = None
        self.buf = Buffer()
        self.listener = TransformListener(self.buf, self)
        self.create_subscription(Odometry, '/ground_truth', self.on_truth, qos_profile_sensor_data)
        self.create_subscription(Twist, '/cmd_vel', self.on_cmd, 10)
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

    def on_truth(self, msg):
        p = msg.pose.pose
        self.truth = (p.position.x, p.position.y, yaw_of(p.orientation))
        self.gt_count += 1
        self.gt_stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self.odom_pose = (p.position.x, p.position.y)

    def on_cmd(self, msg):
        self.cmd = (msg.linear.x, msg.angular.z)

    def estimate(self):
        try:
            tr = self.buf.lookup_transform('map', 'base_link', Time())
        except Exception as exc:  # noqa: BLE001 - report, do not crash
            return None, str(exc)
        t = tr.transform.translation
        return (t.x, t.y, yaw_of(tr.transform.rotation)), None


def main():
    x, y, yaw = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
    budget = float(sys.argv[4]) if len(sys.argv) > 4 else 40.0
    rclpy.init()
    node = Probe()
    try:
        set_pose(*SPAWN)
        time.sleep(2.0)
        while node.truth is None:
            rclpy.spin_once(node, timeout_sec=0.2)
        node.client.wait_for_server(timeout_sec=10.0)
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = node.get_clock().now().to_msg()
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        goal.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(yaw / 2.0)
        send = node.client.send_goal_async(goal)
        rclpy.spin_until_future_complete(node, send, timeout_sec=10.0)
        handle = send.result()
        if handle is None or not handle.accepted:
            print('goal rejected')
            return
        result = handle.get_result_async()
        t0 = node.get_clock().now()
        next_log = 0.0
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.05)
            elapsed = (node.get_clock().now() - t0).nanoseconds * 1e-9
            if elapsed > budget:
                print('budget exhausted')
                break
            if elapsed >= next_log:
                next_log += 0.5
                est, err = node.estimate()
                tx, ty, tyaw = node.truth
                if est is None:
                    print('t=%6.2f truth=(%6.3f,%6.3f,%5.2f) tf=UNAVAILABLE %s'
                          % (elapsed, tx, ty, tyaw, err))
                else:
                    gap = math.hypot(est[0] - tx, est[1] - ty)
                    now_sim = node.get_clock().now().nanoseconds * 1e-9
                    print('t=%6.2f truth=(%6.3f,%6.3f,%5.2f) est=(%6.3f,%6.3f,%5.2f) '
                          'gap=%5.3f dist_to_goal=%5.3f cmd=(%5.2f,%5.2f) '
                          'gt_n=%d gt_age=%.2f odom=(%.2f,%.2f)'
                          % (elapsed, tx, ty, tyaw, est[0], est[1], est[2], gap,
                             math.hypot(x - tx, y - ty), node.cmd[0], node.cmd[1],
                             node.gt_count, now_sim - node.gt_stamp,
                             node.odom_pose[0], node.odom_pose[1]))
            if result.done():
                st = result.result().status
                print('action status', st)
                break
        est, _ = node.estimate()
        tx, ty, _ = node.truth
        print('FINAL truth_dist=%.3f est_dist=%.3f'
              % (math.hypot(x - tx, y - ty),
                 math.hypot(x - est[0], y - est[1]) if est else float('nan')))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
