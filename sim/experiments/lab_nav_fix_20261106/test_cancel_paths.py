"""Targeted test for the two halves of the unconfirmed-cancel path.

The branch itself needs a navigator that accepts a goal, is asked to cancel, and never
answers -- that is a real flake, not something the simulator can be told to produce on
demand.  What *is* testable is everything that branch does once it fires:

  A. the record it writes: the round has no stop evidence, `stops_missing` names it, and
     it is not counted as a confirmed stop;
  B. the session teardown: `_stop_session()` runs stop_fix_stack.bash against the
     registry, which refuses to signal a pid whose kernel start time no longer matches.

So this file proves the record and the teardown, and says plainly that the trigger
itself was seen once in a real batch rather than reproduced here.
"""
import json
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path('/mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106')
OUT = pathlib.Path('/mnt/d/rob-memory/outputs/lab_nav_fix_20261106')
sys.path.insert(0, str(HERE))

import collect_fixmap_eval as summary  # noqa: E402  (module runs its report on import)
import run_nav_eval_fix as ev  # noqa: E402

results = {}

# ---------------------------------------------------------------- A: the record
synthetic = [{
    'goal': 'short_straight', 'round': 2, 'success': False,
    'reason': 'goal_did_not_end', 'action_status': None, 'reported_success': None,
    'final_error_m': None, 'heading_error_rad': None, 'sim_seconds': 61.0,
    'cancel': {'reason': 'budget_sim', 'requested': True, 'acknowledged': False,
               'acknowledged_goals': 0, 'ended': False, 'final_status': None},
    'stop': None,
    'missing_evidence': ['action_terminal_state', 'cancel_acknowledgement',
                         'stop_not_confirmed'],
}, {
    'goal': 'mid_offset', 'round': 0, 'success': True, 'reason': 'succeeded',
    'action_status': 4, 'reported_success': True, 'final_error_m': 0.15,
    'heading_error_rad': 0.08, 'sim_seconds': 16.4,
    'cancel': None,
    'stop': {'ok': True, 'held_s': 1.0, 'v_max': 0.0, 'w_max': 0.0},
}]
trimmed = [summary.trim(r) for r in synthetic]
doc = summary.summarise('test', trimmed)
results['record'] = {
    'stops_confirmed': doc['stops_confirmed'],
    'stops_recorded': doc['stops_recorded'],
    'stops_missing': doc['stops_missing'],
    'ok': (doc['stops_confirmed'] == 1 and doc['stops_recorded'] == 1
           and len(doc['stops_missing']) == 1
           and doc['stops_missing'][0]['goal'] == 'short_straight'),
}

# ------------------------------------------------------------- B: the teardown
tmp = pathlib.Path('/tmp/lab_cancel_selftest')
tmp.mkdir(parents=True, exist_ok=True)
for old in ('processes.tsv',):
    (tmp / old).unlink(missing_ok=True)
proc = subprocess.Popen(['sleep', '90'])
time.sleep(0.3)
stat = open('/proc/%d/stat' % proc.pid).read()
start_time = stat.rsplit(')', 1)[1].split()[19]   # field 22 overall, 20 after comm
cmdline = open('/proc/%d/cmdline' % proc.pid).read().replace('\0', ' ').strip()
(tmp / 'processes.tsv').write_text('sleep90\t%d\t%s\t%s\n' % (proc.pid, start_time, cmdline))

args = type('A', (), {})()
args.stack_log_dir = str(tmp)
cleanup = ev._stop_session(args)
still = os.path.exists('/proc/%d' % proc.pid) and \
    open('/proc/%d/stat' % proc.pid).read().split()[2] != 'Z'
results['teardown'] = {
    'cleanup': cleanup,
    'process_alive_after': still,
    'ok': bool(cleanup.get('returncode') == 0 and not still),
}

# A pid that has been reused must be refused rather than signalled: register a wrong
# start time and check the script reports it as skipped instead of killing it.
wrong = pathlib.Path('/tmp/lab_cancel_selftest_wrong')
wrong.mkdir(parents=True, exist_ok=True)
(wrong / 'processes.tsv').unlink(missing_ok=True)
proc2 = subprocess.Popen(['sleep', '90'])
time.sleep(0.3)
(wrong / 'processes.tsv').write_text('sleep90\t%d\t%s\t%s\n'
                                     % (proc2.pid, '1', 'sleep 90'))
args.stack_log_dir = str(wrong)
refused = ev._stop_session(args)
alive2 = os.path.exists('/proc/%d' % proc2.pid)
results['reused_pid_refused'] = {
    'cleanup_stdout': (refused.get('stdout') or '').splitlines()[-2:],
    'process_alive_after': alive2,
    'ok': bool(alive2),
}
proc2.kill()

results['trigger_reproduced_here'] = False
results['note'] = ('the trigger (cancel requested, never answered) was seen once in '
                   'nav_eval_runs_truth_fixmap.json short_straight r2; this test proves '
                   'the record and the teardown, not the trigger')
results['ok'] = all(v.get('ok') for k, v in results.items()
                    if isinstance(v, dict) and 'ok' in v)
(OUT / 'cancel_path_test.json').write_text(json.dumps(results, indent=1))
print(json.dumps(results, indent=1))
