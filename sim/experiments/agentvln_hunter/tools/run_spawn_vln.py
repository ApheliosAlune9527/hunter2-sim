#!/usr/bin/env python3
"""Run one language-guided, face-on docking episode from the original spawn."""

import argparse
import base64
from itertools import product
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np
import rclpy
from action_msgs.msg import GoalStatusArray
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import FollowPath
from nav2_msgs.srv import ClearEntireCostmap
from nav_msgs.msg import Path as PathMsg
from rclpy.action import ActionClient
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from candidate_builder import yaw_of_quat
from run_spawn_observation import checked_observation_path, save_observation
from run_straight_dock import LAYOUT, angular_error, guarded_scene, snapshot
from run_nav_eval_fix import EvalNode, SPAWN
from target_dock import DockLocalizer, FRONT_LENGTH, detect_blue
from vlm_smoke import ask, measure, truth_map


MIN_STRAIGHT = 0.42
LATERAL_TOL = 0.12
YAW_TOL = 0.12
STANDOFF_MIN = 0.16
STANDOFF_MAX = 0.95


def visible_pair(candidates):
    if len(candidates) != 2:
        return False
    boxes = sorted(row['bbox_xywh'] for row in candidates)
    return (boxes[1][0] - boxes[0][0] - boxes[0][2] >= 12
            and all(x >= 8 and y >= 8 and x+w <= 632 and y+h <= 472
                    for x, y, w, h in boxes))


def choose_target(args, view, depth, image, report):
    if not visible_pair(view['candidates']):
        raise RuntimeError('two distinct blue candidates are not fully visible')
    measured = []
    for candidate in view['candidates']:
        distance, count = measure(depth, candidate)
        if distance is None or count < 400:
            raise RuntimeError('insufficient valid depth to compare blue boxes')
        measured.append((candidate['id'], distance))
    ranked = sorted(measured, key=lambda row: row[1])
    report['depth_order_near_to_far'] = ranked
    if ranked[-1][1] - ranked[0][1] < 0.07:
        raise RuntimeError('measured distances are too similar for this trial')
    encoded = base64.b64encode(image).decode('ascii')
    schema = {'type': 'object', 'properties': {'relation': {'enum': ['farther', 'nearer']}},
              'required': ['relation'], 'additionalProperties': False}
    prompt = (f'从这条中文停车指令中提取用户要求的距离关系：「{args.instruction}」。\n'
              '“较远”或“更远”对应 farther。“较近”或“更近”对应 nearer。'
              '程序会另外测距。请仅根据指令输出距离关系 JSON。')
    raw, elapsed, _, model = ask(args, encoded, prompt, response_schema=schema)
    decoded = json.loads(raw)
    report['model_intent'] = {'prompt': prompt, 'response': decoded, 'wall_ms': elapsed, 'model': model}
    expected_relation = 'farther' if args.farther else 'nearer'
    if decoded != {'relation': expected_relation}:
        raise RuntimeError('model did not extract the requested distance relation')
    selected = ranked[-1 if decoded['relation'] == 'farther' else 0][0]
    report['candidate_resolution'] = 'language_intent_with_measured_depth'
    report['selected_candidate'] = selected
    relation = '较远' if decoded['relation'] == 'farther' else '较近'
    print(f'[语言] 模型理解的距离关系是「{relation}」', flush=True)
    distances = '，'.join(f'#{cid} {value:.3f} m' for cid, value in ranked)
    print(f'[测距] {distances}，结合指令选择 #{selected}', flush=True)
    return next(row for row in view['candidates'] if row['id'] == selected)


