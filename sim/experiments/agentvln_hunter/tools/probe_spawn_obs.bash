#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
P=sim/experiments/agentvln_hunter/tools/try_plan.py
for g in "2.4 1.0 0.273" "2.4 1.2 0.197" "2.2 1.2 0.183" "3.0 1.6 0.0" "3.185 1.235 0.30" "2.6 1.2 0.214"; do
  set -- $g
  echo "== spawn -> ($1,$2,$3)"
  python3 -B $P $1 $2 $3 -0.21 -0.77 0.0 | tail -4
done
