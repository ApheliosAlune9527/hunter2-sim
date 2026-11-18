"""Self-test for metrics.py -- no simulator, no ROS, plain python.

Run:  python3 -B sim/experiments/lab_nav_fix_20261106/test_metrics.py
"""
import math
import sys

import metrics as m

FAILS = []


def check(name, got, want, tol=1e-9):
    ok = abs(got - want) <= tol if isinstance(got, float) else got == want
    print(('PASS ' if ok else 'FAIL ') + name + f'  got={got!r} want={want!r}')
    if not ok:
        FAILS.append(name)


def main():
    # pose error and wrap
    check('wrap(3pi/2)', round(m.wrap(1.5 * math.pi), 6), round(-0.5 * math.pi, 6))
    d, h = m.pose_error((0.0, 0.0, 0.0), (3.0, 4.0, 0.1))
    check('pose_error distance', round(d, 6), 5.0)
    check('pose_error heading', round(h, 6), 0.1)

    # a straight drive: odometry agrees with truth -> no drift
    truth = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
    check('no drift when tracks agree', m.odom_truth_drift(truth, truth)['final_m'], 0.0)

    # odometry 10% long: 2.2 m reported against 2.0 m driven -> 0.2 m drift
    odom = [(0.0, 0.0, 0.0), (1.1, 0.0, 0.0), (2.2, 0.0, 0.0)]
    check('10% scale error -> 0.2 m', m.odom_truth_drift(odom, truth)['final_m'], 0.2)

    # the loop case that the old formula reported as zero drift
    loop_truth = [(0.0, 0.0, 0.0), (1.0, 0.0, math.pi / 2), (1.0, 1.0, math.pi),
                  (0.0, 1.0, -math.pi / 2), (0.0, 0.0, 0.0)]
    check('loop returns to start', round(math.hypot(loop_truth[-1][0], loop_truth[-1][1]), 9), 0.0)
    loop_odom = [(0.0, 0.0, 0.0), (1.2, 0.0, math.pi / 2), (1.2, 1.2, math.pi),
                 (0.0, 1.2, -math.pi / 2), (0.0, 0.0, 0.0)]
    loop = m.odom_truth_drift(loop_odom, loop_truth)
    check('loop ends where it started', loop['final_m'], 0.0)
    check('loop drift is caught at the worst sample', loop['max_m'] > 0.1, True)

    # stop settling: 0.5 s quiet is not enough, 1.2 s is
    short = [(0.0, 0.0, 0.0), (0.5, 0.0, 0.0)]
    check('0.5 s quiet does not settle', m.stop_settled(short)['ok'], False)
    long = [(0.0, 0.0, 0.0), (0.6, 0.0, 0.0), (1.2, 0.0, 0.0)]
    settled = m.stop_settled(long)
    check('1.2 s quiet settles', settled['ok'], True)
    check('settled duration', round(settled['held_s'], 3), 1.2)

    # one noisy sample resets the window: the timer restarts at 1.0
    noisy = [(0.0, 0.0, 0.0), (0.6, 0.0, 0.0), (0.7, 0.02, 0.0), (1.7, 0.0, 0.0)]
    check('noise restarts the window', m.stop_settled(noisy)['ok'], False)

    # verdicts
    check('arrived', m.classify(4, 0.10, 0.05), 'succeeded')
    check('claims success, truth says 0.4 m away',
          m.classify(4, 0.40, 0.05), 'truth_disagrees')
    check('in tolerance but action never returned',
          m.classify(5, 0.10, 0.05), 'stopped_short')
    check('outside everything', m.classify(6, 0.90, 0.80), 'failed')
    check('heading alone out of tolerance',
          m.classify(4, 0.10, 0.50), 'truth_disagrees')

    note = m.budget_note(61.0, 130.5, 60.0)
    check('over budget flagged', note['over_budget'], True)
    check('sim per wall', note['sim_per_wall'], round(61.0 / 130.5, 4))

    print()
    if FAILS:
        print(f'{len(FAILS)} check(s) failed: {FAILS}')
        return 1
    print('all checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
