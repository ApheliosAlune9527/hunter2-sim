#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
probe() { echo "== $1 $2 $3 -> $4 $5 $6"; python3 -B sim/experiments/agentvln_hunter/tools/try_plan.py "$4" "$5" "$6" "$1" "$2" "$3"; }
probe -0.21 -0.77 0.0 1.885 0.435 0.522
probe -0.21 -0.77 0.0 1.3 -0.7 0.0
probe -0.21 -0.77 0.0 1.7 0.0 0.0
probe -0.21 -0.77 0.0 2.0 0.0 0.0
probe -0.21 -0.77 0.0 2.2 0.4 0.5
probe -0.21 -0.77 0.0 3.185 1.235 0.3
