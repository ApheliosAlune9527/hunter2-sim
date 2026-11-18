#!/usr/bin/env python3
"""Run the known and model-selected approaches in the registered virtual scene."""

import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys

import cv2
from geometry_msgs.msg import PointStamped
import numpy as np
import rclpy
from tf2_geometry_msgs import do_transform_point

EXPERIMENT = Path(__file__).resolve().parents[1]
LAYOUT = EXPERIMENT / 'config/target_layout_straight.json'
STACK = Path(os.environ.get('LOG_DIR', '/tmp/agentvln_vlm_straight'))
SURFACE_STANDOFF_M = 0.83
sys.path.insert(0, str(EXPERIMENT.parent / 'lab_nav_fix_20261106'))
from candidate_builder import footprint_clear, path_cost_clear, yaw_of_quat
from run_nav_eval_fix import EvalNode
from target_dock import DockLocalizer, FRONT_LENGTH, backproject, depth_stats, detect_blue
from vlm_smoke import label_png, measure, run_instruction, truth_map


def guarded_scene(layout):
    expected = {'ROS_DOMAIN_ID': '73', 'ROS_LOCALHOST_ONLY': '1',
                'RMW_IMPLEMENTATION': 'rmw_cyclonedds_cpp',
                'IGN_PARTITION': 'hz_sim_aphelios_73'}
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise RuntimeError('wrong simulator environment')
    session = dict(line.split('=', 1) for line in (STACK / 'session.txt').read_text().splitlines()
                   if '=' in line)
    world = EXPERIMENT / layout['world']
    bridge = EXPERIMENT / 'config/agentvln_bridge.yaml'
    if (session.get('world') != str(world) or session.get('bridge') != str(bridge)
            or session.get('ros_domain_id') != '73' or session.get('ros_localhost_only') != '1'
            or session.get('ign_partition') != expected['IGN_PARTITION']
            or session.get('localizer') != 'amcl'):
        raise RuntimeError('registered scene does not match the experiment')
    world_sha = hashlib.sha256(world.read_bytes()).hexdigest()
    if session.get('world_sha256') != world_sha:
        raise RuntimeError('world changed after startup')


def snapshot(node):
    f = node.wait_frame(15.0)
    if f is None:
        raise RuntimeError('no fresh synchronized RGB-D frame and TF')
    candidates = [{'id': i, 'bbox_xywh': row['bbox'], 'u': row['u'], 'v': row['v'],
                   'area_px': row['area_px']} for i, row in enumerate(detect_blue(f['rgb']))]
    report = {'robot_pose': node.robot_pose(f['stamp']), 'K': list(f['info'].k),
              'stamp_ns': f['stamp_ns'], 'candidates': candidates}
    return f, report


