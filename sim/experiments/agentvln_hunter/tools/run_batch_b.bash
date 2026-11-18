#!/usr/bin/env bash
# Batch B: stop the A-arrangement stack, start the variant-B scene, run B1-B3.
set +u
BASE=/mnt/d/rob-memory/sim/experiments/agentvln_hunter
STOP=/mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/stop_fix_stack.bash
export LOG_DIR=/tmp/agentvln_step3/base6
bash "$STOP" || echo "[batchB] stop reported leftovers"
WORLD=$BASE/scenes/lab_agentvln_targets_b.sdf bash "$BASE/tools/start_step3_stack.bash" /tmp/agentvln_step3/base7 || exit 3
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
python3 -B sim/experiments/agentvln_hunter/tools/run_task_matrix.py \
  --layout "$BASE/config/target_layout_b.json" \
  --tsv outputs/agentvln_hunter_20261108_step4/task_runs_b.tsv \
  --tasks "B1:-0.21:-0.77:0.0,B2:0.31:-0.47:0.42,B3:0.83:-0.17:0.60"
