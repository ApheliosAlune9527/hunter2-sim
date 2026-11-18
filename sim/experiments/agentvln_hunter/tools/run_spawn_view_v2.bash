#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
python3 -B sim/experiments/agentvln_hunter/tools/reset_and_seed.py -0.21 -0.77 0.0 0.0025
python3 -B sim/experiments/agentvln_hunter/tools/capture_step3_camera.py --out outputs/agentvln_hunter_20261108_step3/spawn_view_v2 --frames 3