def image_bytes(frame):
    ok, image = cv2.imencode('.png', cv2.cvtColor(frame['rgb'], cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError('could not encode the RGB image')
    return image.tobytes()


def angular_error(a, b):
    return abs(math.atan2(math.sin(a - b), math.cos(a - b)))


def model_goal(args, node, layout, frame, view, report):
    truth = truth_map(view, layout)
    if len(view['candidates']) != 2 or set(truth.values()) != {'blue_far', 'blue_near'}:
        raise RuntimeError('this test requires two separately visible blue boxes')
    bboxes = sorted(row['bbox_xywh'] for row in view['candidates'])
    if (bboxes[1][0] - (bboxes[0][0] + bboxes[0][2]) < 40
            or any(x <= 0 or y <= 0 or x+w >= 640 or y+h >= 480 for x,y,w,h in bboxes)):
        raise RuntimeError('camera framing missed the experiment criterion')
    raw = image_bytes(frame)
    image = label_png(raw, view['candidates'])
    (args.out / 'decision_raw_rgb.png').write_bytes(raw)
    (args.out / 'decision_rgb.png').write_bytes(image)
    np.save(args.out / 'decision_depth.npy', frame['depth'])
    decision = run_instruction(args, view, frame['depth'], base64.b64encode(image).decode('ascii'),
                               '停在较远的蓝箱前', 'blue_far', truth, guided=True)
    report['decision'] = decision
    report['decision_image_sha256'] = hashlib.sha256(image).hexdigest()
    if decision['selected_candidate'] is None:
        raise RuntimeError('model did not select a candidate')
    picked = next(c for c in view['candidates'] if c['id'] == decision['selected_candidate'])
    fresh, live_view = snapshot(node)
    old_pose, pose = view['robot_pose'], live_view['robot_pose']
    if (fresh['stamp_ns'] <= frame['stamp_ns'] or math.dist(old_pose[:2], pose[:2]) > .06
            or angular_error(old_pose[2], pose[2]) > .06 or len(live_view['candidates']) != 2):
        raise RuntimeError('observation changed during inference')
    live = min(live_view['candidates'], key=lambda row: math.hypot(row['u']-picked['u'], row['v']-picked['v']))
    if math.hypot(live['u']-picked['u'], live['v']-picked['v']) > 30:
        raise RuntimeError('could not associate the selected box with the fresh frame')
    z, count = measure(fresh['depth'], live)
    if z is None or count < 400:
        raise RuntimeError('selected box has insufficient valid live depth')
    x, y, w, h = live['bbox_xywh']
    k = live_view['K']
    # The camera is 15 mm to the left of the rear-axle centreline.
    # Sample the selected surface where the straight approach ray meets it.
    lane_u = k[2] + k[0] * .015 / z
    if not x+12 <= lane_u <= x+w-12:
        raise RuntimeError('straight approach ray does not pass through the selected box')
    lane_depth = depth_stats(fresh['depth'], lane_u, y+h/2)
    z = lane_depth['median_m']
    if z is None or lane_depth['valid'] < 400:
        raise RuntimeError('selected surface is missing depth on the approach ray')
    camera = backproject(lane_u, y+h/2, z, k)
    p = PointStamped()
    p.header.stamp = fresh['stamp']
    p.header.frame_id = fresh['info'].header.frame_id
    p.point.x, p.point.y, p.point.z = (float(v) for v in camera)
    tf = node.tf_buffer.lookup_transform('map', p.header.frame_id, fresh['stamp'])
    target = do_transform_point(p, tf).point
    c, s = math.cos(pose[2]), math.sin(pose[2])
    dx, dy = target.x-pose[0], target.y-pose[1]
    advance = c*dx + s*dy - FRONT_LENGTH - SURFACE_STANDOFF_M
    if abs(-s*dx+c*dy) > .06 or not 1.2 <= advance <= 2.25:
        raise RuntimeError('selected box is outside the validated straight approach')
    report['fresh_measurement'] = {'stamp_ns': fresh['stamp_ns'], 'pose': pose,
                                   'pixel': [lane_u, y+h/2], 'depth_m': z,
                                   'target_map': [target.x, target.y, target.z]}
    return (pose[0] + advance*c, pose[1] + advance*s, pose[2]), pose


def planned_approach(node, pose, goal, straight):
    status, path = node.plan(pose, goal, timeout=5.0)
    if status != 4 or len(path) < 2:
        raise RuntimeError(f'planning failed: status={status}, poses={len(path)}')
    xy = [(p.pose.position.x, p.pose.position.y) for p in path]
    cross_track = max(abs(-math.sin(goal[2])*(x-pose[0])+math.cos(goal[2])*(y-pose[1]))
                      for x, y in xy)
    yaw_error = max(angular_error(yaw_of_quat(p.pose.orientation), goal[2]) for p in path)
    end_error = math.dist(xy[-1], goal[:2])
    if straight and (cross_track > .12 or yaw_error > .19 or end_error > .10):
        raise RuntimeError(f'plan is not straight: cross={cross_track:.3f}, yaw={yaw_error:.3f}, end={end_error:.3f}')
    if node.costmap is None or not path_cost_clear(node.costmap, path):
        raise RuntimeError('path did not clear the live costmap')
    if straight and not all(footprint_clear(node.costmap, p.pose.position.x, p.pose.position.y,
                                           yaw_of_quat(p.pose.orientation)) for p in path):
        raise RuntimeError('sampled straight approach footprint did not clear the live costmap')
    return {'status': status, 'max_cross_track_m': cross_track, 'max_yaw_error_rad': yaw_error,
            'endpoint_error_m': end_error, 'poses': xy}


def run(args, layout, report):
    rclpy.init(args=[sys.argv[0], '--ros-args', '-p', 'use_sim_time:=true'])
    cam = DockLocalizer(layout)
    try:
        frame, view = snapshot(cam)
        pose = view['robot_pose']
        report['view'] = view
        if args.mode == 'vlm':
            goal, pose = model_goal(args, cam, layout, frame, view, report)
        else:
            key = 'observation_pose' if args.mode == 'observe' else 'expected_dock'
            goal = tuple(layout[key][k] for k in ('x', 'y', 'yaw'))
        report['proposed_goal'] = goal
        report['plan'] = planned_approach(cam, pose, goal, args.mode != 'observe')
    finally:
        cam.destroy_node()

    nav = EvalNode('amcl')
    try:
        nav.spin_wall(1.0)
        if not (0 < nav.sim_s() < 100000 and nav.truth is not None and nav.odom is not None):
            raise RuntimeError('simulation clock, truth or odometry unavailable')
        report['start_truth'] = nav.truth
        report['sent_goal'] = goal
        report['nav'] = nav.send_goal(*goal, budget_sim=30.0, wall_budget=60.0)
        cancel = report['nav']['cancel']
        if report['nav']['status'] is None or (cancel and not cancel['ended']):
            raise RuntimeError('navigation did not reach a terminal state')
        report['stop'] = nav.collect_stop(hold_s=1.0, max_wait_s=8.0)
        report['final_truth'] = nav.truth
        centre = goal if args.mode == 'observe' else tuple(layout['parking_zone'][k] for k in ('x','y','yaw'))
        report['parking_error_m'] = math.dist(nav.truth[:2], centre[:2])
        report['parking_yaw_error_rad'] = angular_error(nav.truth[2], centre[2])
        report['pass'] = (report['nav']['status'] == 4 and report['parking_error_m'] <= .30
                          and report['parking_yaw_error_rad'] <= .50 and report['stop']['ok']
                          and report['stop']['truth_displacement_m'] is not None
                          and report['stop']['truth_displacement_m'] <= .05)
    finally:
        nav.destroy_node()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', choices=('observe', 'oracle', 'vlm'), required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--port', type=int, default=18081)
    args = ap.parse_args()
    args.api, args.model, args.curl = 'llamacpp', 'qwen-vl', shutil.which('curl.exe')
    args.out.mkdir()
    report = {'mode': args.mode, 'pass': False, 'contact': 'not_measured'}
    try:
        layout = json.loads(LAYOUT.read_text(encoding='utf-8'))
        guarded_scene(layout)
        run(args, layout, report)
    except (RuntimeError, ValueError, OSError, LookupError) as exc:
        report['error'] = str(exc)
    finally:
        if rclpy.ok():
            rclpy.shutdown()
        with (args.out / 'report.json').open('x', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, allow_nan=False)
    print(json.dumps({k: report.get(k) for k in ('mode', 'pass', 'error', 'sent_goal', 'final_truth',
                                                'parking_error_m', 'parking_yaw_error_rad', 'stop')},
                     ensure_ascii=False))
    return 0 if report['pass'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
