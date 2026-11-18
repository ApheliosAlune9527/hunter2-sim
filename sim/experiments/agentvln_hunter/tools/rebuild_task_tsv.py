#!/usr/bin/env python3
"""Rebuild task_runs.tsv from the per-run report.json files.

The matrix writes rows as it goes, but the baseline report keeps its metrics at
the top level instead of under "nav", so the authoritative table is rebuilt here
from the reports themselves.
"""
import argparse
import json
from pathlib import Path

ROOT = Path('/mnt/d/rob-memory')
OUT = ROOT / 'outputs/agentvln_hunter_20261108_step4'
COLS = ['task', 'mode', 'rep', 'success', 'success_task', 'action_ok', 'nav_status',
        'attempts', 'end_x', 'end_y', 'park_m', 'yaw_err_rad', 'parking_ok', 'stop_m',
        'path_m', 'reobserves', 'wall_s', 'dir', 'note']


def pick(d, key):
    if key in d and d[key] is not None:
        return d[key]
    n = d.get('nav') or {}
    return n.get(key)


def row_for(dirpath):
    name = dirpath.name
    parts = name.split('_')
    task, mode, rep = parts[0], parts[1], parts[2].lstrip('r')
    f = dirpath / 'report.json'
    if not f.exists():
        return None
    d = json.loads(f.read_text())
    n = d.get('nav') or {}
    row = {
        'task': task, 'mode': mode, 'rep': rep,
        'success': bool(d.get('success')),
        'nav_status': n.get('status'),
        'attempts': n.get('attempts_used') or (len(n.get('route_legs') or []) + 1),
        'end_x': (pick(d, 'final_truth') or [None])[0],
        'end_y': (pick(d, 'final_truth') or [None, None])[1],
        'park_m': pick(d, 'parking_distance_m'),
        'yaw_err_rad': pick(d, 'parking_yaw_error_rad'),
        'parking_ok': pick(d, 'parking_ok'),
        'stop_m': pick(d, 'stop_displacement_m'),
        'path_m': d.get('truth_path_length_m'),
        'reobserves': len(d.get('reobserve_attempts') or []),
        'wall_s': n.get('wall_s'),
        'dir': str(dirpath.relative_to(ROOT)),
    }
    # The plan defines success as reaching the marked parking zone and stopping
    # (line 40 of the brief), not as the NavigateToPose status code.  Smac aborts
    # in the Dubin dead zone after the vehicle is already parked, so the action
    # status is kept as a separate diagnostic column instead of failing the task.
    stop = row['stop_m']
    parked = bool(row['parking_ok'])
    stopped = stop is not None and stop != '' and float(stop) <= 0.05
    row['success_task'] = bool(parked and stopped)
    row['action_ok'] = row['nav_status'] == 4
    if d.get('reason'):
        row['note'] = d['reason']
    elif not row['action_ok'] and row['success_task']:
        row['note'] = 'nav2_abort_after_parking'
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(OUT / 'task_runs.tsv'))
    args = ap.parse_args()
    rows = []
    for d in sorted(OUT.iterdir()):
        if not d.is_dir():
            continue
        r = row_for(d)
        if r:
            rows.append(r)
    rows.sort(key=lambda r: (r['task'], r['mode'], int(r['rep'])))
    with Path(args.out).open('w') as f:
        f.write('\t'.join(COLS) + '\n')
        for r in rows:
            f.write('\t'.join(str(r.get(c, '')) for c in COLS) + '\n')
    print('rows', len(rows), '->', args.out)


if __name__ == '__main__':
    main()
