#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
B=/mnt/d/rob-memory/sim/experiments/agentvln_hunter
O=outputs/agentvln_hunter_20261108_step4/timing
for r in 1 2; do
  echo "=== baseline r$r"
  python3 -B $B/tools/reset_and_seed.py -0.21 -0.77 0.0 0.0025 > /tmp/tseed.log 2>&1 || { echo seed_failed; sleep 5; python3 -B $B/tools/reset_and_seed.py -0.21 -0.77 0.0 0.0025 > /tmp/tseed.log 2>&1 || { echo seed_failed_again; continue; }; }
  python3 -B $B/tools/baseline_goal.py --layout $B/config/target_layout_b.json --out $O/B1_baseline_r$r > /tmp/trun.log 2>&1
  python3 -c "import json;d=json.load(open('$O/B1_baseline_r$r/report.json'));print('  wall_total',d.get('wall_total_s'),'success',d.get('success'),'park',d.get('parking_distance_m'),'action',d['nav'].get('status'))"
done
echo DONE
