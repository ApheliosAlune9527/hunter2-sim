#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
P=sim/experiments/agentvln_hunter/tools/try_plan.py
echo "== spawn -> obs(2.0,1.5,0.126)"
python3 -B $P 2.0 1.5 0.126 -0.21 -0.77 0.0 | tail -3
echo "== leg1(1.885,0.435,0.522) -> obs(2.0,1.5,0.126)"
python3 -B $P 2.0 1.5 0.126 1.885 0.435 0.522 | tail -3
echo "== obs(2.0,1.5,0.126) -> dock(4.385,1.83,0.138)"
python3 -B $P 4.385 1.83 0.138 2.0 1.5 0.126 | tail -3
echo "== obs(2.0,1.5,0.126) -> dock(4.25,1.8,0.14)"
python3 -B $P 4.25 1.8 0.14 2.0 1.5 0.126 | tail -3