def fit_face(rgb, depth, view, candidate):
    """Fit the dominant visible vertical face in the horizontal map plane."""
    x, y, width, height = candidate['bbox_xywh']
    lo, hi = y + height//8, y + 7*height//8
    region = cv2.cvtColor(rgb[lo:hi, x:x+width], cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(region, (90, 120, 70), (140, 255, 255)) != 0
    region_depth = depth[lo:hi, x:x+width]
    valid = mask & np.isfinite(region_depth) & (region_depth > 0.1) & (region_depth < 12)
    fx, fy, cx, cy = (view['K'][i] for i in (0, 4, 2, 5))
    points = []
    for col in range(1, width-1):
        rows = np.flatnonzero(valid[:, col])
        if len(rows) < 6:
            continue
        z = float(np.median(region_depth[rows, col]))
        points.append(((x+col-cx)*z/fx, (lo+np.median(rows)-cy)*z/fy, z))
    if len(points) < 16:
        raise RuntimeError('too few depth columns for face fitting')
    points = np.asarray(points)
    camera = view['camera_to_map']
    vector = np.asarray(camera['quaternion_xyzw'][:3])
    w = camera['quaternion_xyzw'][3]
    origin = np.asarray(camera['translation'])
    world = (points + 2*np.cross(vector, np.cross(vector, points)+w*points) + origin)[:, :2]
    subsample = world[::2]
    i, j = np.triu_indices(len(subsample), k=1)
    direction = subsample[j] - subsample[i]
    lengths = np.linalg.norm(direction, axis=1)
    span_ok = lengths > 0.13
    normals = direction[span_ok, ::-1] * np.array([-1., 1.]) / lengths[span_ok, None]
    if not len(normals):
        raise RuntimeError('box face has insufficient horizontal span')
    offsets = np.sum(normals * subsample[i[span_ok]], axis=1)
    residuals = np.abs(world @ normals.T - offsets)
    support = residuals < 0.015
    best = np.argmax(support.sum(axis=0))
    inliers = world[support[:, best]]
    if len(inliers) < max(14, len(world)*0.40):
        raise RuntimeError('no stable box face in the selected region')
    mean = inliers.mean(axis=0)
    _, _, vectors = np.linalg.svd(inliers-mean, full_matrices=False)
    tangent, normal = vectors
    pmin, pmax = np.quantile((inliers-mean) @ tangent, (0.02, 0.98))
    centre = mean + (pmin+pmax)/2*tangent
    if np.dot(origin[:2]-centre, normal) < 0:
        normal = -normal
    if pmax-pmin < 0.16:
        raise RuntimeError('dominant box face is too narrow to center the car')
    heading = math.atan2(-normal[1], -normal[0])
    return {'centre': centre.tolist(), 'heading': heading, 'span_m': float(pmax-pmin),
            'columns': len(inliers), 'residual_m': float(np.median(np.abs((inliers-centre) @ normal)))}


def swept_cost(path, costmap, padding):
    px, py = np.meshgrid(np.linspace(-0.184-padding, 0.834+padding, 22),
                         np.linspace(-0.393-padding, 0.393+padding, 18))
    x, y, yaw = path.T[:, :, None]
    a, b = np.cos(yaw), np.sin(yaw)
    gx = x + a*px.ravel() - b*py.ravel()
    gy = y + b*px.ravel() + a*py.ravel()
    i = np.floor((gx-costmap.origin_x)/costmap.resolution).astype(int)
    j = np.floor((gy-costmap.origin_y)/costmap.resolution).astype(int)
    if i.min() < 0 or i.max() >= costmap.width or j.min() < 0 or j.max() >= costmap.height:
        return 101
    costs = costmap.data[j*costmap.width+i]
    return 101 if costs.min() < 0 else int(costs.max())


def alignment_plan(start, face, camera):
    """Plan a low-curvature entry to a face-normal line, then extend it straight."""
    heading = face['heading']
    centre = np.asarray(face['centre'])
    direction = np.array([math.cos(heading), math.sin(heading)])
    side = np.array([-direction[1], direction[0]])
    costmap = camera.costmap
    candidates = []
    for entry_gap, lateral in product((0.56, 0.64, 0.72), (0., -.035, .035, -.065, .065)):
        point = centre - direction*(FRONT_LENGTH+entry_gap) + lateral*side
        status, poses = camera.plan(start, (float(point[0]), float(point[1]), heading))
        if status != 4 or len(poses) < 3:
            continue
        path = np.array([(p.pose.position.x, p.pose.position.y, yaw_of_quat(p.pose.orientation))
                         for p in poses])
        entry = path[-1]
        turn = max(angular_error(a, heading) for a in path[:, 2])
        entry_offset = float((entry[:2]-centre) @ side)
        if (turn > 1.20 or abs(entry_offset) > 0.085
                or np.linalg.norm(entry[:2]-point) > 0.09 or angular_error(entry[2], heading) > 0.09):
            continue
        # Use the returned endpoint so the two segments meet without a lateral jump.
        straight = float((centre-entry[:2]) @ direction)-FRONT_LENGTH-0.20
        if straight < MIN_STRAIGHT:
            continue
        steps = np.linspace(0., straight, math.ceil(straight/0.04)+1)[1:]
        points = entry[:2] + steps[:, None]*direction
        path = np.vstack((path, np.column_stack((points, np.full(len(steps), heading)))))
        cost = swept_cost(path, costmap, 0.)
        margin_cost = swept_cost(path, costmap, 0.085)
        if cost >= 99 or margin_cost >= 100:
            continue
        length = float(np.linalg.norm(np.diff(path[:, :2], axis=0), axis=1).sum())
        score = 0.008*cost+0.005*margin_cost+4*abs(entry_offset)+0.45*turn-.35*straight+0.05*length
        candidates.append((score, path, {'planner': 'Smac Hybrid DUBIN and straight extension',
                                         'planned_standoff_m': 0.20,
                                         'lateral_offset_m': entry_offset, 'straight_m': straight,
                                         'peak_heading_error_rad': turn, 'length_m': length,
                                         'max_cost': cost, 'padded_max_cost': margin_cost}))
    if not candidates:
        raise RuntimeError('no clear forward alignment path to the measured face')
    _, path, summary = min(candidates, key=lambda item: item[0])
    return path, summary


def pose_path(node, points):
    msg = PathMsg()
    msg.header.frame_id = 'map'
    msg.header.stamp = node.get_clock().now().to_msg()
    for x, y, yaw in points:
        p = PoseStamped(header=msg.header)
        p.pose.position.x = float(x)
        p.pose.position.y = float(y)
        p.pose.orientation.z = math.sin(yaw/2)
        p.pose.orientation.w = math.cos(yaw/2)
        msg.poses.append(p)
    return msg


def follow(nav, client, path, budget, monitor=None):
    action = FollowPath.Goal(path=path, controller_id='FollowPath', goal_checker_id='general_goal_checker')
    result = nav.send_action(client, action, budget_sim=budget, wall_budget=budget+16, on_tick=monitor)
    result['stop'] = nav.collect_stop(hold_s=1., max_wait_s=6., wall_budget=12.)
    result['final_truth'] = nav.truth
    return result


def evaluate(layout, view, report, truth):
    actual = truth_map(view, layout).get(report['selected_candidate'])
    if actual is None or truth is None:
        raise RuntimeError('independent box or vehicle truth unavailable')
    box = next(item for item in layout['blue_boxes'] if item['name'] == actual)
    yaw = round(report['face']['heading']/(math.pi/2))*math.pi/2
    direction = np.array([math.cos(yaw), math.sin(yaw)])
    side = np.array([-direction[1], direction[0]])
    face = np.array([box['x'], box['y']])-direction*(np.abs(direction) @ np.array(box['size'][:2]))/2
    delta = face - np.array(truth[:2])
    return {'box': actual, 'target_correct': actual == ('blue_far' if report['farther'] else 'blue_near'),
            'yaw_error_rad': angular_error(truth[2], yaw), 'lateral_m': abs(float(delta @ side)),
            'front_standoff_m': float(delta @ direction)-FRONT_LENGTH}


def docking_checks(dock, evaluation):
    return (('停靠动作', dock['status'] == 4),
            ('目标选择', evaluation['target_correct']),
            ('朝向偏差', evaluation['yaw_error_rad'] <= YAW_TOL),
            ('横向偏差', evaluation['lateral_m'] <= LATERAL_TOL),
            ('箱面间距', STANDOFF_MIN <= evaluation['front_standoff_m'] <= STANDOFF_MAX),
            ('停稳检查', dock['stop']['ok']))


def check_idle(nav):
    qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                     reliability=ReliabilityPolicy.RELIABLE)
    statuses = {}
    for name in ('follow_path', 'navigate_to_pose', 'navigate_through_poses'):
        nav.create_subscription(GoalStatusArray, f'/{name}/_action/status',
                                lambda msg, name=name: statuses.update({name: msg.status_list}), qos)
    nav.spin_wall(1.5)
    if any(item.status in (1, 2, 3) for items in statuses.values() for item in items):
        raise RuntimeError('another navigation action is still active')
    if nav.odom is None or max(abs(nav.odom[3]), abs(nav.odom[4])) > 0.03:
        raise RuntimeError('vehicle is not verified stationary')


