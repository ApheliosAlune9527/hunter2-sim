
import json
from pathlib import Path
D = Path('/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy')
v = json.loads((D/'validation_summary.json').read_text())
for name, r in v['runs'].items():
    cancel = r.get('cancel')
    cs = json.dumps(cancel, ensure_ascii=False)[:90] if cancel else ''
    print('%-24s mode=%-8s passed=%-5s status=%s reason=%s cancel=%s' % (
        name, r.get('mode'), r.get('passed'), r.get('status'), r.get('reason'), cs))
    print('    final=%s err=%s yaw=%s stopped=%s disp=%s' % (
        r.get('final_truth'), r.get('goal_region_error_m'), r.get('goal_region_yaw_error_rad'),
        r.get('stopped'), r.get('stop_truth_displacement_m')))
    vlm = r.get('vlm') or {}
    if vlm: print('    vlm', json.dumps(vlm, ensure_ascii=False)[:180])
print('== contact', v['contact'], '| sim_stop', v['sim_stop'])
print('== end_to_end', json.dumps(v['end_to_end_from_spawn'], ensure_ascii=False)[:260])
print('== vlm_dock', json.dumps(v['vlm_dock_reached_inference'], ensure_ascii=False)[:300])
