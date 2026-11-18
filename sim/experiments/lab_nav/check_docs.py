"""Check that the handover document only points at things that exist.

The README is the entry point for whoever picks this up next, so a path it names
has to resolve and a number it quotes has to match the record it came from.  This
does not run anything; it reads.

Usage: python3 -B sim/experiments/lab_nav/check_docs.py
"""
import json
import re
import sys
from pathlib import Path

OUT = Path('/mnt/d/rob-memory/outputs/lab_nav_20261105')
WS = Path('/mnt/d/rob-memory')

problems = []


def read(name):
    return (OUT / name).read_text(encoding='utf-8')


SEARCH_DIRS = [
    OUT,
    WS,
    WS / 'sim/experiments/lab_nav',
    WS / 'sim/experiments/lab_nav/rl',
    WS / 'sim/experiments/lab_scene',
    WS / 'sim/config',
    WS / 'sim/scenes',
    OUT / 'rl',
    WS / 'outputs/lab_map_compare_20261105',
]


def check_paths():
    """Every backticked path in the README must resolve.

    The README names scripts by bare filename where the section already says which
    directory they live in, so a bare name is accepted if it exists in one of the
    directories this work owns.  Placeholders such as `*_verification.json` or
    `taskN_verification.json` are patterns, not paths, and are skipped.
    """
    text = read('README.md')
    tokens = set(re.findall(r'`([^`\s]+)`', text))
    checked = 0
    for tok in sorted(tokens):
        if not re.search(r'\.(json|md|sdf|py|bash|yaml|stl|pgm|csv|png|zip|xml|jsonl)$', tok):
            continue
        if tok.startswith('/') or tok.startswith('http') or '*' in tok or 'N_' in tok:
            continue
        checked += 1
        if not any((d / tok).exists() for d in SEARCH_DIRS):
            problems.append(f'README names a missing file: {tok}')
    return checked


def check_numbers():
    """The headline counts in RESULTS.md must equal the records."""
    results = read('RESULTS.md')
    t4 = json.loads(read('task4_verification.json'))
    t5 = json.loads(read('task5_verification.json'))

    truth_pass = t4['overall']['successes']
    truth_total = t4['overall']['attempts']
    amcl_pass = t5['navigation_repeats']['successes']
    amcl_total = t5['navigation_repeats']['attempts']

    if f'{truth_pass}/{truth_total} goals reached' not in results:
        problems.append(f'RESULTS.md does not claim {truth_pass}/{truth_total} for truth localisation')
    if f'{amcl_pass}/{amcl_total}' not in results:
        problems.append(f'RESULTS.md does not claim {amcl_pass}/{amcl_total} for AMCL')

    # The AMCL number the README quotes must match too.
    readme = read('README.md')
    if f'{amcl_pass}/{amcl_total}' not in readme:
        problems.append(f'README does not state the AMCL result {amcl_pass}/{amcl_total}')
    return (truth_pass, truth_total, amcl_pass, amcl_total)


def check_task7_runs():
    t7 = json.loads(read('task7_verification.json'))
    if not t7.get('runs'):
        problems.append('task7_verification.json has no runs')
        return 0
    for r in t7['runs']:
        for key in ('run', 'training', 'model'):
            if key not in r:
                problems.append(f'task7 run {r.get("run")} lacks {key}')
    return len(t7['runs'])


def main():
    n_paths = check_paths()
    truth = check_numbers()
    n_runs = check_task7_runs()
    print(f'paths checked: {n_paths}')
    print(f"nav results: truth {truth[0]}/{truth[1]}, amcl {truth[2]}/{truth[3]}")
    print(f'task7 runs: {n_runs}')
    if problems:
        print('\nPROBLEMS')
        for p in problems:
            print(' -', p)
        return 1
    print('\nno contradictions found')
    return 0


if __name__ == '__main__':
    sys.exit(main())
