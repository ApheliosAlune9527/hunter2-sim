#!/usr/bin/env bash
# Bring up the step-3 scene stack (red sign + two blue boxes) on ROS domain 73.
#
#   bash start_step3_stack.bash [/tmp/agentvln_step3/baseN]
#
# The only differences from the step-1 camera stack are WORLD (the step-3 scene)
# and LOG_DIR; parameters, bridge, map and localiser stay on the fixed baseline.
set -o pipefail
LOG_DIR=${1:-/tmp/agentvln_step3/base4}
export PARAMS=/mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/nav2_params_fix.yaml
export LOCALIZER=amcl
# Override WORLD=... to run the exchanged-arrangement scene.
export WORLD=${WORLD:-/mnt/d/rob-memory/sim/experiments/agentvln_hunter/scenes/lab_agentvln_targets.sdf}
export BRIDGE=/mnt/d/rob-memory/sim/experiments/agentvln_hunter/config/agentvln_bridge.yaml
export LOG_DIR
export GUI=0
export DEADLINE=${DEADLINE:-300}
echo "[step3] LOG_DIR=$LOG_DIR"
bash /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/run_fix_stack.bash
