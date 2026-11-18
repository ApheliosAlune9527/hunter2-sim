
import json
from pathlib import Path
D = Path('/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy')
def episodes(p, label):
    d = json.loads(Path(p).read_text())
    eps = d.get('episodes') or d.get('trials') or []
    print('==', label, 'frame=', str(d.get('frame',''))[-40:], 'truth=', d.get('candidate_truth'))
    for e in eps:
        print('   %-26s %-18s exp=%s got=%s correct=%s model_calls=%s tool_calls=%s' % (
            e.get('condition',''), e.get('instruction',''), e.get('expected_box'), e.get('selected_candidate'),
            e.get('correct'), e.get('model_responses'), e.get('tool_calls')))
episodes(D/'paired_2x2_natural_f16/report.json', 'paired_2x2_natural')
episodes(D/'labelled_vlm_f16.json', 'labelled_vlm (带编号+分阶段)')
episodes(D/'labelled_unrestricted_f16.json', 'labelled_unrestricted (自由调度)')
