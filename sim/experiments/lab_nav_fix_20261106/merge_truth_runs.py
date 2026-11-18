"""Merge the two truth run files into one tag so the plot shows all three goals.

The batch stopped after the third short_straight round (the goal never ended after
cancel), so the remaining goals ran as a second file.  Plotting them together is
only about the figure; both files stay as the primary record.
"""
import json
import pathlib

OUT = pathlib.Path('/mnt/d/rob-memory/outputs/lab_nav_fix_20261106')
runs = []
for name in ('nav_eval_runs_truth_fixmap.json', 'nav_eval_runs_truth_fixmap_b.json'):
    p = OUT / name
    if p.exists():
        runs += json.loads(p.read_text())['runs']
goals = [['short_straight', 1.885, 0.435, 0.522],
         ['mid_offset', 3.185, 1.235, 0.5335],
         ['long_run', 4.285, 2.535, 0.634]]
merged = {'runs': runs, 'summary': {}, 'localisation': 'truth', 'goals': goals}
(OUT / 'nav_eval_runs_truth_fixmap_all.json').write_text(json.dumps(merged, indent=1))
print(len(runs))
