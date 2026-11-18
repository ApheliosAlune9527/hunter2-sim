#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
P=sim/experiments/agentvln_hunter/tools/try_plan.py
echo "== obs(2.4,1.0,0.273) -> dock (4.25,1.8,0)"
python3 -B $P 4.25 1.8 0.0 2.4 1.0 0.273 | tail -4
echo "== obs(2.4,1.0,0.273) -> dock (4.393,1.778,0)"
python3 -B $P 4.393 1.778 0.0 2.4 1.0 0.273 | tail -4
