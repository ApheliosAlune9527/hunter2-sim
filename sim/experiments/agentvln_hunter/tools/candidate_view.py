#!/usr/bin/env python3
"""Capture one fresh RGB-D frame, build reachable candidates, project and number them.

This is the interface test before any VLM is attached.  It deliberately uses the
live Nav2 costmap and a trial ComputePathToPose call for every candidate.
"""
import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from message_filters import ApproximateTimeSynchronizer, Subscriber
from rclpy.duration import Duration
from rclpy.qos import QoSProfile, qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CameraInfo, Image

from candidate_builder import CandidateBuilder, yaw_of_quat


class CandidateView(CandidateBuilder):
    def __init__(self):
        super().__init__('candidate_view')
        self.bridge = CvBridge()
        self.sim_ns = 0
        self.latest = None
        self.create_subscription(Clock, '/clock', self.on_clock, 10)
        self.sync = ApproximateTimeSynchronizer(
            [Subscriber(self, Image, '/hz_sim/agentvln/camera/image', qos_profile=qos_profile_sensor_data),
             Subscriber(self, Image, '/hz_sim/agentvln/camera/depth_image', qos_profile=qos_profile_sensor_data),
             Subscriber(self, CameraInfo, '/hz_sim/agentvln/camera/camera_info', qos_profile=QoSProfile(depth=10))],
            queue_size=6, slop=0.15)
        self.sync.registerCallback(self.on_frame)

    def on_clock(self, msg):
        self.sim_ns = msg.clock.sec * 1_000_000_000 + msg.clock.nanosec

    def on_frame(self, image, depth, info):
        if self.sim_ns <= 0:
            return
        stamp = image.header.stamp.sec * 1_000_000_000 + image.header.stamp.nanosec
        age = (self.sim_ns - stamp) / 1e9
        if age < 0.0 or age > 1.5:
            return
        if self.latest is not None and stamp <= self.latest['stamp_ns']:
            return
        try:
            rgb = self.bridge.imgmsg_to_cv2(image, desired_encoding='rgb8')
            dep = self.bridge.imgmsg_to_cv2(depth, desired_encoding='32FC1')
        except Exception:
            return
        self.latest = {'stamp_ns': stamp, 'age_s': age, 'rgb': rgb,
                       'depth': dep, 'info': info}

    def wait_frame(self, timeout=30.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.latest is not None and self.latest['age_s'] <= 1.5:
                try:
                    self.tf_buffer.lookup_transform(
                        'map', 'base_link', self.latest['info'].header.stamp,
                        timeout=Duration(seconds=0.1))
                except Exception:
                    self.latest = None
                    continue
                return self.latest
        return self.latest


def cand_dict(c):
    return {
        'id': c.cid, 'map_pose': [round(c.x, 4), round(c.y, 4), round(c.yaw, 4)],
        'u': round(c.u, 2), 'v': round(c.v, 2),
        'ground_u': round(c.ground_u, 2), 'ground_v': round(c.ground_v, 2),
        'ground_in_frame': bool(c.ground_in_frame), 'projection_height_m': c.vis_height_m,
        'distance_from_robot_m': round(c.distance_from_robot, 3),
        'bearing_deg': round(math.degrees(c.bearing_from_robot), 2),
        'path_length_m': round(c.path_length, 3),
        'plan_status': c.plan_status,
        'footprint_ok': c.footprint_ok,
        'path_clear': c.path_clear,
        'optical_z_m': round(c.optical_z, 3),
        'expected_range_m': round(c.expected_range, 3),
        'depth_median_m': round(c.depth_median, 3),
        'visible': bool(c.visible),
        'occluded': bool(c.occluded),
        'reason': c.reason,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_step2/candidate_view')
    ap.add_argument('--target', nargs=2, type=float, default=None, metavar=('X', 'Y'))
    ap.add_argument('--select', type=int, default=0)
    ap.add_argument('--distances', default='1.4,1.7,2.0')
    ap.add_argument('--angles', default='-26,-13,0,13,26')
    ap.add_argument('--max-candidates', type=int, default=18)
    ap.add_argument('--vis-height', type=float, default=0.5,
                    help='height of the numbered waypoint beacon above the ground pose')
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    distances = tuple(float(v) for v in args.distances.split(','))
    angles = tuple(float(v) for v in args.angles.split(','))

    rclpy.init()
    node = CandidateView()
    if not node.wait_costmap(timeout=10.0):
        print(json.dumps({'error': 'no global costmap'}))
        return 1
    end = time.monotonic() + 2.0
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.05)
    frame = node.wait_frame(timeout=30.0)
    if frame is None:
        print(json.dumps({'error': 'no fresh RGB-D frame'}))
        return 1
    stamp = frame['stamp_ns']
    stamp_msg = frame['info'].header.stamp
    try:
        robot = node.robot_pose(stamp_msg)
    except Exception as exc:
        print(json.dumps({'error': 'no map->base_link at frame: %s' % exc}))
        return 1
    candidates = node.build(stamp_msg, frame['info'], robot, distances, angles, args.max_candidates)
    candidates = node.project(candidates, stamp_msg, frame['info'], frame['depth'],
                              frame['rgb'].shape[:2], args.vis_height)
    visible = [c for c in candidates if c.visible]
    visible.sort(key=lambda c: (c.u, c.v))
    for i, c in enumerate(visible, 1):
        c.cid = i

    selected = None
    mode = 'none'
    if args.select:
        selected = next((c for c in visible if c.cid == args.select), None)
        mode = 'explicit_id'
    elif args.target:
        tx, ty = args.target
        selected = min(visible, key=lambda c: math.hypot(c.x - tx, c.y - ty)) if visible else None
        mode = 'nearest_to_target'
    elif visible:
        selected = max(visible, key=lambda c: (c.path_length, c.distance_from_robot))
        mode = 'farthest_path'

    annotated = cv2.cvtColor(frame['rgb'], cv2.COLOR_RGB2BGR)
    for c in visible:
        color = (0, 255, 255) if selected is c else (0, 255, 0)
        thick = 3 if selected is c else 2
        cv2.circle(annotated, (int(round(c.u)), int(round(c.v))), 9, color, thick)
        cv2.putText(annotated, str(c.cid), (int(round(c.u)) - 7, int(round(c.v)) - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(annotated, str(c.cid), (int(round(c.u)) - 7, int(round(c.v)) - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2, cv2.LINE_AA)
    if selected is not None:
        cv2.putText(annotated, 'selected %d' % selected.cid, (15, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)

    dv = np.clip(frame['depth'], 0.0, 5.0)
    dv = (dv / 5.0 * 255.0).astype(np.uint8)
    cv2.imwrite(str(out / 'rgb.png'), cv2.cvtColor(frame['rgb'], cv2.COLOR_RGB2BGR))
    cv2.imwrite(str(out / 'annotated.png'), annotated)
    cv2.imwrite(str(out / 'depth_vis.png'), cv2.applyColorMap(dv, cv2.COLORMAP_TURBO))
    np.save(str(out / 'depth.npy'), frame['depth'])
    (out / 'camera_info.json').write_text(json.dumps({
        'fx': frame['info'].k[0], 'fy': frame['info'].k[4],
        'cx': frame['info'].k[2], 'cy': frame['info'].k[5],
        'width': frame['info'].width, 'height': frame['info'].height,
        'frame_id': frame['info'].header.frame_id}, indent=2))

    report = {
        'frame': {'stamp_s': stamp / 1e9, 'age_s': round(frame['age_s'], 4),
                  'width': frame['rgb'].shape[1], 'height': frame['rgb'].shape[0]},
        'robot_pose_map': [round(v, 4) for v in robot],
        'costmap': {'width': node.costmap.width, 'height': node.costmap.height,
                    'resolution': node.costmap.resolution,
                    'origin': [node.costmap.origin_x, node.costmap.origin_y]},
        'sampling': {'distances_m': distances, 'angles_deg': angles,
                     'max_candidates': args.max_candidates,
                     'projection_height_m': args.vis_height},
        'build_stats': node.last_stats,
        'candidates_total': len(candidates),
        'candidates_visible': len(visible),
        'selection_mode': mode,
        'selected': cand_dict(selected) if selected else None,
        'target': args.target,
        'candidates': [cand_dict(c) for c in candidates],
        'files': {k: str(out / v) for k, v in {
            'rgb': 'rgb.png', 'annotated': 'annotated.png', 'depth': 'depth.npy',
            'depth_vis': 'depth_vis.png', 'camera_info': 'camera_info.json'}.items()},
    }
    (out / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({k: report[k] for k in ('frame', 'robot_pose_map', 'build_stats',
                                               'candidates_total', 'candidates_visible',
                                               'selection_mode', 'selected')},
                     indent=2, ensure_ascii=False))
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
