"""Repeatable navigation evaluation: reset, drive, record, repeat.

Every round follows the same order so a failure is attributable:

1. put the vehicle back with ``set_pose``, publish a zero twist, then *read the
   pose back* and store the measured start.  ``reset {all: true}`` is banned
   here: it accumulated 1.2-1.45 mm per call in earlier tests.
2. send one ``NavigateToPose`` goal and wait on the simulated clock, not the
   wall clock, with a separate wall-clock watchdog.
3. record the ground-truth trajectory, the odometry trajectory, the planned
   path, contact events, success, final error and both elapsed times.

Contacts are read from ``/contacts`` (Gazebo Contact system).  Wheel
contact with the floor is filtered out: only pairs whose names do not both look
like a wheel are counted as collisions.
"""
import argparse
import csv
import json
import math
import subprocess
import time
from collections import deque
from pathlib import Path

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, Twist
from nav_msgs.msg import Odometry, Path as PathMsg
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from ros_gz_interfaces.msg import Contacts

OUT = Path('/mnt/d/rob-memory/outputs/lab_nav_20261105')
WORLD = 'hz_lab_2d'
MODEL = 'hz_hunter_full'
SPAWN = (-0.21, -0.77, 0.0)
WHEEL_HINTS = ('wheel', 'tire')

# The behaviour tree's xy_goal_tolerance.  A run only counts as a success if the
# truth agrees: one round returned SUCCEEDED while the vehicle was still 1.42 m
# away, because the controller's estimate had run away from the truth.
GOAL_TOL_M = 0.25
REINIT_AMCL = False


def yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def set_pose(x, y, z, yaw):
    req = (f'name: "{MODEL}", position: {{x: {x}, y: {y}, z: {z}}}, '
           f'orientation: {{x: 0, y: 0, z: {math.sin(yaw / 2)}, w: {math.cos(yaw / 2)}}}')
    subprocess.run(['ign', 'service', '-s', f'/world/{WORLD}/set_pose',
                    '--reqtype', 'ignition.msgs.Pose',
                    '--reptype', 'ignition.msgs.Boolean',
                    '--timeout', '5000', '--req', req],
                   capture_output=True, text=True, timeout=20)


