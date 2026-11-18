
import json, math
from pathlib import Path
rep = json.loads(Path('/mnt/d/rob-memory/outputs/agentvln_reverse_record_20261110_042000/report.json').read_text())
leg = rep['legs'][3]
path = leg['path']
stop = leg['final_truth']
best = min(path, key=lambda p: math.hypot(p[0]-stop[0], p[1]-stop[1]))
i = path.index(best)
print('stop', [round(v,3) for v in stop])
print('nearest planned pose', [round(v,3) for v in best], 'index', i, 'of', len(path))
print('offset_m', round(math.hypot(best[0]-stop[0], best[1]-stop[1]), 3),
      'heading_planned', round(best[2],3), 'heading_truth', round(stop[2],3),
      'heading_diff', round(abs(stop[2]-best[2]),3))
# where along the plan does the heading drop below 0.6?
for k in range(0, len(path), max(1, len(path)//12)):
    p = path[k]
    print('  %3d  x=%.2f y=%.2f yaw=%.2f' % (k, p[0], p[1], p[2]))
print('plan_length', leg['plan_length_m'], 'executed', leg['forward_m'])
print('track samples', len(leg['track']), 'max loc err', leg['max_localization_error'])
