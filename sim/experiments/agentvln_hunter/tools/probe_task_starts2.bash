#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
P=sim/experiments/agentvln_hunter/tools/try_plan.py
for s in "0.31 -0.47 0.42" "0.83 -0.17 0.60" "1.08 -0.09 0.45" "0.31 -0.47 0.62"; do
  set -- $s
  echo "== ($1,$2,$3) -> (2.0,0.5,0.522)"
  python3 -B $P 2.0 0.5 0.522 $1 $2 $3 | tail -3
done
