#!/usr/bin/env bash
# Launch the lab navigation world headless + the /hz_sim/lab/ bridge.
# Usage: run_lab_nav.bash [--gui]
set -euo pipefail

ROOT=/mnt/d/rob-memory
WORLD=$ROOT/outputs/lab_nav_20261105/lab_nav_world_drive.sdf
BRIDGE=$ROOT/sim/config/lab_nav_bridge.yaml

# Source the project environment FIRST: it sets IGN_PARTITION, ROS_DOMAIN_ID=73,
# ROS_LOCALHOST_ONLY=1 and rmw_cyclonedds_cpp. Setting those before sourcing gets
# silently overwritten, which makes the server and the ROS clients live on
# different partitions / different middlewares.
source $ROOT/wsl/hz_sim_env.bash >/dev/null 2>&1
source /home/aphelios/hz_sim_ws/install/setup.bash >/dev/null 2>&1

if [[ "${1:-}" == "--gui" ]]; then
  exec ign gazebo -r -v 2 "$WORLD"
fi

ign gazebo -s -r -v 2 --headless-rendering "$WORLD" &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT

# Give the server a moment to advertise before the bridge subscribes.
sleep 6
ros2 run ros_gz_bridge parameter_bridge --ros-args \
  -p config_file:=$BRIDGE \
  -p use_sim_time:=true &
BRIDGE_PID=$!

echo "server_pid=$SERVER bridge_pid=$BRIDGE_PID"
wait $BRIDGE_PID
