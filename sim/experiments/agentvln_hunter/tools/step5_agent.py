#!/usr/bin/env python3
"""Replay interface for the AgentVLN decision step.

The agent gets an image, an instruction and numbered candidates; it may ask for
the depth of a region, select a candidate, request re-observation or finish.
This harness executes those calls against a stored frame (rgb.png, depth.npy,
report.json) and records every step, so a real VLM only has to produce the JSON
decisions -- and the same harness runs the rule baselines unchanged.

Backends:
  area   -- no depth query, "小像面积 = 较远" proxy (step-3 baseline)
  depth  -- query both regions, then "大深度 = 较远"
  replay -- execute decisions from --decisions verbatim (the VLM output slot)
  vlm    -- check for a local backend; currently unavailable
"""
import argparse
import json
import math
import time
from pathlib import Path

import numpy as np

CAM_FWD = 0.644
CAM_Z = 0.640


def load_frame(frame_dir):
    rep = json.loads((Path(frame_dir) / 'report.json').read_text())
    depth = np.load(Path(frame_dir) / 'depth.npy')
    return rep, depth


def measure(depth, cand, half=12):
    x, y, w, h = cand['bbox_xywh']
    cx, cy = int(x + w / 2), int(y + h / 2)
    patch = depth[max(0, cy - half):cy + half + 1, max(0, cx - half):cx + half + 1]
    ok = patch[np.isfinite(patch) & (patch > 0.1) & (patch < 20.0)]
    if ok.size == 0:
        return None, 0
    return round(float(np.median(ok)), 4), int(ok.size)


def truth_map(rep, layout):
    """Nearest-box label per candidate, projected from the recorded pose."""
    pose = rep['robot_pose']
    K = rep['K']
    fx, fy, cx0, cy0 = K[0], K[4], K[2], K[5]
    camx = pose[0] + CAM_FWD * math.cos(pose[2])
    camy = pose[1] + CAM_FWD * math.sin(pose[2])
    out = {}
    for b in layout['blue_boxes']:
        dx, dy = b['x'] - camx, b['y'] - camy
        fwd = math.cos(pose[2]) * dx + math.sin(pose[2]) * dy
        left = -math.sin(pose[2]) * dx + math.cos(pose[2]) * dy
        u = cx0 + fx * (-left) / fwd
        v = cy0 + fy * (-(b['z'] - CAM_Z)) / fwd
        best = min(rep['candidates'],
                   key=lambda c: math.hypot(c['u'] - u, c['v'] - v))
        out[best['id']] = b['name']
    return out


def wants_far(instruction):
    return ('较远' in instruction) or ('更远' in instruction)


def backend_area(rep, instruction, asked):
    far = wants_far(instruction)
    pool = [c for c in rep['candidates']]
    pick = min(pool, key=lambda c: c['area_px']) if far else max(pool, key=lambda c: c['area_px'])
    return {'decision': 'select_target', 'candidate_id': pick['id'],
            'reason': 'area_proxy_%s' % ('small_is_far' if far else 'large_is_near')}


def backend_depth(rep, instruction, asked):
    if len(asked) < len(rep['candidates']):
        todo = [c for c in rep['candidates'] if c['id'] not in asked]
        return {'decision': 'query_depth', 'candidate_id': todo[0]['id'],
                'reason': 'resolve_near_far_ambiguity'}
    far = wants_far(instruction)
    pool = [c for c in rep['candidates'] if c['id'] in asked]
    pick = max(pool, key=lambda c: asked[c['id']]) if far else min(pool, key=lambda c: asked[c['id']])
    return {'decision': 'select_target', 'candidate_id': pick['id'],
            'reason': 'depth_%s' % ('max_is_far' if far else 'min_is_near')}


def backend_replay(decisions, step):
    if step < len(decisions):
        return decisions[step]
    return {'decision': 'finish', 'reason': 'no_more_decisions'}


def vlm_available():
    try:
        import importlib.util
        mods = ['torch', 'transformers', 'ollama', 'llama_cpp']
        return any(importlib.util.find_spec(m) for m in mods)
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frame', required=True)
    ap.add_argument('--instruction', required=True)
    ap.add_argument('--backend', required=True, choices=['area', 'depth', 'replay', 'vlm'])
    ap.add_argument('--layout', required=True)
    ap.add_argument('--decisions', default=None)
    ap.add_argument('--out', required=True)
    ap.add_argument('--max-steps', type=int, default=6)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rep, depth = load_frame(args.frame)
    layout = json.loads(Path(args.layout).read_text())
    truth = truth_map(rep, layout)
    expected = 'blue_far' if wants_far(args.instruction) else 'blue_near'

    if args.backend == 'vlm' and not vlm_available():
        result = {'status': 'backend_unavailable', 'instruction': args.instruction,
                  'checked': ['torch', 'transformers', 'ollama', 'llama_cpp']}
        (out / 'result.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
        return 3

    decisions = []
    if args.backend == 'replay':
        if not args.decisions:
            raise SystemExit('--decisions is required for the replay backend')
        decisions = json.loads(Path(args.decisions).read_text())

    trace = []
    asked = {}
    t0 = time.monotonic()
    selected = None
    for step in range(args.max_steps):
        if args.backend == 'area':
            action = backend_area(rep, args.instruction, asked)
        elif args.backend == 'depth':
            action = backend_depth(rep, args.instruction, asked)
        elif args.backend == 'replay':
            action = backend_replay(decisions, step)
        else:
            action = {'decision': 'finish', 'reason': 'vlm_not_implemented'}
        entry = {'step': step, 'action': dict(action), 't_ms': round((time.monotonic() - t0) * 1000, 1)}
        if action['decision'] == 'query_depth':
            cid = action['candidate_id']
            cand = next(c for c in rep['candidates'] if c['id'] == cid)
            z, valid = measure(depth, cand)
            asked[cid] = z
            entry['tool_result'] = {'candidate_id': cid, 'depth_median_m': z,
                                    'unit': 'm', 'valid_pixels': valid,
                                    'valid_fraction': round(valid / 625.0, 4)}
        elif action['decision'] == 'select_target':
            selected = action['candidate_id']
            entry['selected'] = selected
            entry['selected_box_truth'] = truth.get(selected)
            trace.append(entry)
            break
        elif action['decision'] in ('request_reobserve', 'finish'):
            trace.append(entry)
            break
        trace.append(entry)

    correct = bool(selected is not None and truth.get(selected) == expected)
    result = {
        'status': 'completed' if selected is not None else 'no_selection',
        'backend': args.backend,
        'instruction': args.instruction,
        'expected_box': expected,
        'selected_candidate': selected,
        'selected_box_truth': truth.get(selected) if selected is not None else None,
        'correct': correct,
        'candidate_truth': truth,
        'queries': asked,
        'trace': trace,
        'wall_ms': round((time.monotonic() - t0) * 1000, 1),
        'model_calls': 0 if args.backend != 'vlm' else 1,
    }
    (out / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({k: result[k] for k in ('status', 'backend', 'instruction', 'expected_box',
                                             'selected_candidate', 'selected_box_truth', 'correct',
                                             'queries')}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
