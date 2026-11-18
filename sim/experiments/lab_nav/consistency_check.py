"""Check that clock, odometry, scan and TF agree in time while the robot moves.

Static agreement is easy and proves little: what matters is whether the sensors
stay aligned when the vehicle is driving and the render loop is busy.  This
script drives a short straight segment, records every arrival stamped against
the simulated clock, and reports, per topic, how old each message already is
when it reaches ROS.

`age` is `clock_now - message_stamp`, both in simulated time, so a positive age
means "the message describes a pose the robot has already left".
"""
import argparse
import json
import math
import time

import rclpy
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from rosgraph_msgs.msg import Clock
from tf2_msgs.msg import TFMessage


def stamp_of(msg):
    h = msg.header.stamp
    return h.sec + h.nanosec * 1e-9


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--speed', type=float, default=0.15)
    ap.add_argument('--seconds', type=float, default=12.0)
    ap.add_argument('--out', default='')
    args = ap.parse_args()

    rclpy.init(args=[])
    node = rclpy.create_node('consistency_check')
    cmd = node.create_publisher(Twist, '/cmd_vel', 10)
    state = {'clock': None}
    rows = {'scan': [], 'odom': [], 'ground_truth': [], 'tf': []}

    def now_sim():
        return state['clock']

    def on_clock(msg):
        state['clock'] = msg.clock.sec + msg.clock.nanosec * 1e-9

    def rec(name):
        def cb(msg):
            clock = now_sim()
            if clock is None:
                return
            if name == 'tf':
                stamps = [t.header.stamp for t in msg.transforms
                          if t.child_frame_id == 'base_link']
                if not stamps:
                    return
                s = stamps[0]
                age = clock - (s.sec + s.nanosec * 1e-9)
            else:
                age = clock - stamp_of(msg)
            rows[name].append(round(age, 4))
        return cb

    keep = [
        node.create_subscription(Clock, '/clock', on_clock, qos_profile_sensor_data),
        node.create_subscription(LaserScan, '/scan', rec('scan'), qos_profile_sensor_data),
        node.create_subscription(Odometry, '/odom', rec('odom'), qos_profile_sensor_data),
        node.create_subscription(Odometry, '/ground_truth', rec('ground_truth'),
                                 qos_profile_sensor_data),
        node.create_subscription(TFMessage, '/tf', rec('tf'), qos_profile_sensor_data),
    ]

    start = time.monotonic()
    deadline = start + args.seconds
    msg = Twist()
    msg.linear.x = args.speed
    while time.monotonic() < deadline:
        cmd.publish(msg)
        rclpy.spin_once(node, timeout_sec=0.05)
    stop = Twist()
    for _ in range(10):
        cmd.publish(stop)
        rclpy.spin_once(node, timeout_sec=0.02)

    def stats(values):
        if not values:
            return {'count': 0}
        v = sorted(values)
        n = len(v)
        return {'count': n,
                'age_mean_ms': round(1000 * sum(v) / n, 1),
                'age_p50_ms': round(1000 * v[n // 2], 1),
                'age_p95_ms': round(1000 * v[int(0.95 * (n - 1))], 1),
                'age_max_ms': round(1000 * v[-1], 1),
                'age_min_ms': round(1000 * v[0], 1)}

    report = {'speed_mps': args.speed, 'window_s': args.seconds,
              'per_topic_age': {k: stats(v) for k, v in rows.items()},
              'note': 'age = simulated clock at arrival minus the message stamp'}

    # Skew between the scan and the nearest odometry sample in simulated time.
    node.destroy_node()
    rclpy.shutdown()
    text = json.dumps(report, indent=1, ensure_ascii=False)
    print(text)
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main()
