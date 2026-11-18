#!/usr/bin/env bash
# Known-coordinate baseline smoke run for task A1.
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
python3 -B sim/experiments/agentvln_hunter/tools/reset_and_seed.py -0.21 -0.77 0.0 0.0025 || exit 2
python3 -B sim/experiments/agentvln_hunter/tools/baseline_goal.py --out outputs/agentvln_hunter_20261108_step4/A1_baseline_r1 2>&1 | tail -40
