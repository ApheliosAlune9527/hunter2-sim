#!/usr/bin/env bash
# Step-1 stack: frozen Nav2 baseline + AMCL + the RGB-D camera scene.
#   bash start_step1_stack.bash [/tmp/agentvln_step1/meeting]
set -o pipefail
LOG_DIR=${1:-/tmp/agentvln_step1/meeting}
export PARAMS=/mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/nav2_params_fix.yaml
export LOCALIZER=amcl
export WORLD=/mnt/d/rob-memory/sim/experiments/agentvln_hunter/scenes/lab_agentvln_world.sdf
export BRIDGE=/mnt/d/rob-memory/sim/experiments/agentvln_hunter/config/agentvln_bridge.yaml
export LOG_DIR
export GUI=0
export DEADLINE=${DEADLINE:-300}
echo "[step1] LOG_DIR=$LOG_DIR"
bash /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/run_fix_stack.bash
