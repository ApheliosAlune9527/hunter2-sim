#!/usr/bin/env bash
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
for m in marker_red marker_green marker_blue hz_hunter_full; do
  echo "=== $m ==="
  ign model -m "$m" -p 2>&1 | head -20
done
echo "=== camera sensor ==="
ign model -m hz_hunter_full -l base_link -s agentvln_camera 2>&1 | head -40
