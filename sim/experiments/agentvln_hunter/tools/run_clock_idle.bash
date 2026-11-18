#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
O=outputs/agentvln_hunter_20261109_contention
mkdir -p $O
echo "== idle"
python3 -B sim/experiments/agentvln_hunter/tools/clock_rate.py --seconds 10 --out $O/idle.json 2>&1 | tail -2
