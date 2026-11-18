#!/usr/bin/env python3
"""Measure the Gazebo sim-clock rate: simulated seconds per wall second."""
import argparse
import json
import time

import rclpy
from rclpy.node import Node
from rosgraph_msgs.msg import Clock


class Rate(Node):
    def __init__(self):
        super().__init__('clock_rate')
        self.ns = None
        self.create_subscription(Clock, '/clock', self.cb, 10)

    def cb(self, msg):
        self.ns = msg.clock.sec * 1_000_000_000 + msg.clock.nanosec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=10.0)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    rclpy.init()
    n = Rate()
    while n.ns is None:
        rclpy.spin_once(n, timeout_sec=0.05)
    t0, s0 = time.monotonic(), n.ns
    while time.monotonic() - t0 < args.seconds:
        rclpy.spin_once(n, timeout_sec=0.02)
    t1, s1 = time.monotonic(), n.ns
    wall = t1 - t0
    sim = (s1 - s0) / 1e9
    out = {'wall_s': round(wall, 3), 'sim_s': round(sim, 3), 'rate': round(sim / wall, 3)}
    print(json.dumps(out))
    with open(args.out, 'w') as f:
        json.dump(out, f)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
