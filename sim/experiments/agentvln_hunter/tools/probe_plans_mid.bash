#!/usr/bin/env bash
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
run() { echo "=== $*"; python3 -B sim/experiments/agentvln_hunter/tools/try_plan.py "$@"; }
run 3.185 1.235 0.3 -0.21 -0.77 0
run 4.0 1.5 0.3 3.185 1.235 0.3
run 4.0 1.5 0.3 3.185 1.235 0.5335
run 4.0 1.5 0 3.185 1.235 0.3
