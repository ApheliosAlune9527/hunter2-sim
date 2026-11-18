#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
for g in "4.389 1.883" "4.389 1.783" "4.25 1.80" "4.10 1.75" "3.90 1.70" "3.60 1.60" "4.00 1.80"; do
  set -- $g
  echo "== $1 $2"
  python3 -B sim/experiments/agentvln_hunter/tools/try_plan.py "$1" "$2" 0.0 3.5938 1.6767 0.3053
done
