#!/usr/bin/env bash
# Step-3 closed loop from spawn with the (2.4, 1.0) observation pose.
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
python3 -B sim/experiments/agentvln_hunter/tools/reset_and_seed.py -0.21 -0.77 0.0 0.0025
python3 -B sim/experiments/agentvln_hunter/tools/step3_pipeline.py --out outputs/agentvln_hunter_20261108_step3/pipeline_v4
