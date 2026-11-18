"""Prove that a stalled simulator clock cannot hold the evaluator forever.

The evaluator stops a round on two independent limits: simulated seconds and wall
seconds.  A stall (physics paused, /clock frozen, server wedged) freezes the first
one, so the whole guarantee rests on the second.  This file tests that decision
directly, without needing a simulator to misbehave on demand:

    python3 -B test_watchdog.py

Exit code 0 only when every case passes; the record goes to
outputs/lab_nav_fix_20261106/watchdog_selftest.json.
"""
import json
import time
from pathlib import Path

import metrics

OUT = Path(__file__).resolve().parents[3] / 'outputs' / 'lab_nav_fix_20261106'


def cases():
    out = []

    # 1. Normal progress: neither limit reached.
    out.append(('normal_short_round', metrics.budget_hit(10.0, 20.0, 60.0, 300.0) is None))

    # 2. The planner is slow: simulated time itself passes the budget.
    out.append(('sim_budget_exceeded', metrics.budget_hit(61.0, 90.0, 60.0, 300.0) == 'sim'))

    # 3. The stall case that matters: the clock is frozen at 0.0 simulated seconds
    #    while wall time keeps running.  Only the wall limit can fire, and it must.
    out.append(('frozen_clock_hits_wall_limit',
                metrics.budget_hit(0.0, 300.5, 60.0, 300.0) == 'wall'))

    # 4. Exactly at the wall limit counts as reached (>=), so the loop cannot sit one
    #    tick short of the limit forever.
    out.append(('wall_limit_is_inclusive',
                metrics.budget_hit(0.0, 300.0, 60.0, 300.0) == 'wall'))

    # 5. A small simulated advance must not be mistaken for a stall: with both clocks
    #    moving, the sim budget still wins when it is reached first.
    out.append(('sim_wins_before_wall', metrics.budget_hit(60.0, 5.0, 60.0, 300.0) == 'sim'))

    # 6. The note that ends up in the result file has to name the limit that fired,
    #    otherwise a reader cannot tell a slow planner from a stalled simulator.
    note = metrics.budget_note(0.0, 301.0, 60.0, wall_limit_s=300.0)
    out.append(('note_names_wall_limit',
                note['hit'] == 'wall' and note['over_wall_limit'] is True
                and note['sim_per_wall'] == 0.0))
    note2 = metrics.budget_note(61.0, 90.0, 60.0, wall_limit_s=300.0)
    out.append(('note_names_sim_budget', note2['hit'] == 'sim' and note2['over_budget'] is True))

    return out


def main():
    started = time.monotonic()
    rows = [{'case': name, 'ok': bool(ok)} for name, ok in cases()]
    ok = all(r['ok'] for r in rows)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'watchdog_selftest.json').write_text(json.dumps(
        {'ok': ok, 'cases': rows, 'elapsed_s': round(time.monotonic() - started, 3)},
        indent=1), encoding='utf-8')
    for r in rows:
        print(('PASS ' if r['ok'] else 'FAIL ') + r['case'])
    print('overall', ok)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
