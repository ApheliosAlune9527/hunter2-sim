#!/usr/bin/env python3
"""Plan one approach from the registered spawn and save the live observation."""

import argparse
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
import rclpy
from nav2_msgs.action import FollowPath
from nav_msgs.msg import Path as PathMsg
from rclpy.action import ActionClient

from candidate_builder import footprint_clear, path_cost_clear, path_length, yaw_of_quat
from run_straight_dock import LAYOUT, guarded_scene, image_bytes, snapshot
from run_nav_eval_fix import EvalNode, SPAWN
from target_dock import DockLocalizer
from vlm_smoke import label_png


VIEW_POSES = ((0.831, -0.419, 0.650), (0.689, -0.516, 0.550))


def checked_observation_path(camera, pose):
    if camera.wait_costmap(5.0) is None:
        raise RuntimeError('live costmap unavailable')
    for view in VIEW_POSES:
        status, poses = camera.plan(pose, view)
        if status != 4 or not path_cost_clear(camera.costmap, poses):
            continue
        if not all(footprint_clear(camera.costmap, p.pose.position.x, p.pose.position.y,
                                   yaw_of_quat(p.pose.orientation)) for p in poses):
            continue
        return view, poses
    raise RuntimeError('no clear path from the live pose to a view')


def save_observation(camera, out, report):
    frame, view = snapshot(camera)
    raw = image_bytes(frame)
    tf = camera.tf_buffer.lookup_transform('map', frame['info'].header.frame_id, frame['stamp'])
    t = tf.transform.translation
    q = tf.transform.rotation
    view['camera_to_map'] = {'translation': [t.x, t.y, t.z], 'quaternion_xyzw': [q.x, q.y, q.z, q.w]}
    (out / 'observation_rgb.png').write_bytes(raw)
    (out / 'observation_numbered.png').write_bytes(label_png(raw, view['candidates']))
    np.save(out / 'observation_depth.npy', frame['depth'])
    report['observation'] = view
    return frame, view


def run(args, report):
    layout = json.loads(LAYOUT.read_text(encoding='utf-8'))
    guarded_scene(layout)
    rclpy.init(args=[sys.argv[0], '--ros-args', '-p', 'use_sim_time:=true'])
    camera = DockLocalizer(layout)
    nav = EvalNode('amcl')
    try:
        deadline = time.monotonic() + 6.0
        while (nav.truth is None or nav.odom is None) and time.monotonic() < deadline:
            rclpy.spin_once(nav, timeout_sec=0.1)
        if nav.truth is None or nav.odom is None:
            raise RuntimeError('ground truth or odometry unavailable')
        if (math.dist(nav.truth[:2], SPAWN[:2]) > 0.05 or abs(nav.truth[2] - SPAWN[2]) > 0.07
                or max(abs(nav.odom[3]), abs(nav.odom[4])) > 0.03):
            raise RuntimeError('robot must be stationary at the original world spawn')
        report['start_truth'] = nav.truth
        _, initial_view = snapshot(camera)
        report['initial_view'] = initial_view
        view, poses = checked_observation_path(camera, initial_view['robot_pose'])
        report['requested_view'] = view
        report['plan_length_m'] = path_length(poses)
        report['plan'] = [[p.pose.position.x, p.pose.position.y, yaw_of_quat(p.pose.orientation)]
                          for p in poses]
        if args.preview:
            return
        client = ActionClient(nav, FollowPath, 'follow_path')
        goal = FollowPath.Goal(path=PathMsg(header=poses[0].header, poses=poses),
                               controller_id='FollowPath', goal_checker_id='general_goal_checker')
        report['nav'] = nav.send_action(client, goal, budget_sim=16.0, wall_budget=30.0)
        if report['nav']['status'] is None:
            raise RuntimeError('controller did not report a terminal action status')
        report['stop'] = nav.collect_stop(hold_s=1.0, max_wait_s=6.0)
        report['final_truth'] = nav.truth
        if not report['stop']['ok']:
            raise RuntimeError('vehicle did not settle at the end of the observation leg')
        save_observation(camera, args.out, report)
    finally:
        camera.destroy_node()
        nav.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preview', action='store_true', help='plan only, send no motion action')
    mode.add_argument('--out', type=Path, help='new directory for the recorded approach and frame')
    args = parser.parse_args()
    if args.out:
        args.out.mkdir()
    report = {'preview': args.preview, 'error': None}
    try:
        run(args, report)
    except (RuntimeError, ValueError, OSError, LookupError) as exc:
        report['error'] = str(exc)
    if args.out:
        (args.out / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    summary = {k: report.get(k) for k in ('preview', 'start_truth', 'requested_view', 'plan_length_m',
                                         'final_truth', 'stop', 'error')}
    summary['status'] = report.get('nav', {}).get('status')
    summary['blue_candidates'] = len(report.get('observation', {}).get('candidates', []))
    summary['initial_blue_candidates'] = len(report.get('initial_view', {}).get('candidates', []))
    summary['output'] = str(args.out) if args.out else None
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False))
    return 0 if not report['error'] and (args.preview or summary['status'] == 4) else 2


if __name__ == '__main__':
    raise SystemExit(main())
