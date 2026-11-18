#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
python3 -B sim/experiments/agentvln_hunter/tools/reset_and_seed.py 3.0 1.6 0.0 0.0025
python3 -B sim/experiments/agentvln_hunter/tools/target_dock.py --out outputs/agentvln_hunter_20261108_step3/dock_query_v3
