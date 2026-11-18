#!/usr/bin/env python3
"""Replay the two recorded Step 5 frames against a Windows-hosted local VLM."""

import argparse
import base64
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT / 'sim/experiments/agentvln_hunter/tools'
CONFIG = TOOLS.parent / 'config'
FRAMES = ROOT / 'outputs/agentvln_hunter_20261108_step5'
sys.path.insert(0, str(TOOLS))
from step5_agent import load_frame, measure, truth_map

CASES = {
    'bigfar': ('bigfar_frame', 'target_layout_step5.json'),
    'swap': ('bigfar_swap_frame', 'target_layout_step5_swap.json'),
}
INSTRUCTIONS = {
    'blue_far': '停在较远的蓝箱前',
    'blue_near': '停在较近的蓝箱前',
}
ACTIONS = ('query_depth', 'select_target', 'request_reobserve', 'finish')


def label_png(image, candidates):
    import cv2
    import numpy as np

    img = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError('could not decode the RGB image')
    for row in candidates:
        x, y, w, h = row['bbox_xywh']
        cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 255), 2)
        cv2.putText(img, f'#{row["id"]}', (x, max(18, y-5)),
                    cv2.FONT_HERSHEY_SIMPLEX, .65, (0, 255, 255), 2)
    ok, data = cv2.imencode('.png', img)
    if not ok:
        raise ValueError('could not encode the labelled RGB image')
    return data.tobytes()


def ask(args, image_b64, text, ids, actions=ACTIONS):
    has_id = any(a in ('query_depth', 'select_target') for a in actions)
    has_null = any(a in ('request_reobserve', 'finish') for a in actions)
    id_schema = {'type': 'integer', 'enum': sorted(ids)}
    null_schema = {'type': 'null'}
    candidate_schema = ({'anyOf': [id_schema, null_schema]} if has_id and has_null
                        else id_schema if has_id else null_schema)
    schema = {
        'type': 'object',
        'properties': {
            'decision': {'type': 'string', 'enum': list(actions)},
            'candidate_id': candidate_schema,
        },
        'required': ['decision', 'candidate_id'],
        'additionalProperties': False,
    }
    if args.api == 'ollama':
        endpoint = '/api/chat'
        request = {
            'model': args.model, 'stream': False, 'format': schema,
            'options': {'temperature': 0, 'num_ctx': 4096, 'num_predict': 96, 'seed': 42},
            'keep_alive': '5m',
            'messages': [{'role': 'user', 'content': text, 'images': [image_b64]}],
        }
    else:
        endpoint = '/v1/chat/completions'
        request = {
            'model': args.model, 'stream': False, 'temperature': 0, 'max_tokens': 96, 'seed': 42,
            'response_format': {'type': 'json_object', 'schema': schema},
            'messages': [{'role': 'user', 'content': [
                {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + image_b64}},
                {'type': 'text', 'text': text},
            ]}],
        }
    url = f'http://127.0.0.1:{args.port}{endpoint}'
    # A Windows process called from WSL reaches Windows loopback directly.
    # ASCII JSON keeps the stdin transport independent of the console code page.
    started = time.monotonic()
    proc = subprocess.run(
        [args.curl, '--noproxy', '*', '--silent', '--show-error', '--fail',
         '--connect-timeout', '5', '--max-time', '90',
         '-H', 'Content-Type: application/json', '--data-binary', '@-', url],
        input=json.dumps(request, ensure_ascii=True).encode('ascii'),
        capture_output=True, timeout=95, check=False,
    )
    elapsed_ms = round((time.monotonic() - started) * 1000, 1)
    if proc.returncode:
        raise RuntimeError(f'curl exit {proc.returncode}: {proc.stderr.decode(errors="replace").strip()}')
    result = json.loads(proc.stdout)
    if args.api == 'ollama':
        content = result['message']['content']
        timing = {key: round(result[key] / 1e6, 1) for key in (
            'load_duration', 'prompt_eval_duration', 'eval_duration', 'total_duration'
        ) if key in result}
    else:
        content = result['choices'][0]['message']['content']
        timing = result.get('timings', {})
    return content, elapsed_ms, timing, result.get('model')


