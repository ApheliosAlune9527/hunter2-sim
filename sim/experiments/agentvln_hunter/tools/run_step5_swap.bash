#!/usr/bin/env bash
# Swap control: restart the stack on the exchanged-box scene, capture, re-run the trials.
set +u
B=/mnt/d/rob-memory/sim/experiments/agentvln_hunter
STOP=/mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/stop_fix_stack.bash
LOG_DIR=/tmp/agentvln_step5/base8 bash "$STOP" || echo "[swap] stop leftovers"
WORLD=$B/scenes/lab_agentvln_bigfar_swap.sdf bash $B/tools/start_step3_stack.bash /tmp/agentvln_step5/base9 || exit 3
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
python3 -B $B/tools/reset_and_seed.py 2.0 0.5 0.522 0.0025 || exit 2
python3 -B $B/tools/step5_replay.py --out outputs/agentvln_hunter_20261108_step5/bigfar_swap_frame --layout $B/config/target_layout_step5_swap.json 2>&1 | tail -8
O=outputs/agentvln_hunter_20261108_step5/selection_trials_swap
F=outputs/agentvln_hunter_20261108_step5/bigfar_swap_frame
L=$B/config/target_layout_step5_swap.json
T=$B/tools/step5_agent.py
FAR="经过红牌，停在较远的那个蓝箱前方"
NEAR="经过红牌，停在较近的那个蓝箱前方"
for pair in "far_area:$FAR:area" "far_depth:$FAR:depth" "near_area:$NEAR:area" "near_depth:$NEAR:depth"; do
  name=${pair%%:*}; rest=${pair#*:}; instr=${rest%%:*}; backend=${rest#*:}
  echo "=== swap $name ($backend)"
  python3 -B $T --frame $F --instruction "$instr" --backend $backend --layout $L --out $O/$name 2>&1 | grep -E "selected_candidate|selected_box_truth|correct|status" 
done
echo DONE
