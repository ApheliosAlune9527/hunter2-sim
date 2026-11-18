#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
P=sim/experiments/agentvln_hunter/tools/try_plan.py
for g in "3.0 1.6 0.0" "2.9 1.5 0.1" "3.1 1.7 0.0" "3.0 1.6 0.15" "3.2 1.8 0.0"; do
  set -- $g
  echo "== obs(2.0,0.5,0.522) -> stage($1,$2,$3)"
  python3 -B $P $1 $2 $3 2.0 0.5 0.522 | tail -3
done
