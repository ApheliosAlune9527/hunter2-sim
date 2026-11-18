"""Task 2 acceptance: stopping must settle below a small velocity tolerance.

Criterion: after commanding zero, the odometry speed stays under 0.005 m/s and the
ground-truth displacement stays under 5 mm for 2.0 simulation seconds.
"""
import json
import math
import time

import rclpy

import test_drive_baseline as base

TOL_LINEAR = 0.005      # m/s
TOL_ANGULAR = 0.02      # rad/s
TOL_DISPLACEMENT = 0.005  # m
HOLD_SIM_SECONDS = 2.0


def main():
    rclpy.init()
    node = base.Drive()
    report = {}
    if not node.wait_ready(90.0):
        report['ok'] = False
        report['error'] = 'topics not ready'
        print(json.dumps(report))
        return 1

    base.set_pose(2.535, 12.885, 2.7053)
    node.spin_for(2.0)
    node.command(0.05, 0.0, 6.0)          # get moving
    moving = node.state()
    node.command(0.0, 0.0, 0.4)           # command stop

    # Wait until the commanded zero has had time to act, then start the hold window.
    start = node.state()
    start_truth = base.read_truth()
    deadline = start['sim_time'] + HOLD_SIM_SECONDS
    samples = []
    while True:
        node.pub.publish(base.Twist())
        rclpy.spin_once(node, timeout_sec=0.02)
        now = node.state()
        samples.append({'t': round(now['sim_time'], 3),
                        'vx': round(now['vx'], 5), 'wz': round(now['wz'], 5)})
        if now['sim_time'] >= deadline:
            break
    end = node.state()
    end_truth = base.read_truth()

    drift = math.hypot(end['x'] - start['x'], end['y'] - start['y'])
    truth_drift = (math.hypot(end_truth['x'] - start_truth['x'], end_truth['y'] - start_truth['y'])
                   if 'x' in end_truth and 'x' in start_truth else None)
    max_v = max(abs(s['vx']) for s in samples)
    max_w = max(abs(s['wz']) for s in samples)

    report.update({
        'tolerance': {'linear_mps': TOL_LINEAR, 'angular_rps': TOL_ANGULAR,
                      'displacement_m': TOL_DISPLACEMENT, 'hold_sim_seconds': HOLD_SIM_SECONDS},
        'speed_before_stop_mps': round(moving['vx'], 4),
        'samples': len(samples),
        'max_abs_linear_mps_in_hold': round(max_v, 5),
        'max_abs_angular_rps_in_hold': round(max_w, 5),
        'odom_displacement_m': round(drift, 5),
        'truth_displacement_m': round(truth_drift, 5) if truth_drift is not None else None,
        'sim_seconds_held': round(end['sim_time'] - start['sim_time'], 3),
    })
    report['ok'] = (max_v < TOL_LINEAR and max_w < TOL_ANGULAR and drift < TOL_DISPLACEMENT
                    and (truth_drift is None or truth_drift < TOL_DISPLACEMENT))
    print(json.dumps(report, indent=2))
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
