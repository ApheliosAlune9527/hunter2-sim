#!/usr/bin/env python3
"""Known-coordinate baseline: drive straight to the frozen expected dock.

This is the paired control for the visual closed loop.  It takes no image, runs
no detector and queries no depth: it sends one NavigateToPose goal to the pose
written in the layout and evaluates the result with exactly the criteria the
visual loop uses (parking-zone distance, heading error, stop displacement).
"""
import argparse
import json
import math
import time
from pathlib import Path

import rclpy
from nav_msgs.msg import Odometry

from target_dock import DockLocalizer, LAYOUT


class Logger:
    """Accumulates the ground-truth path length of one run."""

    def __init__(self, node):
        self.node = node
        self.first = None
        self.last = None
        self.length = 0.0
        self.samples = 0
        node.create_subscription(Odometry, '/ground_truth', self.on_truth, 10)

    def on_truth(self, msg):
        p = msg.pose.pose.position
        xy = (p.x, p.y)
        if self.last is not None:
            self.length += math.hypot(xy[0] - self.last[0], xy[1] - self.last[1])
        else:
            self.first = xy
        self.last = xy
        self.samples += 1


def main():
    t_start = time.monotonic()
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--goal', default='auto', choices=['auto', 'expected'])
    ap.add_argument('--layout', default=str(LAYOUT))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    layout = json.loads(Path(args.layout).read_text())

    rclpy.init()
    n = DockLocalizer(layout)
    log = Logger(n)
    end = time.monotonic() + 5.0
    while time.monotonic() < end:
        rclpy.spin_once(n, timeout_sec=0.05)
    start_truth = list(n.truth) if n.truth else None
    start_amcl = list(n.amcl) if n.amcl else None

    # The baseline drives the same *route* the visual loop drives - observation
    # pose then dock - but every waypoint comes from the layout instead of from
    # an image.  A single diagonal goal to the dock is not a fair control: it is
    # a different path (measured 2026-11-08 11:12, status 6, 0.392 m short).
    legs = []
    for wp in layout.get('observation_route') or []:
        st = n.get_clock().now().to_msg()
        nav_leg = n.execute({'x': wp['x'], 'y': wp['y'], 'yaw': wp['yaw']}, st)
        legs.append({'pose': wp, 'nav': nav_leg})
        if nav_leg.get('status') != 4:
            break

    dock = dict(layout['expected_dock'])
    dock['source'] = 'layout_expected_dock'
    stamp = n.get_clock().now().to_msg()
    nav = n.execute(dock, stamp) if (not legs or legs[-1]['nav'].get('status') == 4) else {
        'status': 0, 'skipped': True, 'reason': 'route_leg_failed'}
    nav['skipped'] = nav.get('status') == 0
    nav['route_legs'] = legs

    # one second of zero commands, same as the visual loop's stop measurement
    end = time.monotonic() + 1.0
    while time.monotonic() < end:
        rclpy.spin_once(n, timeout_sec=0.02)

    parking = layout['parking_zone']
    result = {
        'mode': 'known_coordinate_baseline',
        'goal': dock,
        'start_truth': start_truth,
        'start_amcl': start_amcl,
        'nav': nav,
        'wall_total_s': round(time.monotonic() - t_start, 2),
        'truth_path_length_m': round(log.length, 3),
        'truth_samples': log.samples,
        'layout': str(LAYOUT),
    }
    if n.truth:
        result['final_truth'] = [round(v, 4) for v in n.truth]
        result['parking_distance_m'] = round(math.hypot(n.truth[0] - parking['x'],
                                                        n.truth[1] - parking['y']), 4)
        result['parking_yaw_error_rad'] = round(abs(math.atan2(
            math.sin(n.truth[2] - parking['yaw']),
            math.cos(n.truth[2] - parking['yaw']))), 4)
        result['parking_ok'] = bool(result['parking_distance_m'] <= parking['radius_m'] and
                                    result['parking_yaw_error_rad'] <= parking['yaw_tol_rad'])
    result['success'] = bool(nav.get('status') == 4 and result.get('parking_ok') and
                             nav.get('stop_displacement_m', 1.0) <= 0.05)
    (out / 'report.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
