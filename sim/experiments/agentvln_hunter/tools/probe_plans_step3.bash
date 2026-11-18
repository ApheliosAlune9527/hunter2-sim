#!/usr/bin/env bash
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
run() { echo "=== $*"; python3 -B sim/experiments/agentvln_hunter/tools/try_plan.py "$@"; }
run 2.0 1.6 0 1.7 -0.3 0.25
run 2.0 1.6 1.5708 1.7 -0.3 0.25
run 1.8 1.4 1.5708 1.7 -0.3 0.25
run 2.4 1.6 1.5708 1.7 -0.3 0.25
run 2.0 1.6 0 1.7 -0.3 2.0
run 2.0 1.6 0 1.7 -0.3 -0.5
run 3.27 0.73 0.58 1.7 -0.3 0.25
