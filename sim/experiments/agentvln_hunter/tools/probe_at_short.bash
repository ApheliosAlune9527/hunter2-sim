#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
python3 -B sim/experiments/agentvln_hunter/tools/step3_pipeline.py --no-execute --out outputs/agentvln_hunter_20261108_step3/probe_at_short 2>&1 | tail -40