def refresh_costmaps(camera):
    # Reset scan markings left at prior simulated poses, then let live scans refill them.
    for name in ('global', 'local'):
        service = camera.create_client(ClearEntireCostmap, f'/{name}_costmap/clear_entirely_{name}_costmap')
        if not service.wait_for_service(timeout_sec=3.):
            raise RuntimeError(f'{name} costmap reset service unavailable')
        future = service.call_async(ClearEntireCostmap.Request())
        rclpy.spin_until_future_complete(camera, future, timeout_sec=4.)
        if not future.done() or future.result() is None:
            raise RuntimeError(f'{name} costmap reset did not complete')
    camera.costmap = None
    deadline = time.monotonic() + 2.3
    while time.monotonic() < deadline:
        rclpy.spin_once(camera, timeout_sec=0.05)
    if camera.costmap is None:
        raise RuntimeError('no fresh costmap after simulation reset')


def episode(args, report):
    layout = json.loads(LAYOUT.read_text(encoding='utf-8'))
    guarded_scene(layout)
    rclpy.init(args=[sys.argv[0], '--ros-args', '-p', 'use_sim_time:=true'])
    camera, nav = DockLocalizer(layout), EvalNode('amcl')
    client = ActionClient(nav, FollowPath, 'follow_path')
    try:
        deadline = time.monotonic()+6
        while (nav.truth is None or nav.odom is None or nav.sim_s() <= 0) and time.monotonic() < deadline:
            rclpy.spin_once(nav, timeout_sec=0.1)
        check_idle(nav)
        if args.reset_to_spawn:
            subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('reset_and_seed.py')),
                            *(str(v) for v in SPAWN), '0.0025', '--ros-args', '-p', 'use_sim_time:=true'],
                           check=True, timeout=40)
            nav.spin_wall(1.)
        if (nav.truth is None or nav.odom is None or nav.sim_s() <= 0 or math.dist(nav.truth[:2], SPAWN[:2]) > .05
                or angular_error(nav.truth[2], SPAWN[2]) > .07 or max(abs(nav.odom[3]), abs(nav.odom[4])) > .03):
            raise RuntimeError('start must be stationary at the original world spawn')
        refresh_costmaps(camera)
        report['costmaps_refreshed_at_spawn'] = True
        report['start_truth'] = nav.truth
        report['instruction'] = args.instruction
        report['farther'] = args.farther
        print('出生点确认，任务即将开始', flush=True)
        print(f'[指令] {args.instruction}', flush=True)
        nav.spin_wall(3.)
        _, initial = snapshot(camera)
        report['initial_view'] = initial
        print(f'[视觉] 出生点检测到 {len(initial["candidates"])} 个蓝色候选', flush=True)
        if not visible_pair(initial['candidates']):
            view_goal, plan = checked_observation_path(camera, initial['robot_pose'])
            report['requested_view'] = view_goal
            print('[决策] 当前画面不足以比较远近，先驶向观察位', flush=True)
            last_frame = initial['stamp_ns']

            def watch_view():
                nonlocal last_frame
                for _ in range(6):
                    rclpy.spin_once(camera, timeout_sec=0.)
                f = camera.frame
                if f is None or f['stamp_ns'] <= last_frame:
                    return
                last_frame = f['stamp_ns']
                if 'first_pair_during_observation' not in report:
                    boxes = [{'bbox_xywh': row['bbox']} for row in detect_blue(f['rgb'])]
                    if visible_pair(boxes):
                        report['first_pair_during_observation'] = {'stamp_ns': last_frame, 'truth': nav.truth}
                        print('[视觉] 行驶中看到两个可区分的蓝色候选', flush=True)

            observation = follow(nav, client, PathMsg(header=plan[0].header, poses=plan), 20., watch_view)
            report['observation_motion'] = observation
            if observation['status'] != 4 or not observation['stop']['ok']:
                raise RuntimeError('could not complete the observation leg')
        frame, view = save_observation(camera, args.out, report)
        print(f'[视觉] 停在观察位，当前画面有 {len(view["candidates"])} 个蓝色候选', flush=True)
        candidate = choose_target(args, view, frame['depth'], (args.out/'observation_numbered.png').read_bytes(), report)
        face = fit_face(frame['rgb'], frame['depth'], view, candidate)
        report['face'] = face
        if camera.wait_costmap(5.) is None:
            raise RuntimeError('live costmap unavailable')
        path, summary = alignment_plan(tuple(view['robot_pose']), face, camera)
        summary['goal'] = path[-1].tolist()
        report['alignment_plan'] = summary
        report['alignment_waypoints'] = path.tolist()
        print(f'[规划] 用 #{candidate["id"]} 的箱面生成路径，末段直进 {summary["straight_m"]:.2f} m', flush=True)
        print('[执行] Nav2 开始跟踪对正停靠路径', flush=True)
        dock = follow(nav, client, pose_path(nav, path), 70.)
        report['dock_motion'] = dock
        evaluation = evaluate(layout, view, report, dock['final_truth'])
        report['evaluation'] = evaluation
        report['pass'] = all(passed for _, passed in docking_checks(dock, evaluation))
    finally:
        camera.destroy_node()
        nav.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def action_status(motion):
    if motion is None:
        return '未执行'
    code = motion.get('status')
    if code is None:
        return '未确认终态'
    return {4: 'SUCCEEDED (4)', 5: 'CANCELED (5)', 6: 'ABORTED (6)'}.get(code, f'状态码 {code}')


