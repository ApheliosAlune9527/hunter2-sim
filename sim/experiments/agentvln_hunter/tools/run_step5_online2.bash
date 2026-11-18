#!/usr/bin/env bash
# Re-run the depth arm on the step-5 swap scene with the back-off sweep retry.
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
B=sim/experiments/agentvln_hunter
O=outputs/agentvln_hunter_20261108_step5
python3 -B $B/tools/reset_and_seed.py -0.21 -0.77 0.0 0.0025 > /tmp/o5seed.log 2>&1 || exit 2
python3 -B $B/tools/step3_pipeline.py --layout $B/config/target_layout_step5_swap.json --select depth --instruction far --out $O/online_depth2 > /tmp/o5_d2.log 2>&1
python3 - $O/online_depth2 <<PY
import json, sys
d = json.load(open(sys.argv[1] + "/report.json"))
n = d["nav"]
print("success", d["success"], "status", n.get("status"), "attempts", n.get("attempts_used"))
print("sel", d["selection_after_depth"].get("median_m"), d["selection_after_depth"].get("map_point_m"))
print("dock", {k: d["chosen_dock"].get(k) for k in ("x","y","yaw","backoff_m")})
print("park", n.get("parking_distance_m"), "yaw", n.get("parking_yaw_error_rad"), "ok", n.get("parking_ok"), "stop", n.get("stop_displacement_m"))
for a in d.get("dock_attempts", []):
    print(" attempt", a["attempt"], a["nav"].get("status"), a["nav"].get("truth_after"), "retry_cands", len(a.get("retry_candidates") or []))
PY
