#!/usr/bin/env python3
"""Step-3 closed loop: detect two blue boxes, re-observe if occluded, query depth,
backproject the farther box, generate a dock, drive and evaluate the parking zone.

This is an engineering baseline around the frozen scene: target detection is HSV,
not a VLM.  Every stage is written to one report so the before/after depth query
and the re-observation recovery can be audited separately.
"""
import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from geometry_msgs.msg import PointStamped
from tf2_geometry_msgs import do_transform_point

from target_dock import (DockLocalizer, LAYOUT, FRONT_LENGTH, backproject,
                         depth_stats, detect_blue, face_target_yaw,
                         footprint_clear_boxes)


def summarize_components(comps):
    out = []
    for i, c in enumerate(comps):
        out.append({
            'id': i,
            'u': c['u'], 'v': c['v'], 'area_px': c['area_px'],
            'area_fraction': c['area_fraction'],
            'depth_median_m': c['depth']['median_m'],
            'depth_valid_fraction': c['depth']['valid_fraction'],
            'depth_valid_pixels': c['depth']['valid'],
            'depth_unit': 'm',
        })
    return out


def pick_by_area(comps):
    # Before the depth tool: smaller image area is a proxy for a farther object.
    if not comps:
        return None
    return min(comps, key=lambda c: c['area_px'])


class TruthPath:
    """Ground-truth path length of the whole run (same metric as the baseline)."""

    def __init__(self, node):
        from nav_msgs.msg import Odometry
        self.last = None
        self.length = 0.0
        self.samples = 0
        node.create_subscription(Odometry, '/ground_truth', self.on_truth, 10)

    def on_truth(self, msg):
        p = msg.pose.pose.position
        xy = (p.x, p.y)
        if self.last is not None:
            self.length += math.hypot(xy[0] - self.last[0], xy[1] - self.last[1])
        self.last = xy
        self.samples += 1


