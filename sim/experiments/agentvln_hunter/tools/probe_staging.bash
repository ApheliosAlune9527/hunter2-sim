#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
P=sim/experiments/agentvln_hunter/tools/try_plan.py
echo "== obs(2.0,0.5,0.522) -> stage(2.87,1.92,0.0)"
python3 -B $P 2.87 1.92 0.0 2.0 0.5 0.522 | tail -3
echo "== obs(2.0,0.5,0.522) -> stage(2.37,1.92,0.0)"
python3 -B $P 2.37 1.92 0.0 2.0 0.5 0.522 | tail -3
echo "== stage(2.87,1.92,0.0) -> dock(4.373,1.921,0.0)"
python3 -B $P 4.373 1.921 0.0 2.87 1.92 0.0 | tail -3
echo "== stage(2.37,1.92,0.0) -> dock(4.373,1.921,0.0)"
python3 -B $P 4.373 1.921 0.0 2.37 1.92 0.0 | tail -3
