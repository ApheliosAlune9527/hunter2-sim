#!/usr/bin/env bash
# One complete operator run-through, done from the shell instead of through RViz.
# It starts the AMCL stack with a manual initial pose, seeds it, checks that the live
# scan sits on the map, drives one goal, cancels a second goal while it is moving,
# confirms the stop evidence, and stops the stack through the registry.
#
# Every step writes to $LOG so the transcript is the record, not this comment.

cd "$(dirname "$0")" || exit 1
HERE=$(pwd)
OUT=/mnt/d/rob-memory/outputs/lab_nav_fix_20261106
LOG=/tmp/lab_selfrun
STACK_LOG=/tmp/lab_selfrun_stack
rm -rf "$LOG" "$STACK_LOG"
mkdir -p "$LOG" "$STACK_LOG"

# run_fix_stack.bash clears "$LOG_DIR"/*.log before it starts, so the stack keeps its
# own registry directory; the transcript below stays readable after the fact.
export LOG_DIR=$STACK_LOG
export LOCALIZER=amcl
export INIT_POSE=manual
export NAV2=1

source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash || exit 1

echo "=== step 1: start the stack (manual initial pose)"
bash "$HERE/run_fix_stack.bash" > "$STACK_LOG/stack.log" 2>&1 &
STACK_PID=$!

# The banner is printed before the long wait; seeing it means the stack is up and
# waiting for a pose rather than still loading.
for _ in $(seq 1 60); do
  grep -q 'Waiting up to' "$STACK_LOG/stack.log" 2>/dev/null && break
  sleep 2
done
sleep 8
echo "--- stack so far:"; tail -6 "$STACK_LOG/stack.log"

echo "=== step 2: give AMCL the starting pose (the 2D Pose Estimate button does this)"
timeout 20 ros2 topic pub --once /initialpose geometry_msgs/msg/PoseWithCovarianceStamped \
  "{header: {frame_id: map}, pose: {pose: {position: {x: -0.21, y: -0.77}, orientation: {w: 1.0}}, covariance: [0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0685, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}}" \
  > "$LOG/seed.log" 2>&1
echo "pose published"

wait $STACK_PID
STACK_EXIT=$?
echo "--- stack start exit=$STACK_EXIT"; tail -3 "$STACK_LOG/stack.log"
if [ "$STACK_EXIT" -ne 0 ]; then
  echo "stack did not become ready; stopping what was registered"
  LOG_DIR=$STACK_LOG bash "$HERE/stop_fix_stack.bash"
  exit 1
fi

echo "=== step 3: does the live scan sit on the map walls?"
python3 -B "$HERE/check_scan_map.py" 2>&1 | grep -v 'multicast' | tail -2 | tee "$LOG/scan_map.log"

echo "=== step 4: amcl estimate versus the simulator's own pose"
timeout 6 ros2 run tf2_ros tf2_echo map base_link 2>/dev/null | grep -m1 Translation | tee "$LOG/pose.log"

echo "=== step 5: drive mid_offset (known good goal)"
python3 -B "$HERE/run_nav_eval_fix.py" --tag selfrun_mid --localizer amcl \
  --goals mid_offset --rounds 1 --budget-sim 60 --wall-budget 200 2>&1 | tail -3

echo "=== step 6: cancel long_run while it is still moving"
python3 -B "$HERE/run_nav_eval_fix.py" --tag selfrun_cancel --localizer amcl \
  --goals long_run --rounds 1 --budget-sim 6 --wall-budget 200 2>&1 | tail -3

echo "=== step 7: stop the stack"
LOG_DIR=$STACK_LOG bash "$HERE/stop_fix_stack.bash"

echo "=== summary"
python3 - "$OUT" "$LOG" <<'PY'
import json, pathlib, sys
out, log = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
doc = {'steps': {}, 'files': {}}
for tag in ('selfrun_mid', 'selfrun_cancel'):
    p = out / f'nav_eval_runs_{tag}.json'
    if not p.exists():
        doc['steps'][tag] = 'missing'
        continue
    runs = json.loads(p.read_text())['runs']
    doc['steps'][tag] = [{
        'goal': r['goal'], 'success': r.get('success'),
        'action_status': r.get('action_status'),
        'final_error_m': r.get('final_error_m'),
        'stop': (r.get('stop') or {}).get('ok'),
        'cancel': {k: (r.get('cancel') or {}).get(k) for k in
                   ('requested', 'acknowledged_goals', 'ended', 'final_status')},
    } for r in runs]
    doc['files'][tag] = str(p.name)
scan = log / 'scan_map.log'
if scan.exists():
    doc['scan_on_wall'] = scan.read_text().strip()
pose = log / 'pose.log'
if pose.exists():
    doc['amcl_pose'] = pose.read_text().strip()
(out / 'selfrun.json').write_text(json.dumps(doc, indent=1))
print(json.dumps(doc, indent=1))
PY
