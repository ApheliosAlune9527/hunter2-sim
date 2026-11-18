#!/usr/bin/env bash
# Selection trials on the bigfar replay frame: near/far instruction x area/depth backend.
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
O=outputs/agentvln_hunter_20261108_step5/selection_trials
F=outputs/agentvln_hunter_20261108_step5/bigfar_frame
L=sim/experiments/agentvln_hunter/config/target_layout_step5.json
T=sim/experiments/agentvln_hunter/tools/step5_agent.py
FAR="经过红牌，停在较远的那个蓝箱前方"
NEAR="经过红牌，停在较近的那个蓝箱前方"
for pair in "far_area:$FAR:area" "far_depth:$FAR:depth" "near_area:$NEAR:area" "near_depth:$NEAR:depth"; do
  name=${pair%%:*}; rest=${pair#*:}; instr=${rest%%:*}; backend=${rest#*:}
  echo "=== $name ($backend)"
  python3 -B $T --frame $F --instruction "$instr" --backend $backend --layout $L --out $O/$name 2>&1 | tail -12
done
echo "=== vlm probe"
python3 -B $T --frame $F --instruction "$FAR" --backend vlm --layout $L --out $O/vlm_probe 2>&1 | tail -6; echo "exit=$?"
