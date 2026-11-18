#!/usr/bin/env bash
# Full-loop wall-time sample on the B arrangement (B1 start), 3 visual + 3 baseline.
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
B=/mnt/d/rob-memory/sim/experiments/agentvln_hunter
O=outputs/agentvln_hunter_20261108_step4/timing
mkdir -p $O
for mode in visual baseline; do
  for r in 1 2 3; do
    echo "=== $mode r$r"
    python3 -B $B/tools/reset_and_seed.py -0.21 -0.77 0.0 0.0025 > /tmp/tseed.log 2>&1 || { echo seed_failed; continue; }
    if [ "$mode" = visual ]; then
      python3 -B $B/tools/step3_pipeline.py --layout $B/config/target_layout_b.json --out $O/B1_${mode}_r$r > /tmp/trun.log 2>&1
    else
      python3 -B $B/tools/baseline_goal.py --layout $B/config/target_layout_b.json --out $O/B1_${mode}_r$r > /tmp/trun.log 2>&1
    fi
    python3 -c "import json;d=json.load(open('$O/B1_${mode}_r$r/report.json'));print('  wall_total',d.get('wall_total_s'),'success',d.get('success'),'park',(d.get('parking_distance_m') or (d.get('nav') or {}).get('parking_distance_m')),'action',(d.get('nav') or {}).get('status'))"
  done
done
