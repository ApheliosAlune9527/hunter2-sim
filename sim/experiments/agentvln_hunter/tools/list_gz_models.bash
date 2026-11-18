#!/usr/bin/env bash
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
echo "PARTITION=$IGN_PARTITION"
echo "--- models ---"
ign model --list 2>&1 | head -60
echo "--- topics ---"
ign topic -l 2>&1 | grep -E 'marker|camera|clock' | head -40
