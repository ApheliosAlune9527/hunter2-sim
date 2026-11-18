#!/usr/bin/env bash
# Repeat the successful step-3 closed loop (three runs for repeatability).
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
for tag in v11 v12; do
  echo "=== $tag"
  python3 -B sim/experiments/agentvln_hunter/tools/reset_and_seed.py -0.21 -0.77 0.0 0.0025 || exit 2
  python3 -B sim/experiments/agentvln_hunter/tools/step3_pipeline.py --out outputs/agentvln_hunter_20261108_step3/pipeline_$tag > /tmp/${tag}.log 2>&1
  python3 -c "import json,sys; d=json.load(open('outputs/agentvln_hunter_20261108_step3/pipeline_$tag/report.json')); n=d['nav']; print('$tag', 'success', d['success'], 'status', n.get('status'), 'park', n.get('parking_distance_m'), n.get('parking_yaw_error_rad'), n.get('parking_ok'), 'stop', n.get('stop_displacement_m'), 'attempts', n.get('attempts_used'))"
done
