#!/usr/bin/env python3
"""Repeatable navigation evaluation with the corrected scene, footprint and parameters.

Differs from the 2026-11-05 evaluator in ways section E of the correction plan asked for:

  * every number comes from metrics.py, which has its own tests (test_metrics.py);
  * the action status and the truth are recorded separately, and `truth_disagrees` is a
    failure -- a spinning wheel made the old evaluator report success;
  * drift is an SE(2) comparison of matched samples, not chord-minus-path;
  * the stop is verified: zero command, then |v| and |w| below tolerance for a full
    simulated second;
  * the budget is in simulated seconds and the watchdog in wall seconds, both reported;
  * a reset must read the pose back before the run counts.

Usage (stack already running, see run_fix_stack.bash):

    python3 run_nav_eval_fix.py --tag truth --rounds 3
    python3 run_nav_eval_fix.py --tag amcl --localizer amcl --reinit-amcl --rounds 3
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry, Path as PathMsg
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

import metrics

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'outputs' / 'lab_nav_fix_20261106'

# The three goals of the earlier round, with the heading the older run used.  They are
# kept identical on purpose: the point of this round is the configuration, so the task
# set must not move with it.
GOALS = [
    ('short_straight', 1.885, 0.435, 0.522),
    ('mid_offset', 3.185, 1.235, 0.5335),
    ('long_run', 4.285, 2.535, 0.634),
    # 1 m straight ahead of the spawn, yaw 0: the demonstration goal for the real
    # vehicle, where a 3.9 m run is more travel than the operator wants to watch.
    ('near_straight', 0.79, -0.77, 0.0),
    # 0.3 m ahead: the operator asked for a travel short enough to stop by hand.
    ('near_03', 0.09, -0.77, 0.0),
    # 0.5 m ahead: short enough to stop by hand, long enough that the motion is
    # visible after the 0.20 m goal tolerance takes its share.
    ('near_05', 0.29, -0.77, 0.0),
]
SPAWN = (-0.21, -0.77, 0.0)
WORLD = 'hz_lab_2d'
MODEL = 'hz_hunter_full'


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class EvalNode(Node):
    def __init__(self, localizer, amcl_init_std=0.5, amcl_init_yaw_std=0.2618):
        super().__init__('nav_eval_fix')
        self.localizer = localizer
        self.amcl_init_std = amcl_init_std
        self.amcl_init_yaw_std = amcl_init_yaw_std
        self.truth = None
        self.odom = None
        self.plan = None
        self.amcl = None
        sensor = QoSProfile(depth=10)
        sensor.reliability = ReliabilityPolicy.BEST_EFFORT
        latched = QoSProfile(depth=1)
        latched.durability = DurabilityPolicy.TRANSIENT_LOCAL
        self.create_subscription(Odometry, '/ground_truth', self._truth_cb, 10)
        self.create_subscription(Odometry, '/odom', self._odom_cb, 10)
        # /plan is published best-effort and volatile; asking for durable delivery only
        # produces an "incompatible QoS" warning and no messages.
        plan_qos = QoSProfile(depth=1)
        plan_qos.reliability = ReliabilityPolicy.BEST_EFFORT
        self.create_subscription(PathMsg, '/plan', self._plan_cb, plan_qos)
        if localizer == 'amcl':
            self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose',
                                     self._amcl_cb, 10)
        self.cmd = self.create_publisher(Twist, '/cmd_vel', 10)
        self.init = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

    def _truth_cb(self, msg):
        p = msg.pose.pose
        self.truth = (p.position.x, p.position.y, yaw_of(p.orientation))

    def _odom_cb(self, msg):
        p = msg.pose.pose
        self.odom = (p.position.x, p.position.y, yaw_of(p.orientation),
                     msg.twist.twist.linear.x, msg.twist.twist.angular.z)

    def _plan_cb(self, msg):
        self.plan = msg

    def _amcl_cb(self, msg):
        p = msg.pose.pose
        self.amcl = (p.position.x, p.position.y, yaw_of(p.orientation))

    # ---- time helpers -------------------------------------------------------------
    def sim_s(self):
        return self.get_clock().now().nanoseconds / 1e9

    def spin_sim(self, seconds, tick=0.02):
        """Spin until `seconds` of simulated time have passed."""
        end = self.sim_s() + seconds
        while self.sim_s() < end:
            rclpy.spin_once(self, timeout_sec=tick)

    def spin_wall(self, seconds, tick=0.02):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=tick)

    # ---- reset --------------------------------------------------------------------
    def teleport(self, x, y, yaw):
        q = (math.sin(yaw / 2.0), math.cos(yaw / 2.0))
        req = ('name: "%s", position: {x: %.6f, y: %.6f, z: 0.165}, '
               'orientation: {x: 0, y: 0, z: %.6f, w: %.6f}' % (MODEL, x, y, q[0], q[1]))
        return subprocess.run(
            ['ign', 'service', '-s', '/world/%s/set_pose' % WORLD,
             '--reqtype', 'ignition.msgs.Pose', '--reptype', 'ignition.msgs.Boolean',
             '--timeout', '4000', '--req', req],
            capture_output=True, text=True, timeout=20)

    def reseed_amcl(self, x, y, yaw, repeats=5):
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        # A known spawn deserves a tight prior.  The old 0.5 m / 0.26 rad standard
        # deviation left AMCL spread over the corridor and produced a ~9 cm mean error
        # after a 1 m run, which is enough to make the final Dubin segment infeasible.
        msg.pose.covariance[0] = self.amcl_init_std ** 2
        msg.pose.covariance[7] = self.amcl_init_std ** 2
        msg.pose.covariance[35] = self.amcl_init_yaw_std ** 2
        for _ in range(repeats):
            msg.header.stamp = self.get_clock().now().to_msg()
            self.init.publish(msg)
            self.spin_sim(0.2)

    def settle_after_teleport(self, timeout_s=6.0):
        """Wait until the truth stops moving, and return what it read back."""
        last, still_since = None, None
        end = self.sim_s() + timeout_s
        while self.sim_s() < end:
            self.spin_sim(0.05)
            if self.truth is None:
                continue
            if last is not None:
                d = math.hypot(self.truth[0] - last[0], self.truth[1] - last[1])
                if d < 0.002:
                    if still_since is None:
                        still_since = self.sim_s()
                    elif self.sim_s() - still_since >= 0.2:
                        return self.truth
                else:
                    still_since = None
            last = self.truth
        return self.truth

    def reset(self, reinit_amcl):
        self.teleport(*SPAWN)
        self.spin_wall(0.5)
        if reinit_amcl:
            self.reseed_amcl(*SPAWN)
            self.spin_sim(4.0)          # AMCL needs a few scans before its estimate is
                                        # stable; 2 s was measured to still be 1.06 m off
        return self.settle_after_teleport()

    # ---- one run ------------------------------------------------------------------
    def send_goal(self, x, y, yaw, budget_sim, wall_budget):
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        goal.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(yaw / 2.0)

        return self.send_action(self.client, goal, budget_sim, wall_budget)

    def send_action(self, client, goal, budget_sim, wall_budget, on_tick=None):
        if not client.wait_for_server(timeout_sec=10.0):
            return {'status': None, 'reason': 'no_action_server', 'track': [],
                    'cancel': None, 'sim_s': 0.0, 'wall_s': 0.0}

        send_future = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send_future, timeout_sec=10.0)
        handle = send_future.result()
        if handle is None or not handle.accepted:
            return {'status': None, 'reason': 'rejected', 'track': [],
                    'cancel': None, 'sim_s': 0.0, 'wall_s': 0.0}

        result_future = handle.get_result_async()
        track = []
        start_sim = self.sim_s()
        start_wall = time.monotonic()
        next_sample = start_sim
        over = None
        while not result_future.done():
            # Two independent limits.  The simulated clock is what the controller
            # experiences, but it stops if Gazebo stalls -- and then a sim-only budget
            # waits forever.  The wall limit is what guarantees the tool exits.
            over = metrics.budget_hit(self.sim_s() - start_sim,
                                      time.monotonic() - start_wall,
                                      budget_sim, wall_budget)
            if over is not None:
                over = 'budget_' + over
                break
            rclpy.spin_once(self, timeout_sec=0.02)
            if on_tick is not None:
                on_tick()
            now = self.sim_s()
            if now >= next_sample:
                next_sample = now + 0.05
                if self.truth is not None and self.odom is not None:
                    track.append({'t': round(now, 3),
                                  'truth': [round(v, 4) for v in self.truth],
                                  'odom_pose': [round(v, 4) for v in self.odom[:3]]})

        cancel = None
        if over is not None:
            # Ask the navigator to stop, then prove it stopped: an abandoned goal that
            # keeps driving would collide with the next reset.
            cancel = {'reason': over, 'requested': True}
            cf = handle.cancel_goal_async()
            rclpy.spin_until_future_complete(self, cf, timeout_sec=5.0)
            # Three ways this can go, and they are not the same thing: the server never
            # answers (future not done), it answers with an empty list (acknowledged but
            # no goal in flight), or it answers with the goal (real cancellation).
            cancel['ack_future_done'] = bool(cf.done() and cf.result() is not None)
            if cancel['ack_future_done']:
                cancelling = getattr(cf.result(), 'goals_canceling', None)
                cancel['acknowledged_goals'] = len(cancelling) if cancelling else 0
                cancel['acknowledged'] = bool(cancelling)
            else:
                cancel['acknowledged_goals'] = None
                cancel['acknowledged'] = False
            end = time.monotonic() + 15.0
            while not result_future.done() and time.monotonic() < end:
                rclpy.spin_once(self, timeout_sec=0.05)
            cancel['ended'] = result_future.done()
            cancel['final_status'] = result_future.result().status if result_future.done() else None
            cancel['waited_wall_s'] = round(15.0 - max(0.0, end - time.monotonic()), 3)

        return {'status': result_future.result().status if result_future.done() else None,
                'reason': over,
                'track': track,
                'cancel': cancel,
                'sim_s': round(self.sim_s() - start_sim, 3),
                'wall_s': round(time.monotonic() - start_wall, 3)}

    def collect_stop(self, hold_s=1.0, max_wait_s=10.0, wall_budget=None):
        """Publish zero and watch until the vehicle is quiet for hold_s.

        Two independent sources, because either one alone can lie: the wheel odometry
        keeps integrating if a wheel spins against a wall, and the truth pose is what
        the whole evaluation is anchored on.  Both are recorded.

        The truth displacement is measured over the *last* hold_s seconds, not over the
        whole wait: a vehicle that arrives at 0.2 m/s keeps coasting for a second or so
        after the command goes to zero, and that deceleration tail is not a failure to
        stop -- it is the stop happening.
        """
        zero = Twist()
        end = self.sim_s() + max_wait_s
        wall_end = math.inf if wall_budget is None else time.monotonic() + wall_budget
        samples = []
        truth_samples = []
        next_sample = self.sim_s()
        while self.sim_s() < end and time.monotonic() < wall_end:
            self.cmd.publish(zero)
            rclpy.spin_once(self, timeout_sec=0.02)
            now = self.sim_s()
            if now >= next_sample:
                next_sample = now + 0.02
                if self.odom is not None:
                    samples.append((now, self.odom[3], self.odom[4]))
                if self.truth is not None:
                    truth_samples.append((now, self.truth[0], self.truth[1]))
            if metrics.stop_settled(samples, hold_s=hold_s)['ok']:
                break
        verdict = metrics.stop_settled(samples, hold_s=hold_s)
        verdict['waited_s'] = round(self.sim_s() - (end - max_wait_s), 3)

        window = [s for s in truth_samples if truth_samples and s[0] >= truth_samples[-1][0] - hold_s]
        if len(window) >= 2:
            t0, x0, y0 = window[0]
            t1, x1, y1 = window[-1]
            moved = math.hypot(x1 - x0, y1 - y0)
            span = max(t1 - t0, 1e-6)
            verdict['truth_displacement_m'] = round(moved, 4)
            verdict['truth_window_s'] = round(span, 3)
            verdict['truth_speed_mps'] = round(moved / span, 4)
            verdict['truth_still'] = (moved / span) < 0.01
        else:
            verdict['truth_displacement_m'] = None
            verdict['truth_still'] = None
        verdict['ok'] = bool(verdict['ok'] and verdict['truth_still'])
        return verdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', default='truth')
    ap.add_argument('--localizer', default='truth', choices=['truth', 'amcl'])
    ap.add_argument('--rounds', type=int, default=3)
    ap.add_argument('--budget-sim', type=float, default=60.0)
    # Wall-clock limit on a single round.  Without it a stalled /clock makes the
    # simulated budget unreachable and the tool hangs instead of failing.
    ap.add_argument('--wall-budget', type=float, default=300.0)
    ap.add_argument('--goals', default='')
    ap.add_argument('--reinit-amcl', action='store_true')
    ap.add_argument('--amcl-init-std', type=float, default=0.5,
                    help='AMCL initial x/y standard deviation in metres; use 0.05 for a known spawn')
    ap.add_argument('--amcl-init-yaw-std', type=float, default=0.2618,
                    help='AMCL initial yaw standard deviation in radians')
    ap.add_argument('--seed', type=int, default=0)
    # Where run_fix_stack.bash wrote its registry.  Used only for the abnormal exit path,
    # where the goal could not be ended and the session has to be stopped deliberately.
    ap.add_argument('--stack-log-dir', default=os.environ.get('LOG_DIR', '/tmp/lab_fix_stack'))
    ap.add_argument('--stop-on-abort', dest='stop_on_abort', action='store_true', default=True)
    ap.add_argument('--no-stop-on-abort', dest='stop_on_abort', action='store_false')
    args = ap.parse_args()

    wanted = args.goals.split(',') if args.goals else None
    goals = [g for g in GOALS if not wanted or g[0] in wanted]

    rclpy.init()
    node = EvalNode(args.localizer, args.amcl_init_std, args.amcl_init_yaw_std)
    node.set_parameters([rclpy.parameter.Parameter('use_sim_time',
                                                   value=True)])
    # Without a clock and a ground-truth pose there is nothing to evaluate, and waiting
    # forever looks like a hang.  The usual cause is the wrong ROS domain, i.e. the
    # caller forgot to source lab_nav_fix_env.bash.
    wait_end = time.monotonic() + 30.0
    while node.truth is None and time.monotonic() < wait_end:
        rclpy.spin_once(node, timeout_sec=0.1)
    if node.truth is None:
        print('FATAL: no /ground_truth within 30 s -- is this shell in the simulator '
              'environment (source lab_nav_fix_env.bash)?', flush=True)
        node.destroy_node()
        rclpy.shutdown()
        return 4

    runs = []
    for name, gx, gy, gyaw in goals:
        for r in range(args.rounds):
            started_truth = node.reset(args.reinit_amcl)
            if started_truth is None:
                runs.append({'goal': name, 'round': r, 'success': False,
                             'reason': 'reset_failed'})
                continue
            res = node.send_goal(gx, gy, gyaw, args.budget_sim, args.wall_budget)
            status = res['status']
            track = res['track']
            cancel = res['cancel']

            # If the goal could not be ended, the vehicle may still be driving.  Do not
            # reset into the next goal on top of that: take whatever stop evidence can
            # still be had, write the partial record, stop this batch, and then stop the
            # session through the process registry this stack was started with.  Every
            # piece of evidence that is missing is named in `missing_evidence` instead of
            # being left out or filled in.
            if cancel is not None and not cancel.get('ended'):
                stop = node.collect_stop(hold_s=1.0, max_wait_s=5.0)
                missing = ['action_terminal_state']
                if not cancel.get('acknowledged'):
                    missing.append('cancel_acknowledgement')
                if not stop.get('ok'):
                    missing.append('stop_not_confirmed')
                runs.append({'goal': name, 'round': r, 'success': False,
                             'reason': 'goal_did_not_end',
                             'goal_pose': [gx, gy, gyaw],
                             'start_truth': [round(v, 4) for v in started_truth],
                             'final_truth': [round(v, 4) for v in node.truth]
                                            if node.truth is not None else None,
                             'action_status': status,
                             'reported_success': status == 4,
                             'cancel': cancel,
                             'stop': stop,
                             'missing_evidence': missing,
                             'final_error_m': None,
                             'heading_error_rad': None,
                             'sim_seconds': res['sim_s'], 'wall_seconds': res['wall_s'],
                             'budget': metrics.budget_note(res['sim_s'], res['wall_s'],
                                                           args.budget_sim,
                                                           wall_limit_s=args.wall_budget),
                             'samples': len(track),
                             'track': [[p['t'], p['truth'][0], p['truth'][1], p['truth'][2]]
                                       for p in track]})
                cleanup = None
                if args.stop_on_abort:
                    cleanup = _stop_session(args)
                _write(OUT, args, goals, runs, extra={'session_cleanup': cleanup})
                print('[%s %s r%d] goal_did_not_end after cancel (missing: %s); '
                      'stopping the round set and the session'
                      % (args.tag, name, r, ', '.join(missing)), flush=True)
                node.destroy_node()
                rclpy.shutdown()
                return 3

            stop = node.collect_stop()
            final = node.truth
            pos_err, head_err = metrics.pose_error((gx, gy, gyaw), final)

            odom_track = [(p['odom_pose'][0], p['odom_pose'][1], p['odom_pose'][2]) for p in track]
            truth_track = [(p['truth'][0], p['truth'][1], p['truth'][2]) for p in track]
            drift = None
            if len(track) > 2:
                try:
                    drift = metrics.odom_truth_drift(odom_track, truth_track)
                except ValueError as exc:
                    drift = {'error': str(exc)}

            verdict = metrics.classify(status, pos_err, head_err)
            if res['reason'] == 'budget_sim':
                verdict = 'timeout_sim_budget'
            elif res['reason'] == 'budget_wall':
                verdict = 'timeout_wall_budget'
            elif res['reason'] in ('no_action_server', 'rejected'):
                verdict = res['reason']
            if not stop['ok'] and verdict == 'succeeded':
                verdict = 'did_not_stop'

            runs.append({
                'goal': name, 'round': r,
                'goal_pose': [gx, gy, gyaw],
                'start_truth': [round(v, 4) for v in started_truth],
                'final_truth': [round(v, 4) for v in final],
                'action_status': status,
                'reported_success': status == 4,
                'success': verdict == 'succeeded',
                'reason': verdict,
                'cancel': cancel,
                'final_error_m': round(pos_err, 4),
                'heading_error_rad': round(head_err, 4),
                'tolerance_nav2_m': metrics.POS_TOL_NAV2,
                'tolerance_outer_m': metrics.POS_TOL_OUTER,
                'stop': stop,
                'drift': drift,
                'budget': metrics.budget_note(res['sim_s'], res['wall_s'], args.budget_sim,
                                              wall_limit_s=args.wall_budget),
                'samples': len(track),
                # kept so the plots and any later collision audit can use the path the
                # vehicle actually drove rather than reconstruct it from the endpoints
                'track': [[p['t'], p['truth'][0], p['truth'][1], p['truth'][2]]
                          for p in track],
            })
            print('[%s %s r%d] %s err=%.3f head=%.3f sim=%.1fs cancel=%s stop=%s' % (
                args.tag, name, r, verdict, pos_err, head_err, res['sim_s'],
                'yes' if cancel else 'no', stop['ok']), flush=True)
            _write(OUT, args, goals, runs)

    summary = _summarise(goals, runs)
    print(json.dumps({'successes': sum(1 for r in runs if r.get('success')),
                      'attempts': len(runs), 'summary': summary},
                     ensure_ascii=False), flush=True)
    node.destroy_node()
    rclpy.shutdown()
    return 0


def _stop_session(args):
    """Stop this session through the registry, not by process name.

    The registry belongs to run_fix_stack.bash; it records pid and kernel start time, so
    stop_fix_stack.bash refuses to signal a pid that has been reused.  The evaluator must
    not invent its own cleanup.
    """
    script = Path(__file__).resolve().parent / 'stop_fix_stack.bash'
    if not script.exists():
        return {'attempted': False, 'reason': 'stop_fix_stack.bash not found'}
    env = dict(os.environ, LOG_DIR=args.stack_log_dir)
    try:
        proc = subprocess.run(['bash', str(script)], env=env, capture_output=True,
                              text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return {'attempted': True, 'log_dir': args.stack_log_dir, 'timed_out': True}
    return {'attempted': True, 'log_dir': args.stack_log_dir,
            'returncode': proc.returncode,
            'stdout': proc.stdout.strip()[-2000:],
            'stderr': proc.stderr.strip()[-2000:]}


def _write(out, args, goals, runs, extra=None):
    out.mkdir(parents=True, exist_ok=True)
    payload = {'localizer': args.localizer, 'seed': args.seed, 'tag': args.tag,
               'goals': [list(g) for g in goals],
               'budget_sim_limit': args.budget_sim, 'wall_budget_limit': args.wall_budget,
               'summary': _summarise(goals, runs), 'runs': runs}
    if extra:
        payload.update(extra)
    (out / ('nav_eval_runs_%s.json' % args.tag)).write_text(
        json.dumps(payload, ensure_ascii=False, indent=1))


def _summarise(goals, runs):
    summary = {}
    for name, _, _, _ in goals:
        rs = [r for r in runs if r['goal'] == name]
        ok = [r for r in rs if r.get('success')]
        summary[name] = {
            'attempts': len(rs), 'successes': len(ok),
            'mean_error_m': round(sum(r['final_error_m'] for r in ok) / len(ok), 4) if ok else None,
            'mean_sim_s': round(sum(r['budget']['sim_seconds'] for r in ok) / len(ok), 2) if ok else None,
            'reasons': sorted({r.get('reason') for r in rs}),
        }
    return summary


if __name__ == '__main__':
    sys.exit(main())
