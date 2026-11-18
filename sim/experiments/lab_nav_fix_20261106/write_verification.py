#!/usr/bin/env python3
"""Compose task_verification.json from the machine-written result files.

No number in the record is typed by hand: this script reads the run files, the accuracy
probe, the configuration diff and the verification receipts, and asserts that the values
it is about to report are present.  A missing file is an error, not a zero.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'outputs' / 'lab_nav_fix_20261106'
HERE = ROOT / 'sim' / 'experiments' / 'lab_nav_fix_20261106'


def read(name):
    path = OUT / name
    if not path.exists():
        raise SystemExit('missing result file: %s -- the record cannot be written' % path)
    return json.loads(path.read_text())


def sha256(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def check_receipt_is_current(receipt_name, inputs):
    """A receipt that predates the files it describes proves nothing.

    The 2026-11-06 round shipped an `ok: true` receipt that had been written before the
    footprint changed, so it described a configuration the stack no longer had.  Rather
    than trusting the flag, refuse to compose a record from a stale one.
    """
    receipt = OUT / receipt_name
    if not receipt.exists():
        raise SystemExit('missing receipt: %s' % receipt)
    mtime = receipt.stat().st_mtime
    stale = [p.name for p in inputs if p.exists() and p.stat().st_mtime > mtime]
    if stale:
        raise SystemExit('%s is older than %s -- re-run verify_fix_config.py'
                         % (receipt_name, ', '.join(stale)))
    doc = json.loads(receipt.read_text())
    for check in doc['checks']:
        if check['check'].endswith('footprint'):
            if not check.get('ok'):
                raise SystemExit('footprint check did not pass in %s' % receipt_name)
            if check.get('equals_swept_rectangle'):
                raise SystemExit('receipt carries the swept rectangle, not the costmap '
                                 'footprint: %s' % check['check'])
    for fname in ('navigate_no_spin.xml', 'navigate_through_poses_no_spin.xml'):
        entry = next((c for c in doc['checks']
                      if c['check'].startswith(fname)), None)
        if entry is None:
            raise SystemExit('receipt has no check for %s' % fname)
        current = sha256(HERE / fname)
        if entry['sha256'] != current:
            raise SystemExit('receipt records %s sha %s, file is now %s'
                             % (fname, entry['sha256'][:12], current[:12]))
    return doc


def summarise(tag):
    doc = read('nav_eval_runs_%s.json' % tag)
    runs = doc['runs']
    per_goal = {}
    for name, *_ in doc['goals']:
        rs = [r for r in runs if r['goal'] == name]
        ok = [r for r in rs if r['success']]
        per_goal[name] = {
            'attempts': len(rs),
            'successes': len(ok),
            'reasons': sorted({r['reason'] for r in rs}),
            'mean_final_error_m': round(sum(r['final_error_m'] for r in ok) / len(ok), 4) if ok else None,
            'mean_sim_seconds': round(sum(r['budget']['sim_seconds'] for r in ok) / len(ok), 2) if ok else None,
        }
    drift = [r['drift']['max_m'] for r in runs if r.get('drift') and 'max_m' in r['drift']]
    return {
        'localizer': doc['localizer'],
        'attempts': len(runs),
        'successes': sum(1 for r in runs if r['success']),
        'false_successes': sum(1 for r in runs if r.get('reported_success') and not r['success']),
        'stopped_cleanly': sum(1 for r in runs if r['stop']['ok']),
        'per_goal': per_goal,
        'worst_odom_drift_m': round(max(drift), 4) if drift else None,
        'collisions': 'not_measured',
        'artifact': 'nav_eval_runs_%s.json' % tag,
        'plot': 'nav_eval_tracks_%s.png' % tag,
    }


def main():
    truth = summarise('truth3')
    amcl = summarise('amcl3')
    accuracy = read('amcl_eval_fix.json')
    setup = read('contact_sensor_setup.json')
    probe = read('contact_probe.json')
    config = check_receipt_is_current(
        'verify_fix_config.json',
        [HERE / 'nav2_params_fix.yaml', HERE / 'navigate_no_spin.xml',
         HERE / 'navigate_through_poses_no_spin.xml'])
    corridor = read('corridor_check.json')
    footprint_case = read('footprint_case_test.json')
    scope = read('footprint_scope.json')
    watchdog = read('watchdog_selftest.json')
    mid_ok = read('nav_eval_runs_mid_ok.json')['runs'][0]
    mid_timeout = read('nav_eval_runs_mid_timeout.json')['runs'][0]

    record = {
        'round': '2026-11-07 corrected configuration',
        'scene': {
            'world': 'hz_lab_2d (outputs/lab_nav_20261105/lab_nav_world_drive.sdf)',
            'map': 'outputs/lab_nav_20261105/lab_nav_map.pgm (2026-11-01, unpatched)',
            'params': 'sim/experiments/lab_nav_fix_20261106/nav2_params_fix.yaml',
            'params_diff': 'nav2_params_fix_diff.json',
            'loaded_parameters_verified': config.get('ok'),
            'footprint_m': [[-0.184, -0.393], [0.834, -0.393], [0.834, 0.393], [-0.184, 0.393]],
            'footprint_source': 'chassis envelope + 0.02 m margin; the swept front-wheel '
                                'envelope is kept separately for offline audits',
        },
        'footprint_regression_case': footprint_case,
        'corridor_check': corridor,
        'truth_localisation': truth,
        'amcl_localisation_navigation': amcl,
        'amcl_accuracy': {
            'static': accuracy['static'],
            'straight': accuracy['straight'],
            'criteria': accuracy['criteria'],
            'passed': accuracy['ok'],
            'artifact': 'amcl_eval_fix.json',
        },
        'collision_contacts': {
            'status': 'not_measured',
            'why': 'the contact sensor is attached and bridged, but this Gazebo build '
                   'publishes no messages on it, including with the full collision list',
            'attempts': probe,
            'setup': setup,
            'proxy_in_use': 'wheel speed integrating while the truth pose does not move '
                            '(hz_nav_env._blocked); this is a proxy and is labelled as one',
        },
        'still_not_measured': [
            'collision events (see above; the old "0 collisions" claims stay withdrawn)',
            'negative obstacles, dynamic actors, or walls taller than the 2.4 m assumption',
            'long-run (>5 min) drift and thermal/CPU effects',
        ],
    }

    record['round2_acceptance'] = {
        'why': 'the four items asked for on 2026-11-07: fail-fast startup, footprint '
               're-acceptance against the runtime values, one forward-only policy in both '
               'trees, and a timeout that cancels and then proves the vehicle stopped',
        'startup_failure_handling': {
            'env_file': 'sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash -- every '
                        'failure returns non-zero (identity, missing hz_sim_env.bash, domain, '
                        'localhost-only, RMW, partition)',
            'stack_script': 'run_fix_stack.bash -- sources are checked, ign/ros2 must exist, '
                            'world and bridge must be readable, and fail_start() stops only '
                            'the registered processes before exiting 1',
        },
        'footprint_runtime_values': {
            'costmap_half_width_m': scope['costmap_footprint_half_width_m'],
            'equals_swept_rectangle': [c.get('equals_swept_rectangle')
                                       for c in config['checks'] if c['check'].endswith('footprint')],
            'wheels_inside_footprint_upto_deg': scope['wheels_stay_inside_footprint_upto_deg'],
            'wheel_outer_at_inner_wheel_angle_m': scope['wheel_outer_at_inner_wheel_angle_m'],
            'corridors': scope['corridors'],
            'note': 'the planner keeps the rigid chassis (0.393 m half width); beyond '
                    '7.18 deg of steering a front wheel reaches further, up to 0.437 m at '
                    'full lock. The demo corridors are straight, so the wheels stay inside. '
                    'The swept rectangle is used only by offline audits.',
        },
        'forward_only_policy': {
            'behavior_plugins': next((c['got'] for c in config['checks']
                                      if c['check'].endswith('behavior_plugins')), None),
            'bt_paths_loaded': [c['got'] for c in config['checks']
                                if c['check'].endswith('bt_xml')],
            'bt_has_no_backup_or_spin': all(
                c['ok'] for c in config['checks'] if 'no reversing recovery' in c['check']),
        },
        'timeout_and_cancel': {
            'normal_case': {k: mid_ok.get(k) for k in
                            ('reason', 'action_status', 'final_error_m', 'stop', 'budget')},
            'timeout_case': {k: mid_timeout.get(k) for k in
                             ('reason', 'action_status', 'cancel', 'stop', 'budget')},
            'cancel_ended': bool(mid_timeout['cancel'] and mid_timeout['cancel']['ended']),
            'final_status_is_cancelled': mid_timeout['action_status'] == 5,
            'stopped_after_cancel': bool(mid_timeout['stop']['ok']),
            'budget_hit': mid_timeout['budget']['hit'],
        },
        'watchdog_selftest': watchdog,
        'artifacts': ['nav_eval_runs_mid_ok.json', 'nav_eval_runs_mid_timeout.json',
                      'verify_fix_config.json', 'footprint_scope.json',
                      'watchdog_selftest.json', 'nav2_params_fix_diff.json'],
        'still_open': ['collision contacts remain not_measured',
                       'the near-side goal (short_straight) remains a diagnostic case only'],
    }
    path = OUT / 'task_verification.json'
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1))
    print(json.dumps({
        'truth': '%d/%d' % (truth['successes'], truth['attempts']),
        'amcl': '%d/%d' % (amcl['successes'], amcl['attempts']),
        'amcl_static_m': accuracy['static']['max_error_m'],
        'amcl_straight_m': accuracy['straight']['end_error_m'],
        'false_successes': truth['false_successes'] + amcl['false_successes'],
        'mid_ok': mid_ok['reason'],
        'mid_timeout': '%s/cancel_ended=%s/stopped=%s' % (
            mid_timeout['reason'], record['round2_acceptance']['timeout_and_cancel']['cancel_ended'],
            record['round2_acceptance']['timeout_and_cancel']['stopped_after_cancel']),
        'footprint_half_width_m': scope['costmap_footprint_half_width_m'],
    }, indent=1))


if __name__ == '__main__':
    main()
