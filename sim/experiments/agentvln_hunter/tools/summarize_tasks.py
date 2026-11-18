#!/usr/bin/env python3
"""Summarise task_runs.tsv files into a markdown table with success rates."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path


def load(paths):
    rows = []
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        with p.open() as f:
            for r in csv.DictReader(f, delimiter='\t'):
                r['_src'] = p.name
                rows.append(r)
    return rows


def fnum(v, nd=3):
    try:
        return ('%.' + str(nd) + 'f') % float(v)
    except (TypeError, ValueError):
        return '—'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    rows = load(args.files)
    groups = defaultdict(list)
    for r in rows:
        groups[(r['task'], r['mode'])].append(r)
    lines = ['| task | mode | runs | success | park m (mean) | yaw rad (mean) | '
             'stop m (mean) | path m (mean) | reobs (mean) | wall s (mean) |',
             '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for (task, mode), rs in sorted(groups.items()):
        ok = [r for r in rs if r['success'] == 'True']
        def mean(key):
            vals = [float(r[key]) for r in rs if r.get(key) not in (None, '', 'None')]
            return sum(vals) / len(vals) if vals else None
        lines.append('| %s | %s | %d | %d/%d | %s | %s | %s | %s | %s | %s |' % (
            task, mode, len(rs), len(ok), len(rs),
            fnum(mean('park_m')), fnum(mean('yaw_err_rad')), fnum(mean('stop_m')),
            fnum(mean('path_m'), 2), fnum(mean('reobserves'), 1), fnum(mean('wall_s'), 1)))
    text = '\n'.join(lines)
    print(text)
    if args.out:
        Path(args.out).write_text(text + '\n')


if __name__ == '__main__':
    main()
