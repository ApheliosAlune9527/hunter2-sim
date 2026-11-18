
import json
p='/mnt/d/rob-memory/outputs/agentvln_reverse_record_20261110_042000/report.json'
d=json.load(open(p))
for k in ('error','failure_stop','face','measured_dock','selection_check','model_decision','forward_control','stopped_pose_audit'):
    print('==', k)
    print(json.dumps(d.get(k), ensure_ascii=False)[:900])
print('== legs (summary)')
for L in d['legs']:
    if isinstance(L, dict):
        keys = {k: L.get(k) for k in ('name','leg','mode','status','reason','goal','start_truth','final_truth','forward_m','reverse_m','stopped') if k in L}
        print(' ', json.dumps(keys, ensure_ascii=False)[:400])