def gazebo_pose():
    """Ground-truth pose straight from Gazebo, independent of ROS time."""
    proc = subprocess.Popen(['ign', 'topic', '-e', '-t', f'/world/{WORLD}/pose/info', '-n', '3'],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    out, _ = proc.communicate(timeout=20)
    idx = out.find(f'name: "{MODEL}"')
    if idx < 0:
        return None
    chunk = out[idx:]
    m = None
    for m in __import__('re').finditer(
            r'position\s*\{\s*x:\s*([-\d.e+]+)\s*y:\s*([-\d.e+]+)\s*z:\s*([-\d.e+]+)', chunk):
        pass
    if m is None:
        return None
    return tuple(float(v) for v in m.groups())


class Eval(Node):
    def __init__(self):
        super().__init__('nav_eval')
        qos = QoSProfile(depth=30, reliability=ReliabilityPolicy.RELIABLE)
        self.truth = None
        self.odom = None
        self.path = None
        self.contacts = deque(maxlen=2000)
        self.track = []
        self.create_subscription(Odometry, '/ground_truth', self.on_truth, 30)
        self.create_subscription(Odometry, '/odom', self.on_odom, 30)
        self.create_subscription(PathMsg, '/plan', self.on_plan, 5)
        self.create_subscription(Contacts, '/contacts', self.on_contacts, qos)
        self.cmd = self.create_publisher(Twist, '/cmd_vel', 10)
        self.init_pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

    def on_truth(self, msg):
        p = msg.pose.pose
        self.truth = {'t': msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                      'x': p.position.x, 'y': p.position.y, 'yaw': yaw_of(p.orientation)}
        self.track.append(dict(self.truth))

    def on_odom(self, msg):
        p = msg.pose.pose
        self.odom = {'x': p.position.x, 'y': p.position.y,
                     'v': msg.twist.twist.linear.x}

    def on_plan(self, msg):
        self.path = [(p.pose.position.x, p.pose.position.y) for p in msg.poses]

    def on_contacts(self, msg):
        for c in msg.contacts:
            names = tuple(n for n in (c.collision1.name, c.collision2.name) if n)
            joined = ' '.join(names).lower()
            if names and any(h in joined for h in WHEEL_HINTS) and 'floor' in joined:
                continue                     # normal tyre-on-floor contact
            self.contacts.append({'names': names, 't': msg.header.stamp.sec})


def spin_for(node, seconds, wall=False):
    end = time.time() + seconds
    while time.time() < end:
        rclpy.spin_once(node, timeout_sec=0.05)


def reset(node, settle_s=2.0):
    set_pose(SPAWN[0], SPAWN[1], 0.165, SPAWN[2])
    spin_for(node, 0.3)
    node.cmd.publish(Twist())            # clear any command the plugin still holds
    if REINIT_AMCL:                      # teleporting does not move the particle filter
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = node.get_clock().now().to_msg()
        msg.pose.pose.position.x = SPAWN[0]
        msg.pose.pose.position.y = SPAWN[1]
        msg.pose.pose.orientation.z = math.sin(SPAWN[2] / 2)
        msg.pose.pose.orientation.w = math.cos(SPAWN[2] / 2)
        msg.pose.covariance[0] = 0.25
        msg.pose.covariance[7] = 0.25
        msg.pose.covariance[35] = 0.0685
        for _ in range(5):
            node.init_pub.publish(msg)
            spin_for(node, 0.3)
        # the filter needs a few still cycles of scans before it is trusted;
        # without this the first goal was planned from a 1 m wrong estimate
        spin_for(node, 4.0)
    spin_for(node, settle_s)
    # wait until the truth stream is stationary, so the first goal of a fresh
    # stack is not planned from a pose that is still settling
    last = None
    end = time.time() + 6.0
    while time.time() < end:
        spin_for(node, 0.3)
        if node.truth:
            now = (node.truth['x'], node.truth['y'])
            if last and math.hypot(now[0] - last[0], now[1] - last[1]) < 0.002:
                break
            last = now
    pose = gazebo_pose()
    return {'requested': list(SPAWN), 'measured': list(pose) if pose else None}


def one_run(node, goal, budget_s, watchdog_s):
    reset_info = reset(node)
    node.track.clear()
    node.contacts.clear()
    node.path = None
    spin_for(node, 0.5)
    start = dict(node.truth) if node.truth else None

    g = NavigateToPose.Goal()
    g.pose = PoseStamped()
    g.pose.header.frame_id = 'map'
    g.pose.header.stamp = node.get_clock().now().to_msg()
    g.pose.pose.position.x = goal['x']
    g.pose.pose.position.y = goal['y']
    g.pose.pose.orientation.z = math.sin(goal.get('yaw', 0.0) / 2)
    g.pose.pose.orientation.w = math.cos(goal.get('yaw', 0.0) / 2)

    send = node.client.send_goal_async(g)
    rclpy.spin_until_future_complete(node, send, timeout_sec=20.0)
    handle = send.result()
    if handle is None or not handle.accepted:
        return {'goal': goal['name'], 'target': [goal['x'], goal['y'], goal.get('yaw', 0.0)],
                'status': None, 'success': False, 'reason': 'goal_rejected',
                'reset': reset_info, 'start': start, 'end': None,
                'final_error_m': None, 'path_length_m': 0.0, 'progress_m': 0.0,
                'yaw_error_rad': None, 'sim_seconds': 0.0, 'wall_seconds': 0.0,
                'realtime_factor': None, 'plan_waypoints': 0, 'truth_samples': 0,
                'collisions': 0, 'collision_samples': 0, 'odom_vs_truth_gap_m': None,
                'plan': None, 'track': list(node.track)}

    result = handle.get_result_async()
    sim0 = node.get_clock().now().nanoseconds * 1e-9
    wall0 = time.time()
    status = None
    # Odometry that keeps advancing while the truth stands still means the wheels
    # are turning and the body is not: a stuck vehicle whose estimate runs away.
    prev_truth = (start['x'], start['y']) if start else None
    prev_odom = (node.odom['x'], node.odom['y']) if node.odom else None
    odom_travel = truth_travel = 0.0
    while True:
        rclpy.spin_once(node, timeout_sec=0.05)
        if node.truth and node.odom:
            now_t = (node.truth['x'], node.truth['y'])
            now_o = (node.odom['x'], node.odom['y'])
            if prev_truth and prev_odom:
                truth_travel += math.hypot(now_t[0] - prev_truth[0], now_t[1] - prev_truth[1])
                odom_travel += math.hypot(now_o[0] - prev_odom[0], now_o[1] - prev_odom[1])
            prev_truth, prev_odom = now_t, now_o
        sim_now = node.get_clock().now().nanoseconds * 1e-9
        if result.done():
            status = result.result().status
            break
        if sim_now - sim0 > budget_s:
            handle.cancel_goal_async()
            status = -1                      # budget exceeded
            spin_for(node, 1.0)
            break
        if time.time() - wall0 > watchdog_s:
            handle.cancel_goal_async()
            status = -2                      # wall-clock watchdog
            break
    sim_elapsed = node.get_clock().now().nanoseconds * 1e-9 - sim0
    wall_elapsed = time.time() - wall0
    node.cmd.publish(Twist())
    spin_for(node, 0.5)

    end = dict(node.truth) if node.truth else None
    x0, y0 = (start['x'], start['y']) if start else (SPAWN[0], SPAWN[1])
    x1, y1 = (end['x'], end['y']) if end else (x0, y0)
    path_len = sum(math.hypot(b['x'] - a['x'], b['y'] - a['y'])
                   for a, b in zip(node.track, node.track[1:]))
    drift = None
    if start and end and node.odom:
        drift = math.hypot((end['x'] - x0), (end['y'] - y0)) - path_len
    final_error = round(math.hypot(x1 - goal['x'], y1 - goal['y']), 3)
    reported = status == GoalStatus.STATUS_SUCCEEDED
    record = {
        'goal': goal['name'], 'target': [goal['x'], goal['y'], goal.get('yaw', 0.0)],
        'reset': reset_info,
        'status': int(status) if status is not None else None,
        'reported_success': reported,
        'success': bool(reported and final_error <= GOAL_TOL_M),
        'false_success': bool(reported and final_error > GOAL_TOL_M),
        'goal_tolerance_m': GOAL_TOL_M,
        'odom_travel_m': round(odom_travel, 3),
        'truth_travel_m': round(truth_travel, 3),
        'stuck': bool(odom_travel - truth_travel > 0.5),
        'start': start, 'end': end,
        'final_error_m': final_error,
        'path_length_m': round(path_len, 3),
        'progress_m': round(math.hypot(x1 - x0, y1 - y0), 3),
        'yaw_error_rad': round(abs(math.atan2(math.sin((end['yaw'] if end else 0) - goal.get('yaw', 0.0)),
                                              math.cos((end['yaw'] if end else 0) - goal.get('yaw', 0.0)))), 3),
        'sim_seconds': round(sim_elapsed, 2),
        'wall_seconds': round(wall_elapsed, 2),
        'realtime_factor': round(sim_elapsed / wall_elapsed, 3) if wall_elapsed else None,
        'plan_waypoints': len(node.path) if node.path else 0,
        'truth_samples': len(node.track),
        'collisions': len(node.contacts),
        'collision_samples': list(node.contacts)[:5],
        'odom_vs_truth_gap_m': round(drift, 3) if drift is not None else None,
        'track': list(node.track),
        'plan': list(node.path) if node.path else [],
    }
    if not record['success']:
        record['reason'] = ('truth_disagrees' if reported else
                            'budget_exceeded' if status == -1 else
                            'watchdog' if status == -2 else f'status_{status}')
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--goals', default=str(OUT / 'placeable_region.json'))
    ap.add_argument('--rounds', type=int, default=3)
    ap.add_argument('--budget', type=float, default=60.0, help='simulated seconds per run')
    ap.add_argument('--watchdog', type=float, default=180.0, help='wall-clock seconds per run')
    ap.add_argument('--only', default=None, help='comma separated goal names')
    ap.add_argument('--tag', default='', help='suffix for the output files, e.g. amcl')
    ap.add_argument('--reinit-amcl', action='store_true',
                    help='re-send /initialpose after each teleport (AMCL mode)')
    args = ap.parse_args()
    global REINIT_AMCL
    REINIT_AMCL = args.reinit_amcl

    goals = [g for g in json.loads(Path(args.goals).read_text())['goals'] if g.get('feasible')]
    if args.only:
        wanted = {s.strip() for s in args.only.split(',')}
        goals = [g for g in goals if g['name'] in wanted]

    rclpy.init()
    node = Eval()
    if not node.client.wait_for_server(timeout_sec=60.0):
        print(json.dumps({'ok': False, 'error': 'navigate_to_pose unavailable'}))
        return 1
    # let the clock and the ground-truth stream settle
    spin_for(node, 2.0)

    runs = []
    for goal in goals:
        for r in range(args.rounds):
            rec = one_run(node, goal, args.budget, args.watchdog)
            rec['round'] = r + 1
            runs.append(rec)
            print(json.dumps({k: rec[k] for k in ('goal', 'round', 'success', 'status',
                                                  'final_error_m', 'path_length_m',
                                                  'sim_seconds', 'wall_seconds',
                                                  'collisions')}), flush=True)

    summary = {}
    for goal in goals:
        rows = [r for r in runs if r['goal'] == goal['name']]
        summary[goal['name']] = {
            'target': [goal['x'], goal['y']],
            'attempts': len(rows),
            'successes': sum(1 for r in rows if r['success']),
            'reported_successes': sum(1 for r in rows if r['reported_success']),
            'false_successes': sum(1 for r in rows if r['false_success']),
            'stuck_rounds': sum(1 for r in rows if r['stuck']),
            'mean_final_error_m': round(sum(r['final_error_m'] for r in rows) / len(rows), 3),
            'mean_sim_seconds': round(sum(r['sim_seconds'] for r in rows) / len(rows), 2),
            'collisions': sum(r['collisions'] for r in rows),
        }
    payload = {'generated': time.strftime('%Y-%m-%dT%H:%M:%S'),
               'budget_sim_seconds': args.budget, 'rounds': args.rounds,
               'localisation': args.tag or 'truth_localization',
               'spawn': {'x': SPAWN[0], 'y': SPAWN[1], 'yaw': SPAWN[2]},
               'summary': summary,
               'runs': [{k: v for k, v in r.items() if k != 'track'} for r in runs]}
    tag = f'_{args.tag}' if args.tag else ''
    (OUT / f'nav_eval_runs{tag}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=1))

    staging = OUT / f'nav_eval_tracks{tag}.json'
    staging.write_text(json.dumps({f'{r["goal"]}_{r["round"]}': r['track'] for r in runs}))
    with (OUT / f'nav_eval_summary{tag}.csv').open('w', newline='') as fh:
        writer = csv.writer(fh)
        writer.writerow(['goal', 'round', 'success', 'reported_success', 'status', 'final_error_m',
                         'path_length_m', 'yaw_error_rad', 'sim_seconds', 'wall_seconds',
                         'realtime_factor', 'collisions', 'plan_waypoints'])
        for r in runs:
            writer.writerow([r['goal'], r['round'], r['success'], r['reported_success'], r['status'],
                             r['final_error_m'], r['path_length_m'], r['yaw_error_rad'],
                             r['sim_seconds'], r['wall_seconds'], r['realtime_factor'],
                             r['collisions'], r['plan_waypoints']])
    print(json.dumps(summary, indent=1))
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())


