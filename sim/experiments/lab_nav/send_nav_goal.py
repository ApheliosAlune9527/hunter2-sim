"""Send one NavigateToPose goal and record what actually happened.

Records the ground-truth trajectory, the path returned by the planner and the
final arrival error, so acceptance never depends on a node merely being active.
"""
import argparse
import json
import math
import time

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry, Path
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from tf2_ros import Buffer, TransformListener


class GoalTest(Node):
    def __init__(self):
        super().__init__('nav_goal_test', parameter_overrides=[])
        self.truth = None
        self.path = None
        self.track = []
        self.create_subscription(Odometry, '/hz_sim/lab/ground_truth', self.on_truth, 20)
        self.create_subscription(Path, '/plan', self.on_path, 5)
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

    def on_truth(self, msg):
        p = msg.pose.pose
        self.truth = {'t': msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                      'x': p.position.x, 'y': p.position.y,
                      'yaw': math.atan2(2 * (p.orientation.w * p.orientation.z
                                             + p.orientation.x * p.orientation.y),
                                        1 - 2 * (p.orientation.y ** 2 + p.orientation.z ** 2))}
        self.track.append(self.truth)

    def on_path(self, msg):
        self.path = [(p.pose.position.x, p.pose.position.y) for p in msg.poses]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--x', type=float, required=True)
    ap.add_argument('--y', type=float, required=True)
    ap.add_argument('--yaw', type=float, default=0.0)
    ap.add_argument('--timeout', type=float, default=300.0, help='wall-clock seconds')
    args = ap.parse_args()

    rclpy.init()
    node = GoalTest()
    if not node.client.wait_for_server(timeout_sec=60.0):
        print(json.dumps({'ok': False, 'error': 'navigate_to_pose server unavailable'}))
        return 1

    goal = NavigateToPose.Goal()
    goal.pose = PoseStamped()
    goal.pose.header.frame_id = 'map'
    goal.pose.header.stamp = node.get_clock().now().to_msg()
    goal.pose.pose.position.x = args.x
    goal.pose.pose.position.y = args.y
    goal.pose.pose.orientation.z = math.sin(args.yaw / 2.0)
    goal.pose.pose.orientation.w = math.cos(args.yaw / 2.0)

    start = None
    for _ in range(200):          # wait for the first ground-truth sample
        rclpy.spin_once(node, timeout_sec=0.1)
        if node.truth is not None:
            start = dict(node.truth)
            break
    send = node.client.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, send, timeout_sec=30.0)
    handle = send.result()
    if handle is None or not handle.accepted:
        print(json.dumps({'ok': False, 'error': 'goal rejected'}))
        return 1

    result_future = handle.get_result_async()
    t0 = time.time()
    status = None
    while time.time() - t0 < args.timeout:
        rclpy.spin_once(node, timeout_sec=0.1)
        if result_future.done():
            status = result_future.result().status
            break

    end = dict(node.truth) if node.truth else None
    out = {
        'goal': {'x': args.x, 'y': args.y, 'yaw': args.yaw},
        'accepted': True,
        'status': int(status) if status is not None else None,
        'succeeded': status == GoalStatus.STATUS_SUCCEEDED,
        'start': start,
        'end': end,
        'plan_waypoints': len(node.path) if node.path else 0,
        'truth_samples': len(node.track),
    }
    if start and end:
        out['final_error_m'] = round(math.hypot(end['x'] - args.x, end['y'] - args.y), 3)
        out['path_length_m'] = round(sum(
            math.hypot(b['x'] - a['x'], b['y'] - a['y'])
            for a, b in zip(node.track, node.track[1:])), 3)
        out['yaw_error_rad'] = round(abs(math.atan2(math.sin(end['yaw'] - args.yaw),
                                                    math.cos(end['yaw'] - args.yaw))), 3)
    with open('/mnt/d/rob-memory/outputs/lab_nav_20261105/nav_goal_track.json', 'w') as f:
        json.dump({'summary': out, 'track': node.track}, f, indent=1)
    print(json.dumps(out, indent=2))
    node.destroy_node()
    rclpy.shutdown()
    return 0 if out['succeeded'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
