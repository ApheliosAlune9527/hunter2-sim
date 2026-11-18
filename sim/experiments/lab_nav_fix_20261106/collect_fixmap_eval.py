"""Collect the 2026-11-07 fixed-map batches into one record.

Three separate runs feed this file, and the point of collecting them is that the
map changed underneath: before this date map_server loaded the grey pixels as
FREE, so the earlier 6/9 and 7/9 were measured in a world where 57.7 % of the
map was drivable.  These numbers replace them for any claim about unknown space.
"""
import json
import pathlib

OUT = pathlib.Path('/mnt/d/rob-memory/outputs/lab_nav_fix_20261106')


def load(name):
    p = OUT / name
    return json.loads(p.read_text()) if p.exists() else None


def trim(run):
    stop = run.get('stop')
    return {
        'goal': run['goal'],
        'round': run['round'],
        'success': run['success'],
        'reason': run['reason'],
        'action_status': run['action_status'],
        'reported_success': run.get('reported_success'),
        'final_error_m': run.get('final_error_m'),
        'heading_error_rad': run.get('heading_error_rad'),
        'sim_seconds': run.get('sim_seconds'),
        # None means "no stop evidence was recorded", which is not the same as
        # "the stop failed" -- the round that never ended never got to ask.
        'stop_recorded': stop is not None,
        'stop_ok': (stop or {}).get('ok'),
        'missing_evidence': run.get('missing_evidence', []),
    }


def summarise(name, runs):
    by_goal = {}
    for r in runs:
        g = by_goal.setdefault(r['goal'], {'attempts': 0, 'successes': 0,
                                           'errors': [], 'reasons': []})
        g['attempts'] += 1
        g['successes'] += 1 if r['success'] else 0
        g['reasons'].append(r['reason'])
        if r.get('final_error_m') is not None:
            g['errors'].append(r['final_error_m'])
    for g in by_goal.values():
        g['mean_error_m'] = (round(sum(g['errors']) / len(g['errors']), 4)
                             if g['errors'] else None)
        del g['errors']
    recorded = [r for r in runs if r['stop_recorded']]
    return {
        'label': name,
        'attempts': len(runs),
        'successes': sum(1 for r in runs if r['success']),
        'false_successes': sum(1 for r in runs
                               if r.get('reported_success') and not r['success']),
        'stops_confirmed': sum(1 for r in recorded if r['stop_ok']),
        'stops_recorded': len(recorded),
        'stops_missing': [{'goal': r['goal'], 'round': r['round'],
                           'reason': r['reason']} for r in runs if not r['stop_recorded']],
        'stops_recorded_but_failed': [{'goal': r['goal'], 'round': r['round']}
                                      for r in recorded if not r['stop_ok']],
        'per_goal': by_goal,
        'runs': runs,
    }


truth_a = load('nav_eval_runs_truth_fixmap.json')
truth_b = load('nav_eval_runs_truth_fixmap_b.json')
amcl = load('nav_eval_runs_amcl_fixmap.json')
acc = load('amcl_eval_fix.json')

truth_runs = []
for doc in (truth_a, truth_b):
    if doc:
        truth_runs += [trim(r) for r in doc['runs']]
truth_runs.sort(key=lambda r: (r['goal'], r['round']))

doc = {
    'date': '2026-11-07',
    'map': {
        'image': 'outputs/lab_nav_20261105/lab_nav_map.pgm',
        'sha256': '98bb0c9ed71da56189d83658f9402eeb53d4bc71828981216e4dd66f86ec74f0',
        'yaml': 'outputs/lab_nav_fix_20261106/lab_nav_map_fix.yaml',
        'free_thresh': 0.10,
        'why': ('free_thresh 0.25 loaded the grey (p=0.196) cells as free; '
                '/map then held 0 unknown cells and allow_unknown: false '
                'protected nothing'),
    },
    'parameters': {
        'file': 'sim/experiments/lab_nav_fix_20261106/nav2_params_fix.yaml',
        'footprint': [[-0.184, -0.393], [0.834, -0.393],
                      [0.834, 0.393], [-0.184, 0.393]],
        'planner': 'SmacPlannerHybrid / DUBIN / minimum_turning_radius 1.669',
        'controller': 'RegulatedPurePursuit / allow_reversing false / '
                      'use_rotate_to_heading false',
        'budget': {'sim_seconds': 60, 'wall_seconds': 150},
        'success_criterion': 'action SUCCEEDED and truth error <= 0.25 m',
    },
    'truth': summarise('truth_fixmap', truth_runs),
    'amcl': summarise('amcl_fixmap', [trim(r) for r in amcl['runs']]) if amcl else None,
    'amcl_accuracy': acc,
    'comparison_with_pre_fix_map': {
        'note': ('the 6/9 and 7/9 recorded before this date were measured while the '
                 'grey cells were loaded as free; they are kept as history, not as '
                 'evidence about unknown space'),
        'truth_pre_fix': {'attempts': 9, 'successes': 6},
        'amcl_pre_fix': {'attempts': 9, 'successes': 7},
    },
    'reading': [
        'mid_offset and long_run reach the goal in every round in both modes.',
        'short_straight is the hard one: 0/3 (truth) and 1/3 (amcl) with a 26 deg '
        'heading change at 2.4 m and a 1.669 m minimum turning radius; the planner '
        'cannot cut the corner any more now that the grey cells are blocked.',
        'one truth round (short_straight r2) never ended after cancel: the cancel was '
        'requested, no goal was acknowledged, no terminal state arrived, and that is '
        'why it is also the one round with no stop evidence at all.',
        'one bad round per mode is not a difference between localisers: with three '
        'rounds the noise band is wider than the gap.',
        'amcl accuracy on the fixed map: static 0.0418 m constant bias, 2.001 m '
        'straight ends 0.0951 m off with 0.0069 rad heading error.',
    ],
    'still_open': [
        'collision contacts: not measured, this build publishes nothing on the '
        'contact sensor',
        'drift figures for these batches are in the run files but not yet in a table',
    ],
}

(OUT / 'fixmap_eval.json').write_text(json.dumps(doc, indent=1))
print(json.dumps({
    'truth': f"{doc['truth']['successes']}/{doc['truth']['attempts']}",
    'truth_stops': f"{doc['truth']['stops_confirmed']}/{doc['truth']['attempts']}",
    'amcl': f"{doc['amcl']['successes']}/{doc['amcl']['attempts']}",
    'amcl_stops': f"{doc['amcl']['stops_confirmed']}/{doc['amcl']['attempts']}",
    'amcl_static': acc['static']['max_error_m'],
    'amcl_straight': acc['straight']['end_error_m'],
    'false_successes': doc['truth']['false_successes'] + doc['amcl']['false_successes'],
    'stops_missing': doc['truth']['stops_missing'],
}, indent=1))
