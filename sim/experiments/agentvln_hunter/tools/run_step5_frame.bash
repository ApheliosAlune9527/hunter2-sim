#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
python3 -B sim/experiments/agentvln_hunter/tools/reset_and_seed.py 2.0 0.5 0.522 0.0025 || exit 2
python3 -B sim/experiments/agentvln_hunter/tools/step5_replay.py --out outputs/agentvln_hunter_20261108_step5/bigfar_frame --layout sim/experiments/agentvln_hunter/config/target_layout_step5.json
