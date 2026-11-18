#!/usr/bin/env bash
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
for m in red_sign blue_near blue_far; do echo "=== $m"; ign model -m "$m" -p; done
