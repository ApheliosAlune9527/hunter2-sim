#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
for g in "4.15 1.78" "4.39 1.83" "4.25 1.80" "4.39 1.78"; do
  set -- $g
  echo "== $1 $2"
  python3 -B sim/experiments/agentvln_hunter/tools/try_plan.py "$1" "$2" 0.0 3.2244 1.5979 0.083
done
