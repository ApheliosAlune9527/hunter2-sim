#!/usr/bin/env python3
"""Apply the two safety corrections to the car's Nav2 parameter file.

Only two things change, and both are geometry/coverage facts rather than driving
behaviour:

  * footprint      the planner was told the car is 0.52 m ahead of the rear axle
                   and 0.50 m behind it.  The vehicle model says the nose is
                   0.834 m ahead and the tail 0.184 m behind, so the costmap let
                   the front 0.31 m of the car sweep through obstacles.
  * allow_unknown  the planner was allowed to route through unknown space, which
                   contradicts the requirement that unknown cells are not
                   traversable.

Everything else (0.10 m/s speed, reversing allowed, REEDS_SHEPP, the BackUp
recovery in the behaviour tree) is left exactly as it is, because that is the
configuration the car was actually tested with on 2026-10-28.

Dry run by default: prints the diff and touches nothing.  With --write it saves
a timestamped copy beside the original before editing.
"""
import argparse
import datetime
import difflib
import pathlib
import sys

DEFAULT = pathlib.Path('/home/car/hz_nav_ws/config/nav2_params.yaml')

OLD_FOOTPRINT = '"[[0.52, 0.395], [0.52, -0.395], [-0.50, -0.395], [-0.50, 0.395]]"'
NEW_FOOTPRINT = '"[[-0.184, -0.393], [0.834, -0.393], [0.834, 0.393], [-0.184, 0.393]]"'


def patch(text):
    """Return the patched text plus a list of what was done."""
    done = []

    n_foot = text.count(OLD_FOOTPRINT)
    if n_foot != 2:
        raise SystemExit(
            'expected 2 occurrences of the old footprint, found %d -- refusing to '
            'edit a file that does not look like the one that was reviewed' % n_foot)
    text = text.replace(OLD_FOOTPRINT, NEW_FOOTPRINT)
    done.append('footprint: 2 lines, nose 0.52 -> 0.834 m, tail -0.50 -> -0.184 m')

    # allow_unknown appears exactly twice, both under planner_server GridBased.
    n_unk = text.count('allow_unknown: true')
    if n_unk != 2:
        raise SystemExit(
            'expected 2 "allow_unknown: true", found %d -- check the file before '
            'editing' % n_unk)
    text = text.replace('allow_unknown: true', 'allow_unknown: false')
    done.append('allow_unknown: 2 lines, true -> false')

    return text, done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', default=str(DEFAULT))
    ap.add_argument('--write', action='store_true',
                    help='actually edit; without it this is a dry run')
    args = ap.parse_args()

    path = pathlib.Path(args.file)
    if not path.is_file():
        raise SystemExit('no such file: %s' % path)

    original = path.read_text(encoding='utf-8')
    patched, done = patch(original)

    print('file: %s' % path)
    for line in done:
        print('  * %s' % line)

    diff = list(difflib.unified_diff(
        original.splitlines(keepends=True),
        patched.splitlines(keepends=True),
        fromfile=str(path), tofile=str(path) + ' (patched)'))
    print()
    sys.stdout.writelines(diff)

    if not args.write:
        print('\ndry run: nothing written.  re-run with --write to apply.')
        return 0

    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = path.with_suffix(path.suffix + '.bak_' + stamp)
    backup.write_text(original, encoding='utf-8')
    path.write_text(patched, encoding='utf-8')
    print('\nwritten.  backup: %s' % backup)
    print('the running Nav2 must be restarted to load it.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
