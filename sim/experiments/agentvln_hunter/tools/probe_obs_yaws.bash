#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
P=sim/experiments/agentvln_hunter/tools/try_plan.py
for yaw in 0.0 0.3 0.5 0.9; do echo "== leg1 -> (3.0,1.6,$yaw)"; python3 -B $P 3.0 1.6 $yaw 1.885 0.435 0.522 | tail -3; done
echo "== leg1 -> (3.2,1.2,0.3)"; python3 -B $P 3.2 1.2 0.3 1.885 0.435 0.522 | tail -3
echo "== (2.5,0.9,0.6) -> (3.0,1.6,0.0)"; python3 -B $P 3.0 1.6 0.0 2.5 0.9 0.6 | tail -3
echo "== leg1 -> (3.6,1.9,0.4)"; python3 -B $P 3.6 1.9 0.4 1.885 0.435 0.522 | tail -3
