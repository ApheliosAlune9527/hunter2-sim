#!/usr/bin/env bash
# Bring up the whole lab navigation stack and wait until Nav2 reports active.
# Every process records its PID so stop_lab_stack.bash only kills what this
# script started.
set -o pipefail

HERE=/mnt/d/rob-memory/sim/experiments/lab_nav
LOG_DIR=${LOG_DIR:-/tmp/lab_stack}
WORLD=${WORLD:-/mnt/d/rob-memory/outputs/lab_nav_20261105/lab_nav_world_drive.sdf}
DEADLINE=${DEADLINE:-240}
# LOCALIZER=truth (default) publishes map->odom from ground truth.
# LOCALIZER=amcl hands map->odom to AMCL and only odom->base_link is published
# from wheel odometry, so the two never fight over the same edge.
LOCALIZER=${LOCALIZER:-truth}
NAV2=${NAV2:-1}

source "$HERE/lab_nav_env.bash"
# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash
# shellcheck disable=SC1091
source /home/aphelios/hz_sim_ws/install/setup.bash

mkdir -p "$LOG_DIR"
rm -f "$LOG_DIR"/*.pid "$LOG_DIR"/*.log

wait_for_topic() {
  local topic=$1 limit=$2 i=0
  while [ $i -lt "$limit" ]; do
    if ign topic -l 2>/dev/null | grep -qx "$topic"; then return 0; fi
    sleep 1
    i=$((i + 1))
  done
  return 1
}

echo "[stack] starting gz server"
setsid nohup ign gazebo -s -r -v 3 --headless-rendering "$WORLD" > "$LOG_DIR/server.log" 2>&1 &
echo $! > "$LOG_DIR/server.pid"
if ! wait_for_topic /clock 60; then
  echo "[stack] FATAL: /clock never appeared" >&2
  exit 1
fi

echo "[stack] starting bridge"
setsid nohup ros2 run ros_gz_bridge parameter_bridge \
  --ros-args -p config_file:=/mnt/d/rob-memory/sim/config/lab_nav_bridge.yaml \
  -p use_sim_time:=true > "$LOG_DIR/bridge.log" 2>&1 &
echo $! > "$LOG_DIR/bridge.pid"
sleep 3

if [ "$LOCALIZER" = amcl ]; then
  echo "[stack] starting odom_tf + amcl (truth TF publisher stays down)"
  setsid nohup python3 -B "$HERE/odom_tf.py" --ros-args -p use_sim_time:=true \
    > "$LOG_DIR/odom_tf.log" 2>&1 &
  echo $! > "$LOG_DIR/odom_tf.pid"
  # With the navigation stack running, AMCL is created inside that launch so a
  # single lifecycle manager brings up map_server first and AMCL second.
  if [ "$NAV2" = 1 ]; then export WITH_MAP=0; fi
  if [ "$NAV2" != 1 ]; then
    setsid nohup ros2 launch "$HERE/run_amcl.launch.py" > "$LOG_DIR/amcl.log" 2>&1 &
    echo $! > "$LOG_DIR/amcl.pid"
    sleep 4
  fi
else
  echo "[stack] starting truth localisation"
  setsid nohup python3 -B "$HERE/truth_localisation.py" --ros-args -p use_sim_time:=true \
    > "$LOG_DIR/truth.log" 2>&1 &
  echo $! > "$LOG_DIR/truth.pid"
  sleep 3
fi

if [ "$NAV2" != 1 ]; then
  i=0
  while [ $i -lt "$DEADLINE" ]; do
    if [ "$LOCALIZER" = amcl ]; then
      grep -q "Managed nodes are active" "$LOG_DIR"/amcl.log 2>/dev/null && ready=1
    else
      # truth mode has no lifecycle manager to wait for; the localiser is up
      # once its inputs are flowing and the node itself is alive
      if kill -0 "$(cat "$LOG_DIR/truth.pid")" 2>/dev/null &&
         ros2 topic list --no-daemon 2>/dev/null | grep -qx '/ground_truth'; then
        ready=1
      fi
    fi
    if [ "${ready:-0}" = 1 ]; then
      echo "[stack] localisation ready in ${i}s"
      exit 0
    fi
    sleep 2
    i=$((i + 2))
  done
  echo "[stack] FATAL: localisation never became active" >&2
  tail -20 "$LOG_DIR"/amcl.log >&2
  exit 1
fi

echo "[stack] starting nav2"
setsid nohup ros2 launch "$HERE/run_nav2.launch.py" > "$LOG_DIR/nav2.log" 2>&1 &
echo $! > "$LOG_DIR/nav2.pid"

if [ "$LOCALIZER" = amcl ]; then
  # AMCL publishes map -> odom only after an initial pose, and the costmaps will
  # not activate without it, so this has to run in parallel with the bringup.
  sleep 4
  python3 -B "$HERE/init_pose.py" > "$LOG_DIR/init_pose.log" 2>&1 || {
    echo "[stack] FATAL: could not initialise AMCL" >&2
    cat "$LOG_DIR/init_pose.log" >&2
  }
fi

i=0
while [ $i -lt "$DEADLINE" ]; do
  # Read the launch log rather than asking the CLI: a stale ros2 daemon happily
  # reports cached lifecycle states from a previous run.
  if grep -q "Managed nodes are active" "$LOG_DIR/nav2.log" 2>/dev/null; then
    echo "[stack] ready in ${i}s"
    exit 0
  fi
  sleep 2
  i=$((i + 2))
done
echo "[stack] FATAL: nav2 never became active" >&2
tail -20 "$LOG_DIR/nav2.log" >&2
exit 1
