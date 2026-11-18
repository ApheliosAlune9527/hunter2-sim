"""Low-speed drive baseline for the lab world (handoff task 2).

Runs from a wide-open calibration pose so a straight line never ends on a wall.
For every phase it records ground truth (Gazebo /pose/info) before and after and
compares it with the odometry being tested.
"""
import argparse
import json
import math
import re
import subprocess
import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState, LaserScan

WORLD = 'hz_lab_2d'
MODEL = 'hz_hunter_full'
NS = '/hz_sim/lab'
WHEEL_BASE = 0.650
STEER_LIMIT = 0.4

_POSE_RE = re.compile(
    r'name:\s*"%s".*?position\s*\{\s*x:\s*([-\d.eE]+)\s*y:\s*([-\d.eE]+)\s*z:\s*([-\d.eE]+).*?'
    r'orientation\s*\{\s*x:\s*([-\d.eE]+)\s*y:\s*([-\d.eE]+)\s*z:\s*([-\d.eE]+)\s*w:\s*([-\d.eE]+)'
    % MODEL, re.S)


def read_truth():
    try:
        out = subprocess.run(['ign', 'topic', '-e', '-n', '1', '-t', f'/world/{WORLD}/pose/info'],
                             capture_output=True, text=True, timeout=20).stdout
    except Exception as exc:                       # noqa: BLE001
        return {'error': str(exc)}
    m = _POSE_RE.search(out)
    if not m:
        return {'error': 'pose not found'}
    x, y, z, qx, qy, qz, qw = (float(v) for v in m.groups())
    return {'x': x, 'y': y, 'z': z,
            'yaw': math.atan2(2.0 * (qw * qz + qx * qy), 1.0 - 2.0 * (qy * qy + qz * qz))}


def set_pose(x, y, yaw, z=0.165):
    req = ('name: "%s", position: {x: %.4f, y: %.4f, z: %.4f}, '
           'orientation: {x: 0, y: 0, z: %.6f, w: %.6f}'
           % (MODEL, x, y, z, math.sin(yaw / 2.0), math.cos(yaw / 2.0)))
    out = subprocess.run(['ign', 'service', '-s', f'/world/{WORLD}/set_pose',
                          '--reqtype', 'ignition.msgs.Pose',
                          '--reptype', 'ignition.msgs.Boolean',
                          '--timeout', '8000', '--req', req],
                         capture_output=True, text=True, timeout=30)
    return out.stdout.strip()


def wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


