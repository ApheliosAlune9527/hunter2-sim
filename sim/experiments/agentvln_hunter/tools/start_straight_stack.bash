#!/usr/bin/env bash
set -euo pipefail

experiment=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
fix="${experiment%/*}/lab_nav_fix_20261106"
cd -- "$experiment/../../.."
sha256sum --check --strict "$experiment/config/straight_vlm.sha256"

export LOG_DIR=${LOG_DIR:-/tmp/agentvln_vlm_straight}
export WORLD="$experiment/scenes/lab_agentvln_bigfar_straight.sdf"
export BRIDGE="$experiment/config/agentvln_bridge.yaml"
export HZ_NAV2_MAP_YAML="$experiment/config/straight_nav_map/lab_nav_map_fix.yaml"
export PARAMS="$fix/nav2_params_fix.yaml"
export LOCALIZER=amcl NAV2=1 STAGE=stack
export GUI=${GUI:-0}
exec bash "$fix/run_fix_stack.bash"
