#!/usr/bin/env python3
"""One NavigateToPose run while recording RGB frames, truth pose and stop state.

This is the step-1 same-session check: Nav2 must drive to a known map pose while
the RGB-D camera keeps producing fresh frames, including frames captured after
the vehicle has moved.
"""
import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def stamp_ns(msg):
    return msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec


class Recorder(Node):
    def __init__(self):
        super().__init__('nav_camera_once')
        self.truth = None
        self.amcl = None
        self.bridge = CvBridge()
        self.frames = []
        self.snapshots = {}
        self.t0 = None
        self.create_subscription(Odometry, '/ground_truth', self.on_truth, 10)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self.on_amcl, 10)
        self.create_subscription(Image, '/hz_sim/agentvln/camera/image', self.on_image,
                                 qos_profile=qos_profile_sensor_data)
        self.cmd = self.create_publisher(Twist, '/cmd_vel', 10)
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

    def on_truth(self, msg):
        p = msg.pose.pose
        self.truth = (p.position.x, p.position.y, yaw_of(p.orientation))

    def on_amcl(self, msg):
        p = msg.pose.pose
        self.amcl = (p.position.x, p.position.y, yaw_of(p.orientation))

    def on_image(self, msg):
        if self.t0 is None:
            return
        elapsed = time.monotonic() - self.t0
        rgb = self.bridge.imgmsg_to_cv2(msg, desired_encoding='rgb8')
        self.frames.append({
            'stamp_s': stamp_ns(msg) / 1e9,
            'elapsed_s': round(elapsed, 3),
            'truth': list(self.truth) if self.truth else None,
            'mean_rgb': [round(float(v), 2) for v in rgb.reshape(-1, 3).mean(axis=0)],
        })
        if 'start' not in self.snapshots:
            self.snapshots['start'] = rgb.copy()
        elif 'mid' not in self.snapshots and elapsed >= 1.5:
            self.snapshots['mid'] = rgb.copy()
        self.snapshots['last'] = rgb.copy()


def spin_until(node, pred, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.02)
        if pred():
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('x', type=float)
    ap.add_argument('y', type=float)
    ap.add_argument('yaw', type=float)
    ap.add_argument('--timeout', type=float, default=75.0)
    ap.add_argument('--out', default='/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_step1/nav_camera')
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rclpy.init()
    n = Recorder()
    spin_until(n, lambda: n.truth is not None, 5.0)
    if not n.client.wait_for_server(timeout_sec=10.0):
        print(json.dumps({'error': 'action server unavailable'}))
        return 1
    goal = NavigateToPose.Goal()
    goal.pose.header.frame_id = 'map'
    goal.pose.header.stamp = n.get_clock().now().to_msg()
    goal.pose.pose.position.x = args.x
    goal.pose.pose.position.y = args.y
    goal.pose.pose.orientation.z = math.sin(args.yaw / 2.0)
    goal.pose.pose.orientation.w = math.cos(args.yaw / 2.0)
    n.t0 = time.monotonic()
    fut = n.client.send_goal_async(goal)
    rclpy.spin_until_future_complete(n, fut, timeout_sec=10.0)
    handle = fut.result()
    if handle is None or not handle.accepted:
        print(json.dumps({'error': 'goal rejected'}))
        return 1
    res_fut = handle.get_result_async()
    while not res_fut.done() and time.monotonic() - n.t0 < args.timeout:
        rclpy.spin_once(n, timeout_sec=0.02)
    status = res_fut.result().status if res_fut.done() else None
    wall = time.monotonic() - n.t0
    truth = n.truth
    err = math.hypot(truth[0] - args.x, truth[1] - args.y) if truth else None
    herr = abs(math.atan2(math.sin(truth[2] - args.yaw), math.cos(truth[2] - args.yaw))) if truth else None
    amcl_err = math.hypot(n.amcl[0] - truth[0], n.amcl[1] - truth[1]) if n.amcl and truth else None

    t1 = n.truth
    end = time.monotonic() + 1.0
    while time.monotonic() < end:
        n.cmd.publish(Twist())
        rclpy.spin_once(n, timeout_sec=0.02)
    stop_disp = math.hypot(n.truth[0] - t1[0], n.truth[1] - t1[1]) if t1 and n.truth else None

    for name, img in n.snapshots.items():
        cv2.imwrite(str(out / f'{name}.png'), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

    start_truth = n.frames[0]['truth'] if n.frames else None
    moving = []
    if start_truth:
        for f in n.frames:
            if f['truth'] and math.hypot(f['truth'][0] - start_truth[0], f['truth'][1] - start_truth[1]) > 0.05:
                moving.append(f)
    stamps = [f['stamp_s'] for f in n.frames]
    report = {
        'goal': {'x': args.x, 'y': args.y, 'yaw': args.yaw},
        'status': status,
        'status_is_success': status == 4,
        'wall_s': round(wall, 3),
        'final_truth': [round(v, 4) for v in truth] if truth else None,
        'final_error_m': round(err, 4) if err is not None else None,
        'heading_error_rad': round(herr, 4) if herr is not None else None,
        'amcl_error_m': round(amcl_err, 4) if amcl_err is not None else None,
        'stop_displacement_m': round(stop_disp, 4) if stop_disp is not None else None,
        'camera': {
            'frames': len(n.frames),
            'stamp_span_s': round(stamps[-1] - stamps[0], 3) if len(stamps) > 1 else 0.0,
            'frames_while_moving': len(moving),
            'moving_stamp_first': moving[0]['stamp_s'] if moving else None,
            'moving_stamp_last': moving[-1]['stamp_s'] if moving else None,
            'moving_elapsed_first': moving[0]['elapsed_s'] if moving else None,
            'moving_elapsed_last': moving[-1]['elapsed_s'] if moving else None,
            'max_displacement_m': round(max((math.hypot(f['truth'][0] - start_truth[0], f['truth'][1] - start_truth[1])
                                             for f in moving), default=0.0), 4) if start_truth else 0.0,
        },
        'files': {k: str(out / f'{k}.png') for k in n.snapshots},
        'frame_samples': n.frames[::max(1, len(n.frames) // 10)][:12],
    }
    (out / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