def print_summary(report, report_path):
    dock = report.get('dock_motion')
    evaluation = report.get('evaluation')
    rows = [('总体结果', '通过' if report['pass'] else '未通过')]
    if report.get('start_truth') is not None:
        x, y, yaw = report['start_truth']
        rows.append(('原始起点', f'x={x:.3f} m，y={y:.3f} m，航向={math.degrees(yaw):.2f}°'))
    if 'observation_motion' in report:
        rows.append(('观察动作', action_status(report['observation_motion'])))
    selected = report.get('selected_candidate')
    if selected is not None:
        target = f'#{selected}'
        if evaluation is not None:
            box = {'blue_far': '远蓝箱', 'blue_near': '近蓝箱'}.get(evaluation['box'], evaluation['box'])
            target += f' {box}（{"符合指令" if evaluation["target_correct"] else "与指令不符"}）'
        rows.append(('选择目标', target))
    rows.append(('停靠动作', action_status(dock)))
    if evaluation is not None:
        rows.extend((('朝向偏差', f'{math.degrees(evaluation["yaw_error_rad"]):.2f}°（上限 {math.degrees(YAW_TOL):.2f}°）'),
                     ('横向偏差', f'{100*evaluation["lateral_m"]:.2f} cm（上限 {100*LATERAL_TOL:.2f} cm）'),
                     ('箱面间距', f'{100*evaluation["front_standoff_m"]:.2f} cm')))
    stop = dock.get('stop') if dock else None
    if stop is None:
        rows.append(('停稳检查', '未测'))
    else:
        result = '通过' if stop['ok'] else '未通过'
        duration, distance = stop.get('truth_window_s'), stop.get('truth_displacement_m')
        if duration is not None and distance is not None:
            result += f'（{duration:.3f} s 内位移 {1000*distance:.1f} mm）'
        rows.append(('停稳检查', result))
    if dock is not None and evaluation is not None and not report['pass']:
        failures = '、'.join(label for label, passed in docking_checks(dock, evaluation) if not passed)
        if failures:
            rows.append(('未通过项', failures))
    if report.get('error'):
        rows.append(('运行错误', report['error']))
    rows.append(('报告文件', str(report_path)))
    print('\n========== 本轮验收 ==========')
    for label, value in rows:
        print(f'{label}    {value}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instruction', required=True)
    parser.add_argument('--reset-to-spawn', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--port', type=int, default=18081)
    args = parser.parse_args()
    args.farther = any(word in args.instruction for word in ('较远', '更远'))
    nearer = any(word in args.instruction for word in ('较近', '更近'))
    if '蓝箱' not in args.instruction or args.farther == nearer:
        parser.error('instruction must specify exactly one distance relation for the blue box')
    args.api, args.model, args.curl = 'llamacpp', 'qwen-vl', shutil.which('curl.exe')
    if not args.curl:
        parser.error('Windows curl.exe is required')
    args.out.mkdir()
    report_path = args.out/'report.json'
    report = {'pass': False, 'error': None, 'contact': 'not_measured'}
    try:
        episode(args, report)
    except (RuntimeError, ValueError, OSError, LookupError, subprocess.SubprocessError) as exc:
        report['error'] = str(exc)
    finally:
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    print_summary(report, report_path)
    return 0 if report['pass'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
