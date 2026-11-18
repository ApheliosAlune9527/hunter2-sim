#!/usr/bin/env bash
# Controlled ablations for step 3: no re-observation, and no active depth query.
set +u
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
cd /mnt/d/rob-memory
O=outputs/agentvln_hunter_20261108_step3
echo "=== ablation: no re-observation (correction off)"
python3 -B sim/experiments/agentvln_hunter/tools/reset_and_seed.py -0.21 -0.77 0.0 0.0025 || exit 2
python3 -B sim/experiments/agentvln_hunter/tools/step3_pipeline.py --max-reobserves 0 --out $O/ablation_no_reobserve > /tmp/abl1.log 2>&1
python3 -c "import json;d=json.load(open('$O/ablation_no_reobserve/report.json'));print('no_reobserve success',d['success'],'reason',d.get('reason'),'stages',[s['component_count'] for s in d['stages']])"
echo "=== ablation: no active depth query (area proxy selection)"
python3 -B sim/experiments/agentvln_hunter/tools/reset_and_seed.py -0.21 -0.77 0.0 0.0025 || exit 2
python3 -B sim/experiments/agentvln_hunter/tools/step3_pipeline.py --no-depth-query --out $O/ablation_no_depth_query > /tmp/abl2.log 2>&1
python3 -c "import json;d=json.load(open('$O/ablation_no_depth_query/report.json'));n=d['nav'];print('no_depth_query success',d['success'],'sel',d['selection_after_depth']['criterion'],'map',d['selection_after_depth']['map_point_m'],'park',n.get('parking_distance_m'),n.get('parking_yaw_error_rad'),n.get('parking_ok'),'stop',n.get('stop_displacement_m'))"
