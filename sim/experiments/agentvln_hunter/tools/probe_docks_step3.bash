#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
for g in "4.0 2.0" "3.9 2.0" "4.0 1.9" "4.2 1.9" "4.4 1.9" "4.4 2.2"; do
  set -- $g
  echo "== dock $1 $2"
  python3 -B sim/experiments/agentvln_hunter/tools/try_plan.py "$1" "$2" 0.0 3.0 1.6 0.0
done