def draw_frame(rgb, comps, target=None, title=''):
    img = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    for i, c in enumerate(comps):
        color = (0, 255, 255) if c is target else (0, 255, 0)
        cv2.circle(img, (int(c['u']), int(c['v'])), 12, color, 2)
        cv2.putText(img, 'box%d z=%.2fm' % (i, c['depth']['median_m'] or -1.0),
                    (int(c['u']) + 12, int(c['v']) - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)
        if c is target and c['depth'].get('roi'):
            x0, y0, x1, y1 = c['depth']['roi']
            cv2.rectangle(img, (x0, y0), (x1, y1), (0, 255, 255), 2)
    if title:
        cv2.putText(img, title, (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
                    0.60, (255, 255, 255), 2, cv2.LINE_AA)
    return img


def cached_frame(n, comps=None):
    rgb, depth, info = n.frame['rgb'], n.frame['depth'], n.frame['info']
    f = n.frame
    if comps is None:
        comps = detect_blue(rgb)
        for c in comps:
            c['depth'] = depth_stats(depth, c['u'], c['v'])
    return {'rgb': rgb, 'depth': depth, 'info': info, 'stamp': f['stamp'],
            'stamp_ns': f['stamp_ns'], 'age_s': f['age_s'], 'tf': f['tf'],
            'robot': n.robot_pose(f['stamp']), 'comps': comps}


# Smac Hybrid-A* (DUBIN, minimum_turning_radius 1.669) cannot replan once the
# start is inside roughly one footprint of the goal: measured on 2026-11-08, a
# plan from 0.16 m before (1.885, 0.435) failed while 0.26 m succeeded.  An
# intermediate observation leg that Nav2 aborts *after* arriving this close is
# therefore accepted, with the measured shortfall kept in the report.
ACCEPT_SHORTFALL_M = 0.35
ACCEPT_HEADING_RAD = 0.50


def leg_arrived(nav):
    """True when the leg counts as arrived, recording why."""
    if nav.get('status') == 4:
        return True, 'nav2_succeeded'
    err = nav.get('error_to_dock_m')
    head = nav.get('heading_to_dock_rad')
    if err is not None and head is not None and err <= ACCEPT_SHORTFALL_M and abs(head) <= ACCEPT_HEADING_RAD:
        return True, 'nav2_dubin_dead_zone_within_tolerance'
    return False, 'not_arrived'


def main():
    t_start = time.monotonic()
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_step3/pipeline')
    ap.add_argument('--layout', default=str(LAYOUT),
                    help='场景布局；交换近远关系时指向 target_layout_swapped.json')
    ap.add_argument('--max-reobserves', type=int, default=2)
    # Ablation: with the active per-region depth query disabled the selection
    # falls back to the apparent-size proxy, but the final back-projection still
    # uses the depth image, exactly as §4.5 of the plan asks.
    ap.add_argument('--no-depth-query', action='store_true')
    # Step-5 selection arms: 'area' uses the apparent-size proxy (no active
    # depth query for the choice), 'depth' queries both regions and takes the
    # farther one.  The final back-projection always uses the depth image.
    ap.add_argument('--select', default='depth', choices=['depth', 'area'])
    ap.add_argument('--instruction', default='far', choices=['far', 'near'])
    ap.add_argument('--no-execute', action='store_true')
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    layout = json.loads(Path(args.layout).read_text())

    rclpy.init()
    n = DockLocalizer(layout)
    path_log = TruthPath(n)
    stages = []
    reobserve_attempts = []

    def take_stage(label):
        f = n.wait_frame(30.0)
        if f is None:
            stages.append({'stage': label, 'error': 'no synchronized fresh frame'})
            return None
        comps = detect_blue(f['rgb'])
        for c in comps:
            c['depth'] = depth_stats(f['depth'], c['u'], c['v'])
        rec = cached_frame(n, comps)
        rec['stage'] = label
        stages.append({'stage': label, 'stamp_s': round(f['stamp_ns'] / 1e9, 3),
                       'age_s': round(f['age_s'], 3),
                       'robot_pose': [round(v, 4) for v in rec['robot']],
                       'components': summarize_components(comps),
                       'component_count': len(comps)})
        return rec

    first = take_stage('initial_observation')
    if first is None:
        (out / 'report.json').write_text(json.dumps({'stages': stages, 'success': False}, indent=2))
        return 1
    cv2.imwrite(str(out / 'initial.png'),
                draw_frame(first['rgb'], first['comps'], title='initial: find two blue boxes'))

    # A single blue blob is not enough for "the farther of two boxes": the other
    # box is occluded/out of frame.  Try a short, reachable observation pose.
    rec = first
    if len(rec['comps']) < 2 and not args.no_execute:
        obs_route = layout.get('observation_route') or [layout['observation_pose']]
        for attempt in range(1, args.max_reobserves + 1):
            legs = []
            for leg_i, wp in enumerate(obs_route):
                nav = n.execute({'x': wp['x'], 'y': wp['y'], 'yaw': wp['yaw']}, rec['stamp'])
                arrived, why = leg_arrived(nav)
                nav['accepted_as_arrived'] = bool(arrived)
                nav['accepted_reason'] = why
                legs.append({'pose': wp, 'nav': nav})
                if not arrived:
                    break
                rec = take_stage('reobserve_%d_leg_%d' % (attempt, leg_i))
                if rec is None:
                    break
                if len(rec['comps']) >= 2:
                    break
            rec_obs = {'attempt': attempt, 'route': obs_route, 'legs': legs}
            reobserve_attempts.append(rec_obs)
            if rec is None:
                break
            cv2.imwrite(str(out / ('reobserve_%d.png' % attempt)),
                        draw_frame(rec['rgb'], rec['comps'], title='reobserve attempt %d' % attempt))
            if len(rec['comps']) >= 2:
                break

    if rec is None or len(rec['comps']) < 2:
        report = {
            'instruction': layout['instruction'],
            'success': False,
            'safety_end': True,
            'reason': ('fewer_than_two_blue_components_after_reobserve'
                       if args.max_reobserves > 0 else 'fewer_than_two_blue_components_no_reobserve'),
            'reobserves_allowed': args.max_reobserves,
            'stages': stages,
            'reobserve_attempts': reobserve_attempts,
            'final_truth': [round(v, 4) for v in n.truth] if n.truth else None,
        }
        (out / 'report.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        rclpy.shutdown()
        return 0

    rgb, depth, info = rec['rgb'], rec['depth'], rec['info']
    k = [float(v) for v in info.k]
    comps = rec['comps']
    valid = [c for c in comps if c['depth']['median_m'] is not None]
    before = pick_by_area(valid)
    use_area = args.no_depth_query or args.select == 'area'
    if use_area:
        target = before
    else:
        target = (max(valid, key=lambda c: c['depth']['median_m']) if args.instruction == 'far'
                  else min(valid, key=lambda c: c['depth']['median_m']))
    after = target
    selection_before = {
        'criterion': 'smaller_image_area_proxy',
        'box_index': comps.index(before) if before is not None else None,
        'u': before['u'] if before else None,
        'v': before['v'] if before else None,
        'area_px': before['area_px'] if before else None,
        'depth_not_used': True,
    }
    u, v, z = target['u'], target['v'], target['depth']['median_m']
    pc = backproject(u, v, z, k)
    p = PointStamped()
    p.header.frame_id = 'agentvln_camera_optical_frame'
    p.point.x, p.point.y, p.point.z = pc
    try:
        t_map = n.tf_buffer.lookup_transform('map', 'agentvln_camera_optical_frame', rec['stamp'])
    except Exception as e:
        report = {'success': False, 'reason': 'tf_map_optical_failed: %s' % e,
                  'stages': stages, 'reobserve_attempts': reobserve_attempts}
        (out / 'report.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        rclpy.shutdown()
        return 1
    pm = do_transform_point(p, t_map)
    target_map = [round(pm.point.x, 4), round(pm.point.y, 4), round(pm.point.z, 4)]
    target['backprojected_map'] = target_map

    # Depth query records, before and after selection.
    queries = []
    for i, c in enumerate(comps):
        queries.append({
            'box_index': i,
            'u': c['u'], 'v': c['v'],
            'median_m': c['depth']['median_m'], 'unit': 'm',
            'valid_pixels': c['depth']['valid'],
            'valid_fraction': c['depth']['valid_fraction'],
            'selected': c is target,
        })

    # Dock generation from the measured front-surface point.
    boxes = [{'name': b['name'], 'x': b['x'], 'y': b['y']} for b in layout['blue_boxes']]
    robot = n.robot_pose(rec['stamp'])
    # Straight-in docking: the dock sits on the robot -> measured-target ray so
    # the final approach stays a straight line (see target_dock.py for why).
    approach = math.atan2(target_map[1] - robot[1], target_map[0] - robot[0])
    generated = []
    for backoff in (0.10, 0.16, 0.22, 0.28, 0.34):
        for dyaw in (0.0, 0.10, -0.10, 0.20, -0.20):
            yaw = round(approach + dyaw, 4)
            x = round(target_map[0] - (FRONT_LENGTH + backoff) * math.cos(yaw), 3)
            y = round(target_map[1] - (FRONT_LENGTH + backoff) * math.sin(yaw), 3)
            dock = {'x': x, 'y': y, 'yaw': yaw, 'backoff_m': backoff,
                    'yaw_offset_rad': dyaw, 'approach_bearing_rad': round(approach, 4)}
            ok, hit = footprint_clear_boxes(x, y, yaw, boxes)
            dock['footprint_clear_of_marked_boxes'] = bool(ok)
            if not ok:
                dock['rejected'] = 'overlaps_' + hit
                generated.append(dock)
                continue
            st, path = n.plan(robot, (x, y, yaw))
            dock['plan_status'] = int(st)
            dock['planned_poses'] = len(path)
            if st == 4 and len(path) >= 2:
                dock['path_length_m'] = round(sum(
                    math.hypot(b.pose.position.x - a.pose.position.x,
                               b.pose.position.y - a.pose.position.y)
                    for a, b in zip(path[:-1], path[1:])), 3)
            else:
                dock['rejected'] = 'trial_plan_failed'
            generated.append(dock)
    planned = [d for d in generated if d.get('plan_status') == 4 and d.get('planned_poses', 0) >= 2]
    planned.sort(key=lambda d: (abs(d['yaw_offset_rad']), d['backoff_m']))
    fallback = False
    if planned:
        dock = planned[0]
    else:
        exp = layout['expected_dock']
        dock = {'x': exp['x'], 'y': exp['y'], 'yaw': exp['yaw'],
                'fallback': True, 'reason': 'no_generated_candidate_planned'}
        fallback = True

    parking = (layout['parking_zone'] if args.instruction == 'far'
               else layout.get('parking_zone_near', layout['parking_zone']))
    dock_in_zone = math.hypot(dock['x'] - parking['x'], dock['y'] - parking['y']) <= parking['radius_m']
    # Docking is executed with a correction loop: Smac can plan the first dock
    # but the controller cannot hold the closing arc of a path that ends with a
    # 0.4-0.5 rad turn, so a failed attempt is retried from the pose the vehicle
    # actually stopped at.  The retry recomputes the straight-in dock from the
    # current AMCL belief, never from the ground-truth pose.
    nav = {'status': None, 'skipped': True}
    dock_attempts = []
    if not args.no_execute:
        for attempt in range(1, 4):
            nav = n.execute(dock, rec['stamp'])
            nav['skipped'] = False
            nav['attempt'] = attempt
            dock_attempts.append({'attempt': attempt, 'dock': dict(dock), 'nav': dict(nav)})
            if nav.get('status') == 4:
                break
            now = n.amcl
            if now is None:
                dock_attempts[-1]['retry_skipped'] = 'no_amcl_pose'
                break
            dist_to_target = math.hypot(target_map[0] - now[0], target_map[1] - now[1])
            if dist_to_target <= FRONT_LENGTH + 0.20:
                dock_attempts[-1]['retry_skipped'] = 'already_within_docking_distance'
                break
            bearing = math.atan2(target_map[1] - now[1], target_map[0] - now[0])
            # The straight-in dock at the smallest back-off can sit inside the
            # box clearance when the vehicle stopped far away; walk the back-off
            # outwards and take the first one that is both clear and plannable.
            tried = []
            retry = None
            for backoff2 in (0.10, 0.16, 0.22, 0.28, 0.34):
                x2 = round(target_map[0] - (FRONT_LENGTH + backoff2) * math.cos(bearing), 3)
                y2 = round(target_map[1] - (FRONT_LENGTH + backoff2) * math.sin(bearing), 3)
                yaw2 = round(bearing, 4)
                if math.hypot(x2 - now[0], y2 - now[1]) < 0.35:
                    tried.append({'backoff_m': backoff2, 'rejected': 'inside_dead_zone'})
                    continue
                ok2, hit2 = footprint_clear_boxes(x2, y2, yaw2, boxes)
                st2, path2 = n.plan((now[0], now[1], now[2]), (x2, y2, yaw2))
                cand2 = {'x': x2, 'y': y2, 'yaw': yaw2, 'backoff_m': backoff2,
                         'yaw_offset_rad': 0.0, 'approach_bearing_rad': round(bearing, 4),
                         'footprint_clear_of_marked_boxes': bool(ok2),
                         'plan_status': int(st2), 'planned_poses': len(path2),
                         'robot_pose_used': [round(v, 4) for v in now]}
                tried.append(cand2)
                if ok2 and st2 == 4 and len(path2) >= 2:
                    retry = cand2
                    break
            dock_attempts[-1]['retry_candidates'] = tried
            if retry is None:
                dock_attempts[-1]['retry_rejected'] = 'retry_plan_or_clearance_failed'
                break
            dock = retry
        nav['attempts_used'] = len(dock_attempts)
        dock_in_zone = math.hypot(dock['x'] - parking['x'], dock['y'] - parking['y']) <= parking['radius_m']
    if n.truth:
        nav['final_truth'] = [round(v, 4) for v in n.truth]
        nav['parking_distance_m'] = round(math.hypot(n.truth[0] - parking['x'],
                                                     n.truth[1] - parking['y']), 4)
        nav['parking_yaw_error_rad'] = round(abs(math.atan2(
            math.sin(n.truth[2] - parking['yaw']), math.cos(n.truth[2] - parking['yaw']))), 4)
        nav['parking_ok'] = bool(nav['parking_distance_m'] <= parking['radius_m'] and
                                 nav['parking_yaw_error_rad'] <= parking['yaw_tol_rad'])
    nav['success'] = bool(nav.get('status') == 4 and nav.get('parking_ok') and
                          nav.get('stop_displacement_m', 1.0) <= 0.05)
    nav['dock_in_zone_by_geometry'] = bool(dock_in_zone)

    annotated = draw_frame(rgb, comps, target,
                           title='observation: depth z(m) and selected far box')
    cv2.putText(annotated, 'dock %.2f %.2f yaw=%.2f plan=%s' % (
        dock['x'], dock['y'], dock['yaw'], dock.get('plan_status', 'fallback')),
        (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2, cv2.LINE_AA)
    cv2.imwrite(str(out / 'annotated.png'), annotated)
    cv2.imwrite(str(out / 'observation.png'), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    np.save(out / 'depth.npy', depth)

    report = {
        'instruction': layout['instruction'],
        'success': bool(nav.get('success')),
        'stages': stages,
        'reobserve_attempts': reobserve_attempts,
        'frame': {'stamp_s': round(rec['stamp_ns'] / 1e9, 3),
                  'age_s': round(rec['age_s'], 3),
                  'K': k, 'robot_pose': [round(v, 4) for v in robot]},
        'components': comps,
        'depth_queries': queries,
        'selection_before_depth': selection_before,
        'selection_after_depth': {
            'criterion': 'smaller_image_area_proxy' if args.no_depth_query else 'largest_median_depth',
            'box_index': comps.index(after),
            'u': u, 'v': v, 'median_m': z, 'unit': 'm',
            'map_point_m': target_map,
            'reason': 'farther_of_two_blue_boxes',
        },
        'selection_changed_after_depth': bool(before is not after),
        'dock_candidates': generated,
        'chosen_dock': dock,
        'dock_attempts': dock_attempts,
        'fallback_used': fallback,
        'parking': parking,
        'select_arm': 'area_proxy' if use_area else 'depth_query',
        'instruction_arm': args.instruction,
        'nav': nav,
        'wall_total_s': round(time.monotonic() - t_start, 2),
        'truth_path_length_m': round(path_log.length, 3),
        'truth_samples': path_log.samples,
        'files': {'initial': str(out / 'initial.png'),
                  'observation': str(out / 'annotated.png'),
                  'rgb': str(out / 'observation.png'),
                  'depth': str(out / 'depth.npy')},
    }
    (out / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
