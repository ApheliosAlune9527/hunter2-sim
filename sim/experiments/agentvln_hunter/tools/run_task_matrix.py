#!/usr/bin/env python3
"""Run the frozen task matrix: 3 start poses x 2 modes x 3 repetitions.

Each round is: teleport + tight AMCL seed (verified) -> visual loop or
known-coordinate baseline -> one row in task_runs.tsv.  Every number in the
summary comes from the run's own report.json; nothing is typed by hand.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/mnt/d/rob-memory')
TOOLS = ROOT / 'sim/experiments/agentvln_hunter/tools'
OUT = ROOT / 'outputs/agentvln_hunter_20261108_step4'
REPS = 3
TASKS = [
    ('A1', (-0.21, -0.77, 0.0)),
    ('A2', (0.31, -0.47, 0.42)),
    ('A3', (0.83, -0.17, 0.60)),
]
LAYOUT = str(ROOT / 'sim/experiments/agentvln_hunter/config/target_layout.json')
MODES = ['visual', 'baseline']


def run(cmd, timeout=600):
    t0 = time.monotonic()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, time.monotonic() - t0, r.stdout, r.stderr


def seed(start):
    rc, _, out, err = run([sys.executable, '-B', str(TOOLS / 'reset_and_seed.py'),
                           '%.2f' % start[0], '%.2f' % start[1], '%.2f' % start[2], '0.0025'])
    ok = 'seed_ok True' in out
    return ok, out.strip().splitlines()[-3:] if out else [err[-200:]]


def visual(outdir):
    rc, wall, out, err = run([sys.executable, '-B', str(TOOLS / 'step3_pipeline.py'),
                              '--out', str(outdir), '--layout', LAYOUT])
    return rc, wall


def baseline(outdir):
    rc, wall, out, err = run([sys.executable, '-B', str(TOOLS / 'baseline_goal.py'),
                              '--out', str(outdir), '--layout', LAYOUT])
    return rc, wall


def row_from(outdir, task, mode, rep, wall):
    rep_path = outdir / 'report.json'
    if not rep_path.exists():
        return {'task': task, 'mode': mode, 'rep': rep, 'success': False,
                'note': 'no report.json', 'wall_s': round(wall, 1)}
    d = json.loads(rep_path.read_text())
    n = d.get('nav') or {}
    row = {
        'task': task, 'mode': mode, 'rep': rep,
        'success': bool(d.get('success')),
        'nav_status': n.get('status'),
        'attempts': n.get('attempts_used') or (len(n.get('route_legs') or []) + 1),
        'end_x': (n.get('final_truth') or [None])[0],
        'end_y': (n.get('final_truth') or [None, None])[1],
        'park_m': n.get('parking_distance_m'),
        'yaw_err_rad': n.get('parking_yaw_error_rad'),
        'parking_ok': n.get('parking_ok'),
        'stop_m': n.get('stop_displacement_m'),
        'path_m': d.get('truth_path_length_m'),
        'reobserves': len(d.get('reobserve_attempts') or []),
        'wall_s': round(wall, 1),
        'dir': str(outdir.relative_to(ROOT)),
    }
    if 'reason' in d:
        row['note'] = d['reason']
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--layout', default=str(ROOT / 'sim/experiments/agentvln_hunter/config/target_layout.json'))
    ap.add_argument('--tsv', default=None)
    ap.add_argument('--prefix', default='')
    ap.add_argument('--tasks', default=None,
                    help='NAME:x:y:yaw,... 默认 A1/A2/A3')
    args = ap.parse_args()
    global LAYOUT
    LAYOUT = args.layout
    tasks = TASKS
    if args.tasks:
        tasks = []
        for spec in args.tasks.split(','):
            name, x, y, yaw = spec.split(':')
            tasks.append((name, (float(x), float(y), float(yaw))))
    OUT.mkdir(parents=True, exist_ok=True)
    tsv = Path(args.tsv) if args.tsv else OUT / 'task_runs.tsv'
    cols = ['task', 'mode', 'rep', 'success', 'nav_status', 'attempts', 'end_x', 'end_y',
            'park_m', 'yaw_err_rad', 'parking_ok', 'stop_m', 'path_m', 'reobserves',
            'wall_s', 'dir', 'note']
    with tsv.open('w') as f:
        f.write('\t'.join(cols) + '\n')
    for task, start in tasks:
        for mode in MODES:
            for rep in range(1, REPS + 1):
                outdir = OUT / ('%s_%s_r%d' % (task, mode, rep))
                ok, seed_lines = seed(start)
                print('[matrix] %s %s r%d seed=%s' % (task, mode, rep, ok), flush=True)
                if not ok:
                    print('[matrix] seed failed:', seed_lines, flush=True)
                    continue
                rc, wall = (visual if mode == 'visual' else baseline)(outdir)
                row = row_from(outdir, task, mode, rep, wall)
                with tsv.open('a') as f:
                    f.write('\t'.join(str(row.get(c, '')) for c in cols) + '\n')
                print('[matrix]   ->', row['success'], row.get('park_m'), row.get('nav_status'),
                      row.get('wall_s'), flush=True)
    print('[matrix] done', flush=True)


if __name__ == '__main__':
    main()
