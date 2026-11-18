#!/usr/bin/env python3
"""Capture one replay asset and compare the area rule with the depth rule.

Writes the frame, the depth map, the candidate list (编号 + 像素区域 + 深度) and
both rule decisions, so a VLM can later be replayed on exactly this input and
the numbers stay comparable.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import rclpy

from target_dock import DockLocalizer, LAYOUT, depth_stats, detect_blue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--layout', default=str(LAYOUT))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    layout = json.loads(Path(args.layout).read_text())

    rclpy.init()
    n = DockLocalizer(layout)
    f = n.wait_frame(30.0)
    if f is None:
        print(json.dumps({'error': 'no synchronized fresh frame'}))
        return 1
    rgb = f['rgb']
    comps = detect_blue(rgb)
    cands = []
    for i, c in enumerate(comps):
        d = depth_stats(f['depth'], c['u'], c['v'])
        cands.append({
            'id': i, 'u': c['u'], 'v': c['v'],
            'bbox_xywh': c['bbox'], 'area_px': c['area_px'],
            'area_fraction': c['area_fraction'],
            'depth_median_m': d['median_m'], 'depth_valid': d['valid'],
            'depth_valid_fraction': d['valid_fraction'],
        })
    valid = [c for c in cands if c['depth_median_m'] is not None]
    # The step-3 area proxy is "smaller blob = farther"; the depth rule is
    # "larger median depth = farther".  On this scene the two disagree, which is
    # the whole point of the pair.
    area_far = min(valid, key=lambda c: c['area_px']) if valid else None
    area_near = max(valid, key=lambda c: c['area_px']) if valid else None
    depth_far = max(valid, key=lambda c: c['depth_median_m']) if valid else None
    depth_near = min(valid, key=lambda c: c['depth_median_m']) if valid else None
    report = {
        'stage': 'bigfar_frame',
        'robot_pose': [round(v, 4) for v in n.robot_pose(f['stamp'])],
        'stamp_s': round(f['stamp_ns'] / 1e9, 3),
        'K': [float(v) for v in f['info'].k],
        'candidates': cands,
        'rule_area_far_choice': area_far['id'] if area_far else None,
        'rule_area_near_choice': area_near['id'] if area_near else None,
        'rule_depth_far_choice': depth_far['id'] if depth_far else None,
        'rule_depth_near_choice': depth_near['id'] if depth_near else None,
        'area_proxy_agrees_with_depth_far': bool(area_far and depth_far and area_far is depth_far),
        'area_proxy_agrees_with_depth_near': bool(area_near and depth_near and area_near is depth_near),
        'instruction_near': layout.get('instruction_near'),
        'instruction_far': layout.get('instruction'),
        'files': {'rgb': str(out / 'rgb.png'), 'depth': str(out / 'depth.npy'),
                  'annotated': str(out / 'annotated.png')},
    }
    cv2.imwrite(str(out / 'rgb.png'), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    np.save(out / 'depth.npy', f['depth'])
    img = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    for c in cands:
        x, y, w, h = c['bbox_xywh']
        colour = (0, 255, 255) if depth_far and c['id'] == depth_far['id'] else (0, 255, 0)
        cv2.rectangle(img, (x, y), (x + w, y + h), colour, 2)
        cv2.putText(img, '#%d z=%.2fm A=%d' % (c['id'], c['depth_median_m'] or -1, c['area_px']),
                    (x, max(16, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, colour, 2, cv2.LINE_AA)
    cv2.imwrite(str(out / 'annotated.png'), img)
    (out / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
