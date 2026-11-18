#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
probe() { echo "== $1 $2 $3 -> $4 $5 $6"; python3 -B sim/experiments/agentvln_hunter/tools/try_plan.py "$4" "$5" "$6" "$1" "$2" "$3"; }
probe -0.21 -0.77 0.0 1.8 -0.1 0.785
probe -0.21 -0.77 0.0 1.73 -0.33 0.225
probe -0.21 -0.77 0.0 1.7 -0.3 0.0
probe 0.4 -0.69 0.288 1.8 -0.1 0.785
probe 0.4 -0.69 0.288 1.73 -0.33 0.225
probe 1.73 -0.33 0.225 3.0 1.6 0.0
probe 1.73 -0.33 0.225 3.27 0.73 0.58
