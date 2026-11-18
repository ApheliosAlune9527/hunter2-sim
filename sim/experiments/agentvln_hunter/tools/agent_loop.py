#!/usr/bin/env python3
"""One rule-driven AgentVLN wayfinding loop on top of the step-2 candidate layer.

The loop exercises the exact interface that a VLM will later drive:
  fresh frame -> numbered reachable candidates -> structured decision ->
  validate id/frame -> trial plan -> one NavigateToPose segment -> new frame.
The rule selector uses an oracle map target and is labelled as an engineering
baseline, not as a perception model. A colour-marker selector is included as the
fallback image-driven baseline when no local VLM backend is available.
"""
import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from rclpy.duration import Duration

from candidate_builder import yaw_of_quat
from candidate_view import CandidateView, cand_dict


class AgentLoop(CandidateView):
    def __init__(self):
        super().__init__()
        self.truth = None
        self.amcl = None
        self.create_subscription(Odometry, '/ground_truth', self.on_truth, 10)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self.on_amcl, 10)
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.cmd = self.create_publisher(Twist, '/cmd_vel', 10)

    def on_truth(self, msg):
        p = msg.pose.pose
        self.truth = (p.position.x, p.position.y, yaw_of_quat(p.orientation))

    def on_amcl(self, msg):
        p = msg.pose.pose
        self.amcl = (p.position.x, p.position.y, yaw_of_quat(p.orientation))

    def wait_new_frame(self, after_ns, timeout=25.0):
        self.latest = None
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.latest is None or self.latest['stamp_ns'] <= after_ns:
                continue
            if self.latest['age_s'] > 1.5:
                continue
            try:
                self.tf_buffer.lookup_transform('map', 'base_link',
                                                self.latest['info'].header.stamp,
                                                timeout=Duration(seconds=0.1))
            except Exception:
                self.latest = None
                continue
            return self.latest
        return None

    def execute(self, candidate, frame_stamp):
        robot = self.robot_pose(frame_stamp)
        plan_status, path = self.plan(robot, (candidate.x, candidate.y, candidate.yaw))
        action = {'replan_status': int(plan_status), 'planned_poses': len(path),
                  'replanned_path_m': None}
        if plan_status != 4 or len(path) < 2:
            action['status'] = 0
            action['rejected'] = 'replan_failed'
            return action
        # The trial path length is useful evidence but the action itself is authoritative.
        action['replanned_path_m'] = round(sum(
            math.hypot(b.pose.position.x - a.pose.position.x,
                       b.pose.position.y - a.pose.position.y)
            for a, b in zip(path[:-1], path[1:])), 3)
        if not self.nav_client.wait_for_server(timeout_sec=5.0):
            action['status'] = 0
            action['rejected'] = 'nav_server_unavailable'
            return action
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = frame_stamp
        goal.pose.pose.position.x = candidate.x
        goal.pose.pose.position.y = candidate.y
        goal.pose.pose.orientation.z = math.sin(candidate.yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(candidate.yaw / 2.0)
        t0 = time.monotonic()
        fut = self.nav_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=8.0)
        handle = fut.result()
        if handle is None or not handle.accepted:
            action['status'] = 0
            action['rejected'] = 'goal_rejected'
            return action
        res_fut = handle.get_result_async()
        timed_out = False
        while not res_fut.done():
            rclpy.spin_once(self, timeout_sec=0.02)
            if time.monotonic() - t0 > 60.0:
                timed_out = True
                handle.cancel_goal_async()
                rclpy.spin_once(self, timeout_sec=0.5)
                break
        status = res_fut.result().status if res_fut.done() else None
        action.update({'status': int(status) if status is not None else None,
                       'timed_out': timed_out, 'wall_s': round(time.monotonic() - t0, 3),
                       'truth_after': [round(v, 4) for v in self.truth] if self.truth else None})
        if self.truth:
            action['error_to_candidate_m'] = round(math.hypot(
                self.truth[0] - candidate.x, self.truth[1] - candidate.y), 4)
            action['heading_to_candidate_rad'] = round(abs(math.atan2(
                math.sin(self.truth[2] - candidate.yaw),
                math.cos(self.truth[2] - candidate.yaw))), 4)
        # Zero command for one second and measure residual motion.
        t1 = self.truth
        end = time.monotonic() + 1.0
        while time.monotonic() < end:
            self.cmd.publish(Twist())
            rclpy.spin_once(self, timeout_sec=0.02)
        if t1 and self.truth:
            action['stop_displacement_m'] = round(math.hypot(
                self.truth[0] - t1[0], self.truth[1] - t1[1]), 4)
        action['amcl_error_m'] = round(math.hypot(
            self.amcl[0] - self.truth[0], self.amcl[1] - self.truth[1]), 4) if self.amcl and self.truth else None
        return action


def choose(candidates, target):
    visible = [c for c in candidates if c.visible]
    if not visible:
        return None
    return min(visible, key=lambda c: (math.hypot(c.x - target[0], c.y - target[1])
                                       + 0.10 * c.path_length))


