#!/usr/bin/env bash
# Restart on the bigfar-v2 scene, probe reachability, capture, run the 4 offline trials.
set +u
B=/mnt/d/rob-memory/sim/experiments/agentvln_hunter
STOP=/mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/stop_fix_stack.bash
LOG_DIR=/tmp/agentvln_step5/base9 bash "$STOP" || echo "[v2] stop leftovers"
WORLD=$B/scenes/lab_agentvln_bigfar.sdf bash $B/tools/start_step3_stack.bash /tmp/agentvln_step5/base10 || exit 3
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
echo "== plan spawn -> obs"
python3 -B $B/tools/try_plan.py 1.52 0.23 0.522 -0.21 -0.77 0.0 | tail -3
echo "== plan obs -> far dock"
python3 -B $B/tools/try_plan.py 3.03 1.46 0.686 1.52 0.23 0.522 | tail -3
python3 -B $B/tools/reset_and_seed.py 1.52 0.23 0.522 0.0025 || exit 2
python3 -B $B/tools/step5_replay.py --out outputs/agentvln_hunter_20261108_step5/bigfar2_frame --layout $B/config/target_layout_step5.json 2>&1 | grep -E "area_px|depth_median_m|rule_|id|agrees" | head -20
O=outputs/agentvln_hunter_20261108_step5/selection_trials_v2
F=outputs/agentvln_hunter_20261108_step5/bigfar2_frame
L=$B/config/target_layout_step5.json
T=$B/tools/step5_agent.py
FAR="经过红牌，停在较远的那个蓝箱前方"
NEAR="经过红牌，停在较近的那个蓝箱前方"
for pair in "far_area:$FAR:area" "far_depth:$FAR:depth" "near_area:$NEAR:area" "near_depth:$NEAR:depth"; do
  name=${pair%%:*}; rest=${pair#*:}; instr=${rest%%:*}; backend=${rest#*:}
  printf "%s: " $name
  python3 -B $T --frame $F --instruction "$instr" --backend $backend --layout $L --out $O/$name 2>&1 | grep -E "selected_candidate|selected_box_truth|correct" | tr "\n" " "; echo
done
echo DONE
