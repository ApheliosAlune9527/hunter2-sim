#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
P=sim/experiments/agentvln_hunter/tools/try_plan.py
echo "== leg1 -> obs(3.0,1.6,0)"
python3 -B $P 3.0 1.6 0.0 1.885 0.435 0.522 | tail -4
echo "== shortpose -> obs(3.0,1.6,0)"
python3 -B $P 3.0 1.6 0.0 1.726 0.319 0.655 | tail -4
echo "== obs(3.0,1.6,0) -> dock(4.393,1.778,0)"
python3 -B $P 4.393 1.778 0.0 3.0 1.6 0.0 | tail -4
