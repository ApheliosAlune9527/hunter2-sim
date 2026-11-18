#!/usr/bin/env bash
# Profile one world: start the server and the bridge, measure, stop everything.
#
# usage: measure_profile.bash <world.sdf> <bridge.yaml> <label> [seconds]
#
# Deliberately uses its own partition and its own log directory: a profile run
# must not disturb, or be disturbed by, a navigation stack.
set -eo pipefail  # no -u: the ROS setup scripts reference unset vars

WORLD=$1
BRIDGE=$2
LABEL=$3
SECONDS_TO_RUN=${4:-20}

cd /mnt/d/rob-memory
source wsl/hz_sim_env.bash >/dev/null 2>&1
source /home/aphelios/hz_sim_ws/install/setup.bash >/dev/null 2>&1
export IGN_PARTITION=hz_sim_aphelios_73_prof
export ROS_DOMAIN_ID=73
export ROS_LOCALHOST_ONLY=1
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

LOG_DIR=/tmp/hz_profile
mkdir -p "$LOG_DIR"
rm -f "$LOG_DIR"/*.log "$LOG_DIR"/*.pid

cleanup() {
  for pidfile in "$LOG_DIR"/*.pid; do
    [ -e "$pidfile" ] || continue
    pid=$(cat "$pidfile")
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  done
  sleep 2
  for pidfile in "$LOG_DIR"/*.pid; do
    [ -e "$pidfile" ] || continue
    pid=$(cat "$pidfile")
    kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT

if [[ "$WORLD" != /* ]]; then WORLD="/mnt/d/rob-memory/$WORLD"; fi
GUI_FLAG="-s"
if [[ "${GUI:-0}" == "1" ]]; then GUI_FLAG=""; fi
setsid nohup ign gazebo $GUI_FLAG -r -v 2 --iterations 0 "$WORLD" \
  >"$LOG_DIR/server.log" 2>&1 &
echo $! >"$LOG_DIR/server.pid"

for _ in $(seq 1 60); do
  if ros2 topic list --no-daemon 2>/dev/null | grep -qx '/clock'; then break; fi
  sleep 1
done

setsid nohup ros2 run ros_gz_bridge parameter_bridge --ros-args \
  -p config_file:="$BRIDGE" -p use_sim_time:=true \
  >"$LOG_DIR/bridge.log" 2>&1 &
echo $! >"$LOG_DIR/bridge.pid"

sleep 6
echo '[profile] visible topics:' $(ros2 topic list --no-daemon 2>/dev/null | wc -l)
python3 -B sim/experiments/lab_nav/probe_rates.py --profile "${PROFILE:-lean}" --seconds "$SECONDS_TO_RUN" --label "$LABEL" --out "/mnt/d/rob-memory/outputs/lab_nav_20261105/profile_$LABEL.json" \
  --label "$LABEL" --out "/mnt/d/rob-memory/outputs/lab_nav_20261105/profile_$LABEL.json"

echo "[profile] $LABEL done"