def detect_marker(rgb, color, min_area=200):
    """Find the largest saturated colour blob. RGB input, BGR-free."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    if color == 'red':
        mask = cv2.inRange(hsv, (0, 120, 80), (10, 255, 255)) | \
            cv2.inRange(hsv, (170, 120, 80), (180, 255, 255))
    elif color == 'green':
        mask = cv2.inRange(hsv, (35, 100, 60), (85, 255, 255))
    elif color == 'blue':
        mask = cv2.inRange(hsv, (90, 120, 70), (140, 255, 255))
    else:
        return None
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(contour))
    if area < min_area:
        return None
    m = cv2.moments(contour)
    if m['m00'] <= 0:
        return None
    return {
        'color': color,
        'u': round(m['m10'] / m['m00'], 2),
        'v': round(m['m01'] / m['m00'], 2),
        'area_px': round(area, 1),
        'area_fraction': round(area / float(rgb.shape[0] * rgb.shape[1]), 5),
    }


def choose_color(candidates, marker):
    visible = [c for c in candidates if c.visible]
    if not visible or marker is None:
        return None
    return min(visible, key=lambda c: (math.hypot(c.u - marker['u'], c.v - marker['v'])
                                       + 0.05 * c.path_length))


def draw(image, candidates, selected, marker=None):
    out = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    for c in candidates:
        if not c.visible:
            continue
        color = (0, 255, 255) if selected is c else (0, 255, 0)
        thickness = 3 if selected is c else 2
        u, v = int(round(c.u)), int(round(c.v))
        cv2.line(out, (u, v), (u, min(out.shape[0] - 1, v + 26)), color, 1, cv2.LINE_AA)
        cv2.circle(out, (u, v), 9, color, thickness)
        cv2.putText(out, str(c.cid), (u - 7, v - 14), cv2.FONT_HERSHEY_SIMPLEX,
                    0.75, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(out, str(c.cid), (u - 7, v - 14), cv2.FONT_HERSHEY_SIMPLEX,
                    0.75, color, 2, cv2.LINE_AA)
    if selected is not None:
        cv2.putText(out, 'selected %d' % selected.cid, (15, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
    if marker is not None:
        mu, mv = int(round(marker['u'])), int(round(marker['v']))
        cv2.circle(out, (mu, mv), 16, (255, 0, 255), 2, cv2.LINE_AA)
        cv2.putText(out, 'marker %s %.1f%%' % (marker['color'], 100.0 * marker['area_fraction']),
                    (max(5, mu - 60), max(20, mv - 22)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (255, 0, 255), 1, cv2.LINE_AA)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--instruction', default='沿走廊前往目标观察点')
    ap.add_argument('--target', nargs=2, type=float, required=True, metavar=('X', 'Y'))
    ap.add_argument('--max-steps', type=int, default=4)
    ap.add_argument('--finish-tolerance', type=float, default=0.55)
    ap.add_argument('--out', default='/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_step2/agent_loop')
    ap.add_argument('--distances', default='1.4,1.7,2.0')
    ap.add_argument('--angles', default='-26,-13,0,13,26')
    ap.add_argument('--max-candidates', type=int, default=18)
    ap.add_argument('--vis-height', type=float, default=0.5)
    ap.add_argument('--selector', choices=['rule', 'color_red', 'color_green', 'color_blue'],
                    default='rule')
    ap.add_argument('--marker-min-area', type=float, default=200.0)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    distances = tuple(float(v) for v in args.distances.split(','))
    angles = tuple(float(v) for v in args.angles.split(','))

    rclpy.init()
    node = AgentLoop()
    if not node.wait_costmap(timeout=10.0):
        print(json.dumps({'error': 'no global costmap'}))
        return 1
    if not node.nav_client.wait_for_server(timeout_sec=10.0):
        print(json.dumps({'error': 'no navigate_to_pose server'}))
        return 1
    end = time.monotonic() + 2.0
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.05)

    runs = []
    prev_stamp = 0
    failure = None
    start_wall = time.monotonic()
    for step in range(args.max_steps):
        frame = node.wait_new_frame(prev_stamp, timeout=25.0)
        if frame is None:
            failure = 'no_fresh_frame'
            break
        stamp = frame['stamp_ns']
        prev_stamp = stamp
        try:
            robot = node.robot_pose(frame['info'].header.stamp)
        except Exception as exc:
            failure = 'no_robot_tf: %s' % exc
            break
        if math.hypot(robot[0] - args.target[0], robot[1] - args.target[1]) <= args.finish_tolerance:
            step_dir = out / ('step_%02d' % step)
            step_dir.mkdir(exist_ok=True)
            (step_dir / 'decision.json').write_text(json.dumps({
                'decision': 'finish', 'frame_stamp_s': stamp / 1e9,
                'robot_pose_map': [round(v, 4) for v in robot],
                'target': args.target,
                'distance_to_target_m': round(math.hypot(robot[0] - args.target[0],
                                                          robot[1] - args.target[1]), 4),
                'instruction': args.instruction}, indent=2, ensure_ascii=False))
            failure = None
            runs.append({'step': step, 'decision': 'finish', 'robot': [round(v, 4) for v in robot]})
            break
        candidates = node.build(frame['info'].header.stamp, frame['info'], robot,
                                distances, angles, args.max_candidates)
        candidates = node.project(candidates, frame['info'].header.stamp, frame['info'],
                                  frame['depth'], frame['rgb'].shape[:2], args.vis_height)
        visible = [c for c in candidates if c.visible]
        visible.sort(key=lambda c: (c.u, c.v))
        for i, c in enumerate(visible, 1):
            c.cid = i
        marker = None
        if args.selector.startswith('color_'):
            marker = detect_marker(frame['rgb'], args.selector.split('_', 1)[1], args.marker_min_area)
            selected = choose_color(candidates, marker)
            selection_reason = ('color: nearest visible candidate to %s marker in image' %
                                args.selector.split('_', 1)[1])
        else:
            selected = choose(candidates, args.target)
            selection_reason = 'rule: nearest visible candidate to oracle target, path-length tie-break'
        step_dir = out / ('step_%02d' % step)
        step_dir.mkdir(exist_ok=True)
        annotated = draw(frame['rgb'], candidates, selected, marker)
        cv2.imwrite(str(step_dir / 'frame.png'), cv2.cvtColor(frame['rgb'], cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(step_dir / 'annotated.png'), annotated)
        step_report = {
            'step': step,
            'instruction': args.instruction,
            'selector': args.selector,
            'frame': {'stamp_s': stamp / 1e9, 'age_s': round(frame['age_s'], 4)},
            'robot_pose_map': [round(v, 4) for v in robot],
            'target': args.target,
            'build_stats': node.last_stats,
            'candidates_total': len(candidates),
            'candidates_visible': len(visible),
            'candidates': [cand_dict(c) for c in candidates],
            'marker': marker,
            'decision': None,
            'action': None,
        }
        if not visible or selected is None:
            reason = 'no_visible_candidate'
            if args.selector.startswith('color_') and marker is None:
                reason = 'color_marker_not_found'
            decision = {'decision': 'request_reobserve', 'reason': reason,
                        'selector': args.selector, 'marker': marker,
                        'frame_stamp_s': stamp / 1e9, 'instruction': args.instruction}
            step_report['decision'] = decision
            (step_dir / 'decision.json').write_text(json.dumps(decision, indent=2, ensure_ascii=False))
            (step_dir / 'report.json').write_text(json.dumps(step_report, indent=2, ensure_ascii=False))
            failure = reason
            runs.append({'step': step, 'decision': decision, 'report': str(step_dir)})
            break
        decision = {
            'decision': 'select_candidate',
            'candidate_id': selected.cid,
            'frame_stamp_s': stamp / 1e9,
            'instruction': args.instruction,
            'selector': args.selector,
            'reason': selection_reason,
            'marker': marker,
            'candidate_map_pose': [round(selected.x, 4), round(selected.y, 4), round(selected.yaw, 4)],
            'distance_to_target_m': round(math.hypot(selected.x - args.target[0],
                                                     selected.y - args.target[1]), 4),
        }
        step_report['decision'] = decision
        (step_dir / 'decision.json').write_text(json.dumps(decision, indent=2, ensure_ascii=False))
        action = node.execute(selected, frame['info'].header.stamp)
        step_report['action'] = action
        (step_dir / 'report.json').write_text(json.dumps(step_report, indent=2, ensure_ascii=False))
        runs.append({'step': step, 'decision': decision, 'action': action,
                     'report': str(step_dir), 'annotated': str(step_dir / 'annotated.png')})
        if action.get('status') != 4:
            failure = 'action_status_%s' % action.get('status')
            break

    final_truth = node.truth
    final_error = math.hypot(final_truth[0] - args.target[0],
                             final_truth[1] - args.target[1]) if final_truth else None
    success = bool(final_error is not None and final_error <= args.finish_tolerance and failure is None)
    summary = {
        'instruction': args.instruction,
        'target': args.target,
        'finish_tolerance_m': args.finish_tolerance,
        'selector': args.selector,
        'steps_executed': sum(1 for r in runs if isinstance(r.get('decision'), dict)
                            and r['decision'].get('decision') == 'select_candidate'),
        'success': success,
        'failure': failure,
        'final_truth': [round(v, 4) for v in final_truth] if final_truth else None,
        'final_error_m': round(final_error, 4) if final_error is not None else None,
        'amcl_error_m': round(math.hypot(node.amcl[0] - final_truth[0],
                                          node.amcl[1] - final_truth[1]), 4) if node.amcl and final_truth else None,
        'wall_s': round(time.monotonic() - start_wall, 3),
        'runs': runs,
    }
    (out / 'run.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps({k: summary[k] for k in ('instruction', 'target', 'selector', 'steps_executed',
                                               'success', 'failure', 'final_truth',
                                               'final_error_m', 'amcl_error_m', 'wall_s')},
                     indent=2, ensure_ascii=False))
    rclpy.shutdown()
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
