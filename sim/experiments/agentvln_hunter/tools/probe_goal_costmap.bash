#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
python3 -B sim/experiments/agentvln_hunter/tools/query_costmap.py goal,1.885,0.435 robot,1.728,0.393
