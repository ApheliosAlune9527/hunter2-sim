"""Metric definitions for the corrected round, as pure functions.

Section E of the correction plan asks for one place that defines what each number
means, so the evaluator, the plots and the write-up cannot drift apart.  Nothing here
touches ROS: the functions take plain tuples, which also makes them testable without a
simulator (see test_metrics.py).

Poses are (x, y, yaw).  Distances are metres, angles radians.
"""
import math

POS_TOL_NAV2 = 0.20   # controller xy_goal_tolerance in the senior's parameters
YAW_TOL_NAV2 = 0.35   # controller yaw_goal_tolerance
POS_TOL_OUTER = 0.25  # the outer acceptance the evaluator has always used

STOP_LIN = 0.01       # m/s
STOP_ANG = 0.01       # rad/s
STOP_HOLD_S = 1.0     # simulated seconds it has to stay stopped


def wrap(a):
    """Wrap an angle to (-pi, pi]."""
    return math.atan2(math.sin(a), math.cos(a))


def pose_error(truth, est):
    """Position error and heading error between two poses."""
    dx = est[0] - truth[0]
    dy = est[1] - truth[1]
    return math.hypot(dx, dy), wrap(est[2] - truth[2])


def compose(a, b):
    """T(a) * T(b)."""
    c, s = math.cos(a[2]), math.sin(a[2])
    return (a[0] + c * b[0] - s * b[1],
            a[1] + s * b[0] + c * b[1],
            wrap(a[2] + b[2]))


def inverse(a):
    c, s = math.cos(a[2]), math.sin(a[2])
    return (-(c * a[0] + s * a[1]), -(-s * a[0] + c * a[1]), wrap(-a[2]))


def relative(origin, pose):
    """pose expressed in the frame of origin."""
    return compose(inverse(origin), pose)


def odom_truth_drift(odom, truth):
    """SE(2) difference between the odometry's motion and the truth's motion.

    Both tracks are aligned at their first sample; then, at every sample, the odometry's
    relative motion is compared with the truth's relative motion and the difference is
    expressed as a pose.  The drift is reported both at the last sample and as the
    worst sample in between -- the loop below is why: a vehicle that drives out and
    back ends where it started, so an endpoint-only comparison calls a 20 % scale error
    zero drift.

    This replaces the old `hypot(end-start) - path_len`, which is a straight-line
    shortcut and is not a drift at all.
    """
    if len(odom) != len(truth):
        raise ValueError('the two tracks need the same number of samples')
    if len(odom) < 2:
        raise ValueError('need at least two samples')
    worst_t, worst_r = 0.0, 0.0
    last = None
    for i in range(1, len(odom)):
        residual = compose(relative(odom[0], odom[i]),
                           inverse(relative(truth[0], truth[i])))
        last = residual
        worst_t = max(worst_t, math.hypot(residual[0], residual[1]))
        worst_r = max(worst_r, abs(residual[2]))
    return {
        'final_m': round(math.hypot(last[0], last[1]), 4),
        'final_rad': round(abs(last[2]), 4),
        'max_m': round(worst_t, 4),
        'max_rad': round(worst_r, 4),
        'samples': len(odom),
    }


def stop_settled(samples, lin_tol=STOP_LIN, ang_tol=STOP_ANG, hold_s=STOP_HOLD_S):
    """Was the vehicle at rest, within tolerance, for `hold_s` simulated seconds?

    `samples` is a sequence of (sim_time, v, w) taken after the zero command was sent.
    Returns a dict: whether it settled, for how long, and the worst values seen during
    the settled window.  A window that never reaches hold_s does not count as settled.
    """
    settled_since = None
    best = {'ok': False, 'held_s': 0.0, 'v_max': None, 'w_max': None}
    for t, v, w in samples:
        quiet = abs(v) < lin_tol and abs(w) < ang_tol
        if not quiet:
            settled_since = None
            continue
        if settled_since is None:
            settled_since = t
        held = t - settled_since
        if held >= hold_s:
            window = [s for s in samples if settled_since <= s[0] <= t]
            best = {'ok': True, 'held_s': round(held, 3),
                    'v_max': max(abs(s[1]) for s in window),
                    'w_max': max(abs(s[2]) for s in window)}
    return best


def classify(action_status, pos_err, heading_err,
             pos_tol=POS_TOL_OUTER, yaw_tol=YAW_TOL_NAV2):
    """One verdict per run, with the reason when it is not a success.

    An action that reports success while the truth says otherwise is `truth_disagrees`
    -- the failure mode found on 2026-11-06, where a spinning wheel fooled the
    controller into believing it had arrived.
    """
    status_ok = action_status == 4  # STATUS_SUCCEEDED
    within = pos_err <= pos_tol and abs(heading_err) <= yaw_tol
    if status_ok and within:
        return 'succeeded'
    if status_ok and not within:
        return 'truth_disagrees'
    if not status_ok and within:
        return 'stopped_short'
    return 'failed'


def budget_hit(sim_elapsed, wall_elapsed, budget_sim_s, wall_limit_s):
    """Which limit ended the round, or None if neither has been reached.

    Kept as a pure function so the stall case can be tested without a simulator: when
    /clock freezes, `sim_elapsed` stops growing and only the wall limit can fire.
    """
    if sim_elapsed >= budget_sim_s:
        return 'sim'
    if wall_elapsed >= wall_limit_s:
        return 'wall'
    return None


def budget_note(sim_seconds, wall_seconds, budget_sim_s, wall_limit_s=None):
    """Both clocks, kept separate: the budget is in simulated seconds, the watchdog in
    wall seconds, and the ratio is reported rather than assumed.

    `hit` names which of the two actually stopped the round, because "over budget" and
    "the wall clock ran out" mean different things: the first says the planner was slow,
    the second says the simulator itself may have stalled.
    """
    hit = None
    if sim_seconds > budget_sim_s:
        hit = 'sim'
    if wall_limit_s is not None and wall_seconds >= wall_limit_s:
        hit = 'wall' if hit is None else 'sim_and_wall'
    return {
        'sim_seconds': round(sim_seconds, 3),
        'wall_seconds': round(wall_seconds, 3),
        'budget_sim_s': budget_sim_s,
        'wall_limit_s': wall_limit_s,
        'over_budget': sim_seconds > budget_sim_s,
        'over_wall_limit': (wall_limit_s is not None and wall_seconds >= wall_limit_s),
        'hit': hit,
        'sim_per_wall': round(sim_seconds / wall_seconds, 4) if wall_seconds > 0 else None,
    }