class Drive(Node):
    def __init__(self):
        super().__init__('lab_drive_baseline')
        qos = QoSProfile(depth=20, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.pub = self.create_publisher(Twist, f'{NS}/cmd_vel', 10)
        self.odom = self.scan = self.joints = None
        self.create_subscription(Odometry, f'{NS}/odom', self._odom, qos)
        self.create_subscription(LaserScan, f'{NS}/scan', self._scan, qos)
        self.create_subscription(JointState, f'{NS}/joint_states', self._joints, qos)

    def _odom(self, msg):
        self.odom = msg

    def _scan(self, msg):
        self.scan = msg

    def _joints(self, msg):
        self.joints = msg

    def spin_for(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.02)

    def command(self, linear, angular, seconds):
        msg = Twist()
        msg.linear.x = float(linear)
        msg.angular.z = float(angular)
        end = time.time() + seconds
        while time.time() < end:
            self.pub.publish(msg)
            rclpy.spin_once(self, timeout_sec=0.02)
        self.pub.publish(Twist())

    def wait_ready(self, timeout=90.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.odom and self.scan and self.joints:
                return True
        return False

    def state(self):
        p = self.odom.pose.pose
        return {'x': p.position.x, 'y': p.position.y,
                'yaw': math.atan2(2.0 * (p.orientation.w * p.orientation.z +
                                        p.orientation.x * p.orientation.y),
                                  1.0 - 2.0 * (p.orientation.y ** 2 + p.orientation.z ** 2)),
                'sim_time': self.odom.header.stamp.sec + self.odom.header.stamp.nanosec * 1e-9,
                'vx': self.odom.twist.twist.linear.x,
                'wz': self.odom.twist.twist.angular.z}

    def joint_map(self):
        return {n: round(p, 4) for n, p in zip(self.joints.name, self.joints.position)}


def run_phase(node, name, linear, angular, distance, max_sim_seconds, stop_heading=None):
    start_odom = node.state()
    start_truth = read_truth()
    node.command(linear, angular, 1.2)                 # leave the acceleration ramp
    after_ramp = node.state()
    sim_deadline = after_ramp['sim_time'] + max_sim_seconds
    travelled = 0.0
    while True:
        node.command(linear, angular, 0.3)
        now = node.state()
        travelled = math.hypot(now['x'] - after_ramp['x'], now['y'] - after_ramp['y'])
        if travelled >= distance or now['sim_time'] >= sim_deadline:
            break
        if stop_heading is not None:
            truth = read_truth()
            if 'yaw' in truth and abs(wrap(truth['yaw'] - start_truth.get('yaw', 0.0))) >= stop_heading:
                break
    node.command(0.0, 0.0, 0.6)
    end_odom = node.state()
    time.sleep(1.0)
    end_truth = read_truth()

    phase = {
        'phase': name,
        'commanded_linear_mps': linear,
        'commanded_angular_rps': angular,
        'target_distance_m': distance,
        'odom_start': start_odom,
        'odom_after_accel': after_ramp,
        'odom_end': end_odom,
        'truth_start': start_truth,
        'truth_end': end_truth,
        'steady_linear_mps': round(after_ramp['vx'], 4),
        'steady_angular_rps': round(after_ramp['wz'], 4),
        'sim_seconds_used': round(end_odom['sim_time'] - start_odom['sim_time'], 3),
        'joints_after': node.joint_map(),
    }
    if 'x' in start_truth and 'x' in end_truth:
        td = math.hypot(end_truth['x'] - start_truth['x'], end_truth['y'] - start_truth['y'])
        od = math.hypot(end_odom['x'] - start_odom['x'], end_odom['y'] - start_odom['y'])
        dyaw = wrap(end_truth['yaw'] - start_truth['yaw'])
        phase.update({
            'truth_distance_m': round(td, 4),
            'odom_distance_m': round(od, 4),
            'distance_relative_error': round(abs(od - td) / td, 4) if td > 1e-3 else None,
            'truth_dyaw_rad': round(dyaw, 4),
        })
        if abs(dyaw) > 1e-3 and td > 1e-3:
            phase['radius_from_truth_m'] = round(td / abs(dyaw), 3)
    return phase


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--x', type=float, default=2.535)
    ap.add_argument('--y', type=float, default=12.885)
    ap.add_argument('--yaw', type=float, default=2.7053)
    ap.add_argument('--straight', type=float, default=2.0)
    ap.add_argument('--reverse', type=float, default=1.0)
    ap.add_argument('--out', default='/mnt/d/rob-memory/outputs/lab_nav_20261105/drive_baseline.json')
    args = ap.parse_args()

    rclpy.init()
    node = Drive()
    report = {'world': WORLD, 'model': MODEL, 'namespace': NS}
    if not node.wait_ready(120.0):
        report.update({'ok': False, 'error': 'topics not ready'})
        Path(args.out).write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
        return 1

    s = node.scan
    finite = [r for r in s.ranges if math.isfinite(r) and r > 0]
    report['scan'] = {'beams': len(s.ranges), 'angle_min': round(s.angle_min, 4),
                      'angle_max': round(s.angle_max, 4), 'range_min': s.range_min,
                      'range_max': s.range_max, 'finite_beams': len(finite),
                      'min_finite_range': round(min(finite), 3) if finite else None}

    # Place the vehicle at the calibration pose and read back what actually happened.
    report['set_pose_reply'] = set_pose(args.x, args.y, args.yaw)
    node.spin_for(3.0)
    report['placed_truth'] = read_truth()

    phases = []
    phases.append(run_phase(node, 'straight_forward', 0.05, 0.0, args.straight, 90.0))
    node.spin_for(3.0)
    phases.append(run_phase(node, 'reverse', -0.05, 0.0, args.reverse, 60.0))
    node.spin_for(3.0)
    radius = WHEEL_BASE / math.sin(STEER_LIMIT)
    omega = 0.05 / radius
    phases.append(run_phase(node, 'turn_left_min_radius', 0.05, omega, 3.0, 120.0,
                            stop_heading=math.pi / 2))
    node.spin_for(4.0)
    phases.append(run_phase(node, 'turn_right_min_radius', 0.05, -omega, 3.0, 120.0,
                            stop_heading=math.pi / 2))
    node.command(0.0, 0.0, 1.0)
    node.spin_for(2.0)

    report['phases'] = phases
    report['expected_turn_radius_m'] = round(radius, 3)
    report['final_truth'] = read_truth()
    report['ok'] = all(p.get('truth_distance_m') is not None for p in phases)
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in report.items() if k != 'phases'}, indent=2,
                     ensure_ascii=False))
    for p in phases:
        print(f"{p['phase']}: odom={p.get('odom_distance_m')} truth={p.get('truth_distance_m')} "
              f"err={p.get('distance_relative_error')} dyaw={p.get('truth_dyaw_rad')} "
              f"R={p.get('radius_from_truth_m')} sim={p.get('sim_seconds_used')}")
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
