#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
P=sim/experiments/agentvln_hunter/tools/try_plan.py
S=1.6748,0.2790,0.6729
echo "== goal yaw 0.522 from amcl start"
python3 -B $P 1.885 0.435 0.522 1.6748 0.2790 0.6729 | tail -3
echo "== goal yaw 0.673 from amcl start"
python3 -B $P 1.885 0.435 0.673 1.6748 0.2790 0.6729 | tail -3
echo "== goal yaw 0.0 from amcl start"
python3 -B $P 1.885 0.435 0.0 1.6748 0.2790 0.6729 | tail -3
echo "== goal yaw 0.522 from truth start"
python3 -B $P 1.885 0.435 0.522 1.7284 0.3932 0.6455 | tail -3
echo "== goal 2.0 0.5 yaw 0.522 from amcl start"
python3 -B $P 2.0 0.5 0.522 1.6748 0.2790 0.6729 | tail -3