def run_instruction(args, frame, depth, image_b64, instruction, expected, truth,
                    *, guided=False, allow_depth=True):
    by_id = {row['id']: row for row in frame['candidates']}
    visible = [{'id': cid, 'bbox_xywh': by_id[cid]['bbox_xywh']} for cid in sorted(by_id)]
    requested = []
    trace = []
    selected = None
    for _ in range(4 if allow_depth else 1):
        actions, allowed_ids = ACTIONS, by_id
        text = (
            '你是仿真车的图像决策模块。请结合640×480图像和中文指令选择蓝箱。'
            '候选区域使用图像像素[x,y,w,h]。如需分辨近远，可调用 query_depth 读取某个编号的深度，'
            '单位是米。请勿重复查询同一编号。有足够依据后调用 select_target。'
            '看不到足够信息可 request_reobserve 或 finish。每次只输出 JSON 对象，'
            '包含 decision 和 candidate_id。query_depth/select_target 需要合法整数编号，'
            '另外两项的 candidate_id 为 null。\n'
            f'指令：{instruction}\n'
            f'候选区域：{json.dumps(visible)}\n'
            f'已返回的深度查询：{json.dumps(requested)}'
        )
        if guided:
            text = (
                '图中蓝箱的检测结果已整理为候选区域。候选编号由列表提供。'
                '你负责用图像、指令和工具回执选定目标。只输出一个 JSON 对象。'
                '格式为 {"decision":"动作名","candidate_id":整数编号或null}。\n'
                f'指令：{instruction}\n'
                f'候选区域[x,y,w,h]：{json.dumps(visible)}\n'
                f'已返回的深度查询（米）：{json.dumps(requested)}\n'
            )
            if allow_depth:
                remaining = set(by_id) - {item['candidate_id'] for item in requested}
                if remaining:
                    actions, allowed_ids = ('query_depth',), remaining
                    text += ('当前是测量阶段。箱子像素面积不代表距离。'
                             f'请返回 query_depth，选择一个还未测量的编号 {sorted(remaining)}。')
                else:
                    actions = ('select_target',)
                    measured = '\n'.join(
                        f'候选 {item["candidate_id"]} 的实测深度：{item["depth_m"]:.3f} 米'
                        for item in sorted(requested, key=lambda item: item['candidate_id']))
                    text = (
                        '请选出符合用户指令的蓝箱，两个编号与图像区域如下。\n'
                        f'候选区域[x,y,w,h]：{json.dumps(visible)}\n'
                        f'{measured}\n'
                        '深度数值小表示较近，深度数值大表示较远。以实测深度为准，'
                        '不要按图上的像素面积或查询先后选择。\n'
                        f'当前用户指令：「{instruction}」。\n'
                        '按当前指令比较这两个数字。只返回 JSON 对象，'
                        'decision 为 select_target，candidate_id 为你选的整数编号。'
                    )
            else:
                actions = ('select_target', 'request_reobserve', 'finish')
                text += ('本轮深度查询工具不可用。请根据画面和指令直接用 select_target 选择。'
                         '依据不足可 request_reobserve 或 finish，编号写 null。')
        entry = {'step': len(trace) + 1, 'prompt': text}
        trace.append(entry)
        try:
            raw, elapsed, timing, returned_model = ask(args, image_b64, text, allowed_ids, actions)
            entry.update(raw=raw, wall_ms=elapsed, server_timing=timing, returned_model=returned_model)
            action = json.loads(raw)
            if not isinstance(action, dict) or set(action) != {'decision', 'candidate_id'}:
                raise ValueError('expected decision and candidate_id')
            name, cid = action['decision'], action['candidate_id']
            if name not in actions:
                raise ValueError('unsupported decision')
            if name in ('query_depth', 'select_target'):
                if type(cid) is not int or cid not in allowed_ids:
                    raise ValueError('unknown candidate_id')
            elif cid is not None:
                raise ValueError('this decision requires candidate_id=null')
            entry['action'] = action
            if name == 'query_depth':
                if not allow_depth:
                    raise ValueError('depth tool disabled in this condition')
                if any(item['candidate_id'] == cid for item in requested):
                    raise ValueError('repeated depth query')
                z, count = measure(depth, by_id[cid])
                observation = {'candidate_id': cid, 'depth_m': z, 'valid_pixels': count}
                requested.append(observation)
                entry['tool_result'] = observation
                if guided and (z is None or count < 400):
                    raise ValueError('insufficient valid depth, no target selected')
            elif name == 'select_target':
                selected = cid
                break
            else:
                break
        except (OSError, RuntimeError, ValueError, TypeError, LookupError, subprocess.TimeoutExpired) as exc:
            entry['error'] = str(exc)
            break

    return {
        'instruction': instruction, 'expected_box': expected,
        'expected_candidate': next(cid for cid, label in truth.items() if label == expected),
        'selected_candidate': selected, 'correct': truth.get(selected) == expected,
        'model_responses': sum('raw' in entry for entry in trace),
        'tool_calls': len(requested), 'trace': trace,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--api', choices=('ollama', 'llamacpp'), required=True)
    ap.add_argument('--port', type=int)
    ap.add_argument('--model')
    ap.add_argument('--case', choices=('bigfar', 'swap', 'both'), default='both')
    ap.add_argument('--guided-depth', action='store_true')
    ap.add_argument('--label-candidates', action='store_true')
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    args.port = args.port if args.port is not None else (11434 if args.api == 'ollama' else 8081)
    if not 1 <= args.port <= 65535:
        ap.error('invalid TCP port')
    args.model = args.model or ('qwen2.5vl:3b' if args.api == 'ollama' else 'qwen-vl')
    args.curl = shutil.which('curl.exe')
    if args.curl is None:
        ap.error('Windows curl.exe is required. Run from the Ubuntu-22.04 WSL shell with Windows interop.')

    runs = []
    for case in CASES if args.case == 'both' else (args.case,):
        frame_name, layout_name = CASES[case]
        frame_dir = FRAMES / frame_name
        frame, depth = load_frame(frame_dir)
        layout = json.loads((CONFIG / layout_name).read_text(encoding='utf-8'))
        truth = truth_map(frame, layout)
        ids = {item['id'] for item in frame['candidates']}
        if len(ids) != 2 or set(truth) != ids or set(truth.values()) != set(INSTRUCTIONS):
            raise SystemExit(f'{case}: could not match two distinct candidates to the fixture boxes')
        raw = (frame_dir / 'rgb.png').read_bytes()
        image = label_png(raw, frame['candidates']) if args.label_candidates else raw
        image_b64 = base64.b64encode(image).decode('ascii')
        for expected, instruction in INSTRUCTIONS.items():
            run = run_instruction(args, frame, depth, image_b64, instruction, expected, truth,
                                  guided=args.guided_depth)
            run.update(case=case, image_sha256=sha256(image).hexdigest())
            runs.append(run)
            first = run['trace'][0]
            print(f'{case} {instruction}: selected={run["selected_candidate"]} '
                  f'expected={run["expected_candidate"]} correct={run["correct"]} '
                  f'queries={run["tool_calls"]} first_ms={first.get("wall_ms")}', flush=True)
            if 'error' in run['trace'][-1]:
                print(run['trace'][-1]['error'], file=sys.stderr)
    report = {'api': args.api, 'requested_model': args.model, 'port': args.port,
              'guided_depth': args.guided_depth, 'label_candidates': args.label_candidates,
              'episodes': runs}
    out = args.out or HERE / f'vlm_{args.api}_{datetime.now():%Y%m%d_%H%M%S_%f}.json'
    with out.open('x', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    correct = sum(run['correct'] for run in runs)
    print(f'{correct}/{len(runs)} selections correct. Trace: {out}')
    return 0 if correct == len(runs) else 2


if __name__ == '__main__':
    raise SystemExit(main())
