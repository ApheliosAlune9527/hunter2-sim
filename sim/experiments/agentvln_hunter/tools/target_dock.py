#!/usr/bin/env python3
"""Query depth for a target region, backproject to map, generate and drive to a dock."""
import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import PointStamped, PoseWithCovarianceStamped, Twist
from message_filters import ApproximateTimeSynchronizer, Subscriber
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CameraInfo, Image
from tf2_geometry_msgs import do_transform_point

from candidate_builder import CandidateBuilder, quat_from_yaw, yaw_of_quat

LAYOUT = Path('/mnt/d/rob-memory/sim/experiments/agentvln_hunter/config/target_layout.json')
FRONT_LENGTH = 0.834
FOOTPRINT = [(-0.184, -0.393), (0.834, -0.393), (0.834, 0.393), (-0.184, 0.393)]


def stamp_ns(msg):
    return msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec


def yaw_to_quat(yaw):
    q = quat_from_yaw(yaw)
    return {'x': q[0], 'y': q[1], 'z': q[2], 'w': q[3]}


def detect_blue(rgb, min_area=500.0):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, (90, 120, 70), (140, 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in contours:
        area = float(cv2.contourArea(c))
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(c)
        m = cv2.moments(c)
        if m['m00'] <= 0:
            continue
        out.append({'u': round(m['m10'] / m['m00'], 2), 'v': round(m['m01'] / m['m00'], 2),
                    'area_px': round(area, 1), 'bbox': [int(x), int(y), int(w), int(h)],
                    'area_fraction': round(area / float(rgb.shape[0] * rgb.shape[1]), 5)})
    out.sort(key=lambda r: r['area_px'], reverse=True)
    return out


def depth_stats(depth, u, v, half=12):
    h, w = depth.shape
    x0, x1 = max(0, int(round(u)) - half), min(w, int(round(u)) + half + 1)
    y0, y1 = max(0, int(round(v)) - half), min(h, int(round(v)) + half + 1)
    patch = depth[y0:y1, x0:x1]
    valid = patch[np.isfinite(patch) & (patch > 0.1) & (patch < 20.0)]
    if valid.size == 0:
        return {'median_m': None, 'mean_m': None, 'valid': 0,
                'valid_fraction': 0.0, 'min_m': None, 'max_m': None,
                'roi': [x0, y0, x1, y1]}
    return {'median_m': round(float(np.median(valid)), 6),
            'mean_m': round(float(np.mean(valid)), 6),
            'valid': int(valid.size), 'valid_fraction': round(valid.size / float(patch.size), 4),
            'min_m': round(float(valid.min()), 6), 'max_m': round(float(valid.max()), 6),
            'roi': [x0, y0, x1, y1]}


def backproject(u, v, z, k):
    fx, fy, cx, cy = k[0], k[4], k[2], k[5]
    return [(u - cx) / fx * z, (v - cy) / fy * z, z]


def poly_intersects_box(poly, cx, cy, half, margin=0.03):
    # Axis-aligned footprint polygon vs axis-aligned target rectangle.
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    box = (cx - half - margin, cy - half - margin, cx + half + margin, cy + half + margin)
    return not (max(xs) < box[0] or min(xs) > box[2] or max(ys) < box[1] or min(ys) > box[3])


def face_target_yaw(target_x, target_y, x, y):
    """Heading that points the vehicle nose at the measured target point.

    A dock generated with yaw 0 asked Smac for a right turn at the very end of
    the approach; from 0.67 m out that needs a 1.31 m radius, below the 1.669 m
    minimum, and the replan failed (pipeline_v5).  Facing the target keeps the
    final heading inside what the planner can still realise.
    """
    return round(math.atan2(target_y - y, target_x - x), 4)


def footprint_poly(x, y, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    return [(x + px * c - py * s, y + px * s + py * c) for px, py in FOOTPRINT]


def footprint_clear_boxes(x, y, yaw, boxes):
    poly = footprint_poly(x, y, yaw)
    for b in boxes:
        if poly_intersects_box(poly, b['x'], b['y'], 0.175):
            return False, b['name']
    return True, None


class DockLocalizer(CandidateBuilder):
    def __init__(self, layout):
        super().__init__('target_dock')
        self.layout = layout
        self.bridge = CvBridge()
        self.clock_ns = None
        self.frame = None
        self.ready_at = time.monotonic() + 2.0
        self.truth = None
        self.amcl = None
        self.create_subscription(Clock, '/clock', self.on_clock, 10)
        self.create_subscription(Odometry, '/ground_truth', self.on_truth, 10)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self.on_amcl, 10)
        self.subs = [
            Subscriber(self, Image, '/hz_sim/agentvln/camera/image', qos_profile=qos_profile_sensor_data),
            Subscriber(self, Image, '/hz_sim/agentvln/camera/depth_image', qos_profile=qos_profile_sensor_data),
            Subscriber(self, CameraInfo, '/hz_sim/agentvln/camera/camera_info', qos_profile=qos_profile_sensor_data),
        ]
        self.sync = ApproximateTimeSynchronizer(self.subs, queue_size=10, slop=0.10)
        self.sync.registerCallback(self.on_frame)
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.cmd = self.create_publisher(Twist, '/cmd_vel', 10)

    def on_clock(self, msg):
        self.clock_ns = msg.clock.sec * 1_000_000_000 + msg.clock.nanosec

    def on_truth(self, msg):
        p = msg.pose.pose
        self.truth = (p.position.x, p.position.y, yaw_of_quat(p.orientation))

    def on_amcl(self, msg):
        p = msg.pose.pose
        self.amcl = (p.position.x, p.position.y, yaw_of_quat(p.orientation))

    def on_frame(self, rgb_msg, depth_msg, info_msg):
        if time.monotonic() < self.ready_at or self.clock_ns is None:
            return
        stamp = rgb_msg.header.stamp
        ns = stamp_ns(rgb_msg)
        age = (self.clock_ns - ns) / 1e9
        if age < 0 or age > 1.5:
            return
        try:
            tf = self.tf_buffer.lookup_transform('agentvln_camera_optical_frame', 'map', stamp)
            self.tf_buffer.lookup_transform('map', 'base_link', stamp, timeout=Duration(seconds=0.05))
        except Exception:
            return
        self.frame = {'rgb': self.bridge.imgmsg_to_cv2(rgb_msg, desired_encoding='rgb8'),
                      'depth': self.bridge.imgmsg_to_cv2(depth_msg, desired_encoding='32FC1'),
                      'info': info_msg, 'stamp': stamp, 'stamp_ns': ns, 'age_s': age, 'tf': tf}

    def wait_frame(self, timeout=25.0):
        self.frame = None
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.frame is not None:
                return self.frame
        return None

    def execute(self, dock, frame_stamp):
        if not self.nav_client.wait_for_server(timeout_sec=5.0):
            return {'status': 0, 'rejected': 'nav_server_unavailable'}
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = frame_stamp
        goal.pose.pose.position.x = dock['x']
        goal.pose.pose.position.y = dock['y']
        q = yaw_to_quat(dock['yaw'])
        goal.pose.pose.orientation.x = q['x']
        goal.pose.pose.orientation.y = q['y']
        goal.pose.pose.orientation.z = q['z']
        goal.pose.pose.orientation.w = q['w']
        t0 = time.monotonic()
        fut = self.nav_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=8.0)
        handle = fut.result()
        if handle is None or not handle.accepted:
            return {'status': 0, 'rejected': 'goal_rejected'}
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
        out = {'status': int(status) if status is not None else None,
               'timed_out': timed_out, 'wall_s': round(time.monotonic() - t0, 3),
               'truth_after': [round(v, 4) for v in self.truth] if self.truth else None}
        if self.truth:
            out['error_to_dock_m'] = round(math.hypot(self.truth[0] - dock['x'],
                                                      self.truth[1] - dock['y']), 4)
            out['heading_to_dock_rad'] = round(abs(math.atan2(
                math.sin(self.truth[2] - dock['yaw']),
                math.cos(self.truth[2] - dock['yaw']))), 4)
        t1 = self.truth
        end = time.monotonic() + 1.0
        while time.monotonic() < end:
            self.cmd.publish(Twist())
            rclpy.spin_once(self, timeout_sec=0.02)
        if t1 and self.truth:
            out['stop_displacement_m'] = round(math.hypot(
                self.truth[0] - t1[0], self.truth[1] - t1[1]), 4)
        out['amcl_error_m'] = round(math.hypot(
            self.amcl[0] - self.truth[0], self.amcl[1] - self.truth[1]), 4) if self.amcl and self.truth else None
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_step3/dock_query')
    ap.add_argument('--target', default='auto', choices=['auto', 'blue_near', 'blue_far'])
    ap.add_argument('--no-execute', action='store_true')
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    layout = json.loads(LAYOUT.read_text())

    rclpy.init()
    n = DockLocalizer(layout)
    f = n.wait_frame(30.0)
    if f is None:
        print(json.dumps({'error': 'no synchronized fresh frame'}))
        return 1
    rgb, depth, info = f['rgb'], f['depth'], f['info']
    k = [float(v) for v in info.k]
    comps = detect_blue(rgb)
    for c in comps:
        c['depth'] = depth_stats(depth, c['u'], c['v'])
    valid = [c for c in comps if c['depth']['median_m'] is not None]
    if not valid:
        print(json.dumps({'error': 'no blue component with depth', 'components': comps}, indent=2))
        return 1
    if args.target == 'auto':
        target = max(valid, key=lambda c: c['depth']['median_m'])
        selection_reason = 'farthest_median_depth'
    else:
        # Engineering oracle: pick the component nearest the named box projection.
        box = next(b for b in layout['blue_boxes'] if b['name'] == args.target)
        p = PointStamped()
        p.header.frame_id = 'map'
        p.point.x, p.point.y, p.point.z = box['x'], box['y'], box['z']
        q = do_transform_point(p, f['tf'])
        pt = (q.point.x / q.point.z * k[0] + k[2], q.point.y / q.point.z * k[4] + k[5])
        target = min(valid, key=lambda c: math.hypot(c['u'] - pt[0], c['v'] - pt[1]))
        selection_reason = 'oracle_named_box_projection'
    u, v = target['u'], target['v']
    z = target['depth']['median_m']
    pc = backproject(u, v, z, k)
    p = PointStamped()
    p.header.frame_id = 'agentvln_camera_optical_frame'
    p.point.x, p.point.y, p.point.z = pc
    try:
        t_map = n.tf_buffer.lookup_transform('map', 'agentvln_camera_optical_frame', f['stamp'])
    except Exception as e:
        print(json.dumps({'error': 'tf map<-optical failed: %s' % e}))
        return 1
    pm = do_transform_point(p, t_map)
    target_map = [round(pm.point.x, 4), round(pm.point.y, 4), round(pm.point.z, 4)]
    target['backprojected_map'] = target_map

    # Candidate docks are generated from the measured front-surface point, not
    # from the scene annotation. The known box rectangles are only used for a
    # conservative self-overlap rejection in this engineering baseline.
    boxes = [{'name': b['name'], 'x': b['x'], 'y': b['y']} for b in layout['blue_boxes']]
    robot = n.robot_pose(f['stamp'])
    # Straight-in docking: the dock lies on the robot -> measured-target ray, so
    # the final approach is a straight line the 1.669 m Dubin radius can hold.
    # A dock placed laterally instead forced a right turn in the last 0.6 m,
    # which needs a 1.31 m radius and made every replan fail (pipeline_v5/v6).
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
    # Prefer the straight-in candidate (smallest heading offset), then the
    # closest one to the target face.
    planned.sort(key=lambda d: (abs(d['yaw_offset_rad']), d['backoff_m']))
    fallback = False
    if planned:
        dock = planned[0]
    else:
        exp = layout['expected_dock']
        dock = {'x': exp['x'], 'y': exp['y'], 'yaw': exp['yaw'], 'fallback': True,
                'reason': 'no_generated_candidate_planned'}
        fallback = True

    # independent parking-zone evaluation from the frozen layout
    parking = layout['parking_zone']
    dock_in_zone = math.hypot(dock['x'] - parking['x'], dock['y'] - parking['y']) <= parking['radius_m']
    nav = {'status': None, 'skipped': True}
    if not args.no_execute:
        nav = n.execute(dock, f['stamp'])
        nav['skipped'] = False
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

    drawn = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    for i, c in enumerate(comps):
        color = (0, 255, 255) if c is target else (0, 255, 0)
        cv2.circle(drawn, (int(c['u']), int(c['v'])), 12, color, 2)
        cv2.putText(drawn, '%s z=%.2f' % ('target' if c is target else 'box%d' % i,
                                           c['depth']['median_m'] or -1),
                    (int(c['u']) + 10, int(c['v']) - 10), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, color, 2, cv2.LINE_AA)
    if target['depth'].get('roi'):
        x0, y0, x1, y1 = target['depth']['roi']
        cv2.rectangle(drawn, (x0, y0), (x1, y1), (0, 255, 255), 2)
    cv2.putText(drawn, 'target %s u=%.1f v=%.1f z=%.3f' % (args.target, u, v, z),
                (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(drawn, 'dock %.2f %.2f yaw=%.2f plan=%s' % (dock['x'], dock['y'], dock['yaw'],
                                                            dock.get('plan_status', 'fallback')),
                (15, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2, cv2.LINE_AA)
    cv2.imwrite(str(out / 'annotated.png'), drawn)
    cv2.imwrite(str(out / 'rgb.png'), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    np.save(out / 'depth.npy', depth)

    report = {
        'instruction': layout['instruction'],
        'frame': {'stamp_s': round(f['stamp_ns'] / 1e9, 3), 'age_s': round(f['age_s'], 3),
                  'width': int(rgb.shape[1]), 'height': int(rgb.shape[0]),
                  'K': k, 'robot_pose': [round(v, 4) for v in robot]},
        'components': comps,
        'selection': {'mode': args.target, 'reason': selection_reason,
                      'target_u': u, 'target_v': v, 'target_depth_median_m': z,
                      'target_map': target_map},
        'dock_candidates': generated,
        'chosen_dock': dock,
        'fallback_used': fallback,
        'parking': parking,
        'nav': nav,
        'truth': [round(v, 4) for v in n.truth] if n.truth else None,
        'amcl': [round(v, 4) for v in n.amcl] if n.amcl else None,
        'files': {'annotated': str(out / 'annotated.png'), 'rgb': str(out / 'rgb.png'),
                  'depth': str(out / 'depth.npy')},
    }
    (out / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
