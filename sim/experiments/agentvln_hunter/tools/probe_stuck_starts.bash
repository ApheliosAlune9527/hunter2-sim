#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
P=sim/experiments/agentvln_hunter/tools/try_plan.py
echo "== spawn start again"
python3 -B $P 2.4 1.0 0.273 -0.21 -0.77 0.0 | tail -3
echo "== stuck start 0.09,-0.75,0.131"
python3 -B $P 2.4 1.0 0.273 0.09 -0.75 0.131 | tail -3
echo "== stuck start yaw 0.0"
python3 -B $P 2.4 1.0 0.273 0.09 -0.75 0.0 | tail -3
echo "== mid start 0.5,-0.5,0.2"
python3 -B $P 2.4 1.0 0.273 0.5 -0.5 0.2 | tail -3
echo "== spawn -> 2.6,1.2,0.214"
python3 -B $P 2.6 1.2 0.214 -0.21 -0.77 0.0 | tail -3
