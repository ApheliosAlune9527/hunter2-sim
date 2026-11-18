"""Measure the actual turning radius in open space.

Places the vehicle at the calibration pose, drives a steady arc, samples ground
truth along the way and fits a circle. The endpoint-only estimate used earlier is
sensitive to where the phase happens to stop, so points are fitted instead.
"""
import json
import math
import subprocess
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

import test_drive_baseline as base

NS = '/hz_sim/lab'
POSE = (2.535, 12.885, 2.7053)
WHEEL_BASE = 0.650
STEER_LIMIT = 0.4
V = 0.05
R_EXPECTED = WHEEL_BASE / math.sin(STEER_LIMIT)
OMEGA = V / R_EXPECTED


def fit_circle(points):
    """Algebraic (Kasa) circle fit; returns centre and radius."""
    n = len(points)
    sx = sum(p[0] for p in points) / n
    sy = sum(p[1] for p in points) / n
    u = [p[0] - sx for p in points]
    v = [p[1] - sy for p in points]
    suu = sum(a * a for a in u)
    svv = sum(b * b for b in v)
    suv = sum(a * b for a, b in zip(u, v))
    suuu = sum(a ** 3 for a in u)
    svvv = sum(b ** 3 for b in v)
    suvv = sum(a * b * b for a, b in zip(u, v))
    svuu = sum(b * a * a for a, b in zip(u, v))
    det = suu * svv - suv * suv
    if abs(det) < 1e-12:
        return None
    bu = 0.5 * (suuu + suvv)
    bv = 0.5 * (svvv + svuu)
    uc = (bu * svv - bv * suv) / det
    vc = (bv * suu - bu * suv) / det
    r = math.sqrt(uc * uc + vc * vc + (suu + svv) / n)
    return {'cx': sx + uc, 'cy': sy + vc, 'radius': r}


def main():
    rclpy.init()
    node = base.Drive()
    report = {'expected_radius_m': round(R_EXPECTED, 3),
              'commanded_linear_mps': V, 'commanded_angular_rps': round(OMEGA, 5)}
    report['set_pose_reply'] = base.set_pose(*POSE)
    node.spin_for(3.0)
    report['placed_truth'] = base.read_truth()

    msg = Twist()
    msg.linear.x = V
    msg.angular.z = OMEGA
    points = []
    t0 = time.time()
    next_sample = 0.0
    while time.time() - t0 < 150:
        node.pub.publish(msg)
        rclpy.spin_once(node, timeout_sec=0.02)
        elapsed = time.time() - t0
        if elapsed >= next_sample:
            truth = base.read_truth()
            if 'x' in truth:
                points.append((truth['x'], truth['y'], truth['yaw']))
            next_sample = elapsed + 6.0
        if len(points) >= 9:
            break
    node.command(0.0, 0.0, 0.5)
    node.spin_for(1.0)
    report['points'] = [{'x': round(p[0], 3), 'y': round(p[1], 3), 'yaw': round(p[2], 4)}
                        for p in points]
    report['end_truth'] = base.read_truth()

    if len(points) >= 4:
        fit = fit_circle([(p[0], p[1]) for p in points])
        dyaw = abs(math.atan2(math.sin(points[-1][2] - points[0][2]),
                              math.cos(points[-1][2] - points[0][2])))
        arc = 0.0
        for a, b in zip(points, points[1:]):
            arc += math.hypot(b[0] - a[0], b[1] - a[1])
        report['fit'] = {k: round(v, 3) for k, v in fit.items()} if fit else None
        report['dyaw_rad'] = round(dyaw, 4)
        report['arc_length_m'] = round(arc, 4)
        report['radius_from_arc_over_angle'] = round(arc / dyaw, 3) if dyaw > 1e-3 else None

    print(json.dumps(report, indent=2, ensure_ascii=False))
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
