#!/usr/bin/env python3
"""Compare real VLM selections on one recorded frame with paired inputs."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil

from vlm_smoke import INSTRUCTIONS, label_png, load_frame, run_instruction, truth_map

LAYOUT = Path(__file__).resolve().parents[1] / 'config/target_layout_straight.json'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--frame', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--port', type=int, default=18081)
    args = ap.parse_args()
    args.api, args.model, args.curl = 'llamacpp', 'qwen-vl', shutil.which('curl.exe')
    if not args.curl:
        ap.error('Windows curl.exe is required')
    frame, depth = load_frame(args.frame)
    layout = json.loads(LAYOUT.read_text(encoding='utf-8'))
    truth = truth_map(frame, layout)
    ids = {c['id'] for c in frame['candidates']}
    if len(ids) != 2 or set(truth) != ids or set(truth.values()) != set(INSTRUCTIONS):
        raise RuntimeError('the frame needs two separately labelled candidates')
    src = args.frame / 'rgb.png'
    raw = src.read_bytes()
    labels = label_png(raw, frame['candidates'])
    b64_raw, b64_labels = (base64.b64encode(x).decode('ascii') for x in (raw, labels))
    args.out.mkdir()
    (args.out / 'labels_only.png').write_bytes(labels)
    episodes = []
    for expected, instruction in INSTRUCTIONS.items():
        for label, encoded in (('raw', b64_raw), ('image_labels', b64_labels)):
            for enabled in (True, False):
                outcome = run_instruction(args, frame, depth, encoded, instruction, expected,
                                          truth, guided=True, allow_depth=enabled)
                suffix = 'with_depth_tool' if enabled else 'depth_unavailable'
                episodes.append({'condition': f'{label}_{suffix}', **outcome})
    result = {'frame': str(args.frame), 'model': args.model, 'candidate_truth': truth,
              'rgb_sha256': hashlib.sha256(raw).hexdigest(),
              'labels_sha256': hashlib.sha256(labels).hexdigest(), 'episodes': episodes}
    with (args.out / 'report.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, allow_nan=False)
    for row in episodes:
        print(row['condition'], row['expected_box'], row['selected_candidate'],
              row['correct'], 'queries', row['tool_calls'])


if __name__ == '__main__':
    main()
