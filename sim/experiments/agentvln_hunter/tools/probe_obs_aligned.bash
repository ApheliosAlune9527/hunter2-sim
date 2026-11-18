#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
P=sim/experiments/agentvln_hunter/tools/try_plan.py
for g in "2.0 0.5 0.522" "1.7 0.4 0.550" "2.1 0.5 0.503"; do
  set -- $g
  echo "== spawn -> ($1,$2,$3)"
  python3 -B $P $1 $2 $3 -0.21 -0.77 0.0 | tail -3
  echo "== obs($1,$2,$3) -> dock (4.25,1.8,0)"
  python3 -B $P 4.25 1.8 0.0 $1 $2 $3 | tail -3
done
