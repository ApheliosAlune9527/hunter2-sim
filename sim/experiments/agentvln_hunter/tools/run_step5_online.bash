#!/usr/bin/env bash
# Online selection arms on the step-5 scene (stack must already run that world).
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
B=sim/experiments/agentvln_hunter
O=outputs/agentvln_hunter_20261108_step5
L=$B/config/target_layout_step5_swap.json
for arm in depth area; do
  echo "=== online $arm"
  python3 -B $B/tools/reset_and_seed.py -0.21 -0.77 0.0 0.0025 > /tmp/o5seed.log 2>&1 || { echo seed_failed; continue; }
  python3 -B $B/tools/step3_pipeline.py --layout $L --select $arm --instruction far --out $O/online_${arm} > /tmp/o5_$arm.log 2>&1
  python3 - $O/online_${arm} <<PY
import json, sys
d = json.load(open(sys.argv[1] + "/report.json"))
n = d["nav"]
print("  arm", d.get("select_arm"), "success", d["success"], "status", n.get("status"))
print("  selected depth", d["selection_after_depth"].get("median_m"), "map", d["selection_after_depth"].get("map_point_m"))
print("  park", n.get("parking_distance_m"), "yaw", n.get("parking_yaw_error_rad"), "ok", n.get("parking_ok"), "stop", n.get("stop_displacement_m"))
PY
done
echo DONE
