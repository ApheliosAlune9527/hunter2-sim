#!/usr/bin/env python3
"""Verify the RGB-D camera, optical TF, and marker projection in one ROS session.

Checks are deliberately about what the navigation and perception code will later
consume: frame ids, image encoding and size, depth units, intrinsics, the
base_link -> optical edge, and the projection of three known marker centres.
It writes the raw and annotated frames next to a JSON report so the numbers can
be re-checked without rerunning Gazebo.
"""
import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import cv2
import rclpy
from cv_bridge import CvBridge
from message_filters import ApproximateTimeSynchronizer, Subscriber
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import CameraInfo, Image
from rosgraph_msgs.msg import Clock
from tf2_ros import Buffer, TransformListener

CAM = 'agentvln_camera_optical_frame'
BASE = 'base_link'
MAP = 'map'
EXPECTED_T = (0.644, 0.015, 0.640)
EXPECTED_Q = (-0.5, 0.5, -0.5, 0.5)


def qmat(q):
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)],
        [2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)],
        [2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)],
    ], dtype=float)


def transform_matrix(ts):
    t = ts.transform.translation
    q = ts.transform.rotation
    m = np.eye(4)
    m[:3, :3] = qmat((q.x, q.y, q.z, q.w))
    m[:3, 3] = (t.x, t.y, t.z)
    return m


def image_to_array(msg, dtype, channels=1):
    h, w = msg.height, msg.width
    itemsize = np.dtype(dtype).itemsize * channels
    raw = np.frombuffer(msg.data, dtype=np.uint8)
    if msg.step == w * itemsize:
        flat = raw.copy()
    else:
        flat = raw.reshape(h, msg.step)[:, :w * itemsize].copy().reshape(-1)
    arr = flat.view(dtype).reshape(h, w, channels) if channels > 1 else flat.view(dtype).reshape(h, w)
    return arr


def stamp_ns(msg):
    return msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec


class CameraVerifier(Node):
    def __init__(self, out_dir, samples, timeout):
        super().__init__('agentvln_camera_verifier')
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.samples_wanted = samples
        self.deadline = time.monotonic() + timeout
        self.buf = Buffer()
        self.listener = TransformListener(self.buf, self)
        self.bridge = CvBridge()
        self.frames = []
        self.clock_ns = None
        self.clock_recv = None
        # Buffered frames from before the TF listener is warm are stale: Gazebo
        # keeps publishing while this node starts, and the bridge delivers a
        # short backlog.  Wait for the TF cache and accept only live frames.
        self.ready_at = time.monotonic() + 3.0

        self.create_subscription(Clock, '/clock', self.on_clock, 10)
        rgb = Subscriber(self, Image, '/hz_sim/agentvln/camera/image', qos_profile=qos_profile_sensor_data)
        depth = Subscriber(self, Image, '/hz_sim/agentvln/camera/depth_image', qos_profile=qos_profile_sensor_data)
        info = Subscriber(self, CameraInfo, '/hz_sim/agentvln/camera/camera_info', qos_profile=qos_profile_sensor_data)
        self.sync = ApproximateTimeSynchronizer([rgb, depth, info], queue_size=10, slop=0.10)
        self.sync.registerCallback(self.on_frame)
        self.get_logger().info(f'waiting for {samples} synchronised RGB-D frames')

    def on_clock(self, msg):
        self.clock_ns = msg.clock.sec * 1_000_000_000 + msg.clock.nanosec
        self.clock_recv = time.time()

    def on_frame(self, rgb, depth, info):
        if len(self.frames) >= self.samples_wanted:
            return
        if time.monotonic() < self.ready_at or self.clock_ns is None:
            return
        age_s = (self.clock_ns - stamp_ns(rgb)) / 1e9
        if not (0.0 <= age_s <= 1.5):
            return
        self.frames.append((rgb, depth, info, self.clock_ns, time.time()))
        self.get_logger().info(f'frame {len(self.frames)} stamp={stamp_ns(rgb)/1e9:.3f}')

    def lookup(self, target, source, stamp, latest=False):
        when = Time() if latest else Time(nanoseconds=stamp)
        try:
            return self.buf.lookup_transform(target, source, when, timeout=Duration(seconds=1.0))
        except Exception as exc:  # noqa: BLE001 - report the exact tf2 message
            return exc


def colour_ok(mean_rgb, name):
    r, g, b = [float(v) for v in mean_rgb]
    if name == 'red':
        return r > 100 and r > 1.6 * max(g, b), (r, g, b)
    if name == 'green':
        return g > 90 and g > 1.5 * max(r, b), (r, g, b)
    if name == 'blue':
        return b > 100 and b > 1.5 * max(r, g), (r, g, b)
    return False, (r, g, b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_step1/camera_verify')
    ap.add_argument('--markers', default='/mnt/d/rob-memory/sim/experiments/agentvln_hunter/config/scene_markers.json')
    ap.add_argument('--samples', type=int, default=3)
    ap.add_argument('--timeout', type=float, default=35.0)
    args = ap.parse_args()

    markers = json.loads(Path(args.markers).read_text())['markers']
    rclpy.init()
    node = CameraVerifier(args.out, args.samples, args.timeout)
    try:
        while time.monotonic() < node.deadline and len(node.frames) < args.samples:
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        frames = list(node.frames)
        checks = []

        def check(name, ok, detail):
            checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
            return bool(ok)

        check('frames_received', len(frames) >= 1, {'count': len(frames), 'wanted': args.samples})
        report = {'overall': False, 'checks': checks, 'markers': [], 'frames': []}
        if not frames:
            node.destroy_node()
            rclpy.try_shutdown()
            (node.out / 'report.json').write_text(json.dumps(report, indent=2))
            print(json.dumps(report, indent=2))
            return 1

        rgb0, depth0, info0, clk0, _ = frames[0]
        h, w = rgb0.height, rgb0.width
        check('rgb_size', (w, h) == (640, 480), {'width': w, 'height': h})
        check('rgb_encoding', rgb0.encoding == 'rgb8', {'encoding': rgb0.encoding})
        check('rgb_frame', rgb0.header.frame_id == CAM, {'frame_id': rgb0.header.frame_id})
        check('depth_size', (depth0.width, depth0.height) == (w, h), {'width': depth0.width, 'height': depth0.height})
        check('depth_encoding', depth0.encoding == '32FC1', {'encoding': depth0.encoding})
        check('depth_frame', depth0.header.frame_id == CAM, {'frame_id': depth0.header.frame_id})
        check('info_size', (info0.width, info0.height) == (w, h), {'width': info0.width, 'height': info0.height})
        check('distortion_zero', all(abs(float(v)) < 1e-9 for v in info0.d), {'d': list(info0.d)})

        K = np.array(info0.k, dtype=float).reshape(3, 3)
        P = np.array(info0.p, dtype=float).reshape(3, 4)
        fx, fy, cx, cy = float(K[0, 0]), float(K[1, 1]), float(K[0, 2]), float(K[1, 2])
        check('intrinsics_k', (fx > 0 and fy > 0 and abs(fx - fy) < 1e-6), {'fx': fx, 'fy': fy, 'cx': cx, 'cy': cy})
        check('intrinsics_p', (abs(P[0, 0] - fx) < 1e-6 and abs(P[1, 1] - fy) < 1e-6 and
                               abs(P[0, 2] - cx) < 1e-6 and abs(P[1, 2] - cy) < 1e-6), {'P': P.tolist()})

        stamps = []
        for rgb, depth, info, clk, recv in frames:
            stamps.append(stamp_ns(rgb))
            check(f'stamp_rgb_depth_{len(stamps)}', abs(stamp_ns(rgb) - stamp_ns(depth)) <= 50_000_000,
                  {'rgb': stamp_ns(rgb), 'depth': stamp_ns(depth)})
            check(f'stamp_rgb_info_{len(stamps)}', abs(stamp_ns(rgb) - stamp_ns(info)) <= 50_000_000,
                  {'rgb': stamp_ns(rgb), 'info': stamp_ns(info)})
            if clk is not None:
                check(f'stamp_behind_clock_{len(stamps)}', 0.0 <= (clk - stamp_ns(rgb)) / 1e9 <= 3.0,
                      {'age_s': (clk - stamp_ns(rgb)) / 1e9})
        check('new_frames', len(stamps) >= 2 and stamps[-1] > stamps[0], {'stamps': stamps})

        rgb = image_to_array(rgb0, np.uint8, 3)
        depth = image_to_array(depth0, np.float32, 1)
        valid = np.isfinite(depth) & (depth > 0.05) & (depth < 20.0)
        check('rgb_not_black', float(rgb.mean()) > 3.0, {'mean': float(rgb.mean()), 'std': float(rgb.std())})
        check('depth_valid_fraction', float(valid.mean()) > 0.30, {'valid_fraction': float(valid.mean())})
        check('depth_plausible_metres', bool(valid.any()) and 0.1 < float(np.median(depth[valid])) < 20.0,
              {'min': float(depth[valid].min()) if valid.any() else None,
               'median': float(np.median(depth[valid])) if valid.any() else None,
               'max': float(depth[valid].max()) if valid.any() else None})

        t_static = node.lookup(BASE, CAM, 0, latest=True)
        if isinstance(t_static, Exception):
            check('tf_static_available', False, {'error': str(t_static)})
            t_base_cam = None
        else:
            m = transform_matrix(t_static)
            terr = float(np.linalg.norm(m[:3, 3] - np.array(EXPECTED_T)))
            q = t_static.transform.rotation
            qerr = min(np.linalg.norm(np.array((q.x, q.y, q.z, q.w)) - np.array(EXPECTED_Q)),
                       np.linalg.norm(np.array((q.x, q.y, q.z, q.w)) + np.array(EXPECTED_Q)))
            check('tf_static_translation', terr < 1e-4, {'error_m': terr, 'actual': m[:3, 3].tolist()})
            check('tf_static_rotation', qerr < 1e-4, {'error': qerr,
                  'actual_xyzw': [q.x, q.y, q.z, q.w]})
            axes = {'optical_x_to_base': m[:3, 0].tolist(), 'optical_y_to_base': m[:3, 1].tolist(),
                    'optical_z_to_base': m[:3, 2].tolist()}
            check('optical_axes', (np.allclose(m[:3, 0], (0, -1, 0), atol=1e-4) and
                                   np.allclose(m[:3, 1], (0, 0, -1), atol=1e-4) and
                                   np.allclose(m[:3, 2], (1, 0, 0), atol=1e-4)), axes)
            t_base_cam = m

        t_map_base = node.lookup(MAP, BASE, stamp_ns(rgb0))
        check('tf_map_base_at_stamp', not isinstance(t_map_base, Exception),
              {'ok': not isinstance(t_map_base, Exception), 'error': None if not isinstance(t_map_base, Exception) else str(t_map_base)})
        t_opt_map = node.lookup(CAM, MAP, stamp_ns(rgb0))
        t_map_opt = node.lookup(MAP, CAM, stamp_ns(rgb0))
        check('tf_map_optical_at_stamp', not isinstance(t_opt_map, Exception) and not isinstance(t_map_opt, Exception),
              {'error': str(t_opt_map) if isinstance(t_opt_map, Exception) else None})

        annotated = rgb.copy()
        marker_rows = []
        if not isinstance(t_opt_map, Exception) and not isinstance(t_map_opt, Exception):
            M_opt_map = transform_matrix(t_opt_map)
            M_map_opt = transform_matrix(t_map_opt)
            for mk in markers:
                name = mk['name']
                p_map = np.array(mk['xyz'], dtype=float)
                p_opt = M_opt_map[:3, :3] @ p_map + M_opt_map[:3, 3]
                z = float(p_opt[2])
                u = fx * p_opt[0] / z + cx if abs(z) > 1e-6 else float('nan')
                v = fy * p_opt[1] / z + cy if abs(z) > 1e-6 else float('nan')
                row = {'name': name, 'xyz_map': p_map.tolist(), 'xyz_optical': p_opt.tolist(),
                       'expected_z_m': z, 'u': u, 'v': v}
                in_frame = math.isfinite(u) and math.isfinite(v) and 4 <= u < w - 4 and 4 <= v < h - 4 and z > 0.2
                row['in_frame'] = bool(in_frame)
                if in_frame:
                    ui, vi = int(round(u)), int(round(v))
                    patch = rgb[max(0, vi-3):vi+4, max(0, ui-3):ui+4].reshape(-1, 3)
                    mean_rgb = patch.mean(axis=0)
                    ok_colour, mean_rgb_t = colour_ok(mean_rgb, name)
                    dpatch = depth[max(0, vi-4):vi+5, max(0, ui-4):ui+5]
                    dvalid = dpatch[np.isfinite(dpatch) & (dpatch > 0.05) & (dpatch < 20.0)]
                    med = float(np.median(dvalid)) if dvalid.size else float('nan')
                    row.update({'mean_rgb': list(mean_rgb_t), 'colour_ok': bool(ok_colour),
                                'depth_median_m': med, 'depth_valid_pixels': int(dvalid.size),
                                'depth_error_m': abs(med - z) if dvalid.size else None})
                    check(f'marker_{name}_colour', ok_colour, {'mean_rgb': list(mean_rgb_t)})
                    check(f'marker_{name}_depth', dvalid.size >= 4 and abs(med - z) < 0.12,
                          {'depth_m': med, 'expected_z_m': z, 'valid_pixels': int(dvalid.size)})
                    if dvalid.size:
                        ray = np.array([(u - cx) / fx, (v - cy) / fy, 1.0])
                        p_meas = M_map_opt[:3, :3] @ (med * ray) + M_map_opt[:3, 3]
                        err = float(np.linalg.norm(p_meas - p_map))
                        row.update({'backprojected_map': p_meas.tolist(), 'backprojection_error_m': err})
                        check(f'marker_{name}_backprojection', err < 0.15, {'error_m': err})
                    colour = (0, 0, 255) if name == 'red' else ((0, 255, 0) if name == 'green' else (255, 0, 0))
                    cv2.circle(annotated, (ui, vi), 8, colour, 2)
                    cv2.putText(annotated, f'{name} z={z:.2f}', (ui + 10, vi - 6),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, colour, 1, cv2.LINE_AA)
                else:
                    check(f'marker_{name}_in_frame', False, {'u': u, 'v': v, 'z': z})
                marker_rows.append(row)
                report['markers'].append(row)
        else:
            check('marker_projection', False, {'error': 'map -> optical TF unavailable'})

        cv2.imwrite(str(node.out / 'rgb.png'), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(node.out / 'annotated.png'), cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR))
        dvis = np.zeros_like(depth, dtype=np.uint8)
        dvis[valid] = np.clip((depth[valid] - 0.1) / 4.9 * 255.0, 0, 255).astype(np.uint8)
        dvis_col = cv2.applyColorMap(dvis, cv2.COLORMAP_TURBO)
        dvis_col[~valid] = 0
        cv2.imwrite(str(node.out / 'depth_vis.png'), dvis_col)
        np.save(node.out / 'depth.npy', depth)
        (node.out / 'camera_info.json').write_text(json.dumps({
            'width': info0.width, 'height': info0.height, 'frame_id': info0.header.frame_id,
            'k': list(info0.k), 'p': list(info0.p), 'd': list(info0.d),
        }, indent=2))

        report.update({
            'overall': all(c['ok'] for c in checks),
            'frames': [{'stamp_ns': s, 'stamp_s': s / 1e9} for s in stamps],
            'topics': {'rgb': '/hz_sim/agentvln/camera/image',
                       'depth': '/hz_sim/agentvln/camera/depth_image',
                       'info': '/hz_sim/agentvln/camera/camera_info'},
            'camera': {'width': w, 'height': h, 'fx': fx, 'fy': fy, 'cx': cx, 'cy': cy},
            'tf': {'base_to_camera': t_base_cam.tolist() if t_base_cam is not None else None},
            'image_stats': {'mean_rgb': [float(v) for v in rgb.reshape(-1, 3).mean(axis=0)],
                            'depth_valid_fraction': float(valid.mean()),
                            'depth_median': float(np.median(depth[valid])) if valid.any() else None},
            'files': {'rgb': str(node.out / 'rgb.png'), 'annotated': str(node.out / 'annotated.png'),
                      'depth_vis': str(node.out / 'depth_vis.png'), 'depth_npy': str(node.out / 'depth.npy')},
        })
        (node.out / 'report.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        node.destroy_node()
        rclpy.try_shutdown()
        return 0 if report['overall'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
