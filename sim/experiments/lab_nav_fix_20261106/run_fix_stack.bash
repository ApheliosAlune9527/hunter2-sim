#!/usr/bin/env bash
# Bring up the corrected lab navigation stack.
#
# Differences from sim/experiments/lab_nav/run_lab_stack.bash:
#   * every path points into this directory, so the parameters, bridge and launch
#     that run are the ones this round edited;
#   * each started process is written to a registry with its kernel start time and
#     command line, which is what stop_fix_stack.bash uses to kill only these
#     processes -- there is no pkill-by-name fallback anywhere;
#   * the scene hash and the ROS identity are recorded before anything moves, so a
#     later reader can tell which world produced a log.
#
# This script only moves the simulated vehicle inside Gazebo on ROS domain 73 with
# ROS_LOCALHOST_ONLY=1.  It never touches the real vehicle on domain 88.
set -o pipefail

HERE=/mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106
LOG_DIR=${LOG_DIR:-/tmp/lab_fix_stack}
WORLD=${WORLD:-/mnt/d/rob-memory/outputs/lab_nav_20261105/lab_nav_world_drive.sdf}
BRIDGE=${BRIDGE:-$HERE/lab_bridge_fix.yaml}
DEADLINE_WAS_SET=${DEADLINE:+1}
DEADLINE=${DEADLINE:-240}
LOCALIZER=${LOCALIZER:-truth}
NAV2=${NAV2:-1}
# GUI=1 opens the Gazebo window; STAGE=sim stops after the scene and the bridge, which
# is the first step of the walkthrough (see README).  Headless stays the default.
GUI=${GUI:-0}
STAGE=${STAGE:-stack}

source "$HERE/lab_nav_fix_env.bash" || {
  echo "[stack] FATAL: the lab navigation environment did not load" >&2
  exit 1
}
# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash || {
  echo "[stack] FATAL: could not source /opt/ros/humble/setup.bash" >&2
  exit 1
}
# shellcheck disable=SC1091
source /home/aphelios/hz_sim_ws/install/setup.bash || {
  echo "[stack] FATAL: could not source /home/aphelios/hz_sim_ws/install/setup.bash" >&2
  exit 1
}
command -v ign >/dev/null 2>&1 || { echo "[stack] FATAL: ign not on PATH" >&2; exit 1; }
command -v ros2 >/dev/null 2>&1 || { echo "[stack] FATAL: ros2 not on PATH" >&2; exit 1; }
[ -r "$WORLD" ] || { echo "[stack] FATAL: world file missing: $WORLD" >&2; exit 1; }
[ -r "$BRIDGE" ] || { echo "[stack] FATAL: bridge config missing: $BRIDGE" >&2; exit 1; }

# A start that fails halfway must not leave half a stack behind: stop only the
# processes this script registered, then exit non-zero.
fail_start() {
  echo "[stack] FATAL: $*" >&2
  echo "[stack] cleaning up only the processes registered in $LOG_DIR" >&2
  LOG_DIR="$LOG_DIR" bash "$HERE/stop_fix_stack.bash" || \
    echo "[stack] WARNING: cleanup reported leftovers; the registry is $LOG_DIR/processes.tsv" >&2
  exit 1
}

mkdir -p "$LOG_DIR"
# A second stack started into the same directory used to overwrite the registry and
# leave the first one's bridge running unseen -- two publishers on /scan, 20 Hz of
# duplicate messages.  Refuse to start while any recorded process is still alive.
if [ -f "$LOG_DIR/processes.tsv" ]; then
  live=""
  while IFS=$'\t' read -r name pid start_time _; do
    [ -r "/proc/$pid/stat" ] || continue
    now_start=$(awk '{print $22}' "/proc/$pid/stat" 2>/dev/null || true)
    [ "$now_start" = "$start_time" ] && live="$live $name($pid)"
  done < "$LOG_DIR/processes.tsv"
  if [ -n "$live" ]; then
    echo "[stack] refusing to start: these recorded processes are still alive:$live" >&2
    echo "[stack] stop them first:  bash $HERE/stop_fix_stack.bash" >&2
    exit 3
  fi
fi
rm -f "$LOG_DIR"/*.pid "$LOG_DIR"/*.log "$LOG_DIR/processes.tsv"

WORLD_SHA=$(sha256sum "$WORLD" | awk '{print $1}')
BRIDGE_SHA=$(sha256sum "$BRIDGE" | awk '{print $1}')
{
  echo "started=$(date -Is)"
  echo "user=$(whoami)"
  echo "ros_domain_id=$ROS_DOMAIN_ID"
  echo "ros_localhost_only=$ROS_LOCALHOST_ONLY"
  echo "rmw=$RMW_IMPLEMENTATION"
  echo "ign_partition=$IGN_PARTITION"
  echo "world=$WORLD"
  echo "world_sha256=$WORLD_SHA"
  echo "bridge=$BRIDGE"
  echo "bridge_sha256=$BRIDGE_SHA"
  echo "localizer=$LOCALIZER"
} > "$LOG_DIR/session.txt"

read_start_time() { awk '{print $22}' "/proc/$1/stat" 2>/dev/null; }

# Start a command in its own session, record its identity, and never guess later.
start() {
  local name=$1; shift
  setsid nohup "$@" > "$LOG_DIR/$name.log" 2>&1 &
  local pid=$!
  sleep 0.3
  local st
  st=$(read_start_time "$pid")
  printf '%s\t%s\t%s\t%s\n' "$name" "$pid" "$st" "$*" >> "$LOG_DIR/processes.tsv"
  echo "$pid" > "$LOG_DIR/$name.pid"
  echo "[stack] $name pid=$pid start=$st"
}

wait_for_topic() {
  local topic=$1 limit=$2 i=0
  while [ $i -lt "$limit" ]; do
    if ign topic -l 2>/dev/null | grep -qx "$topic"; then return 0; fi
    sleep 1
    i=$((i + 1))
  done
  return 1
}

echo "[stack] world sha256=$WORLD_SHA"
if [ "$GUI" = 1 ]; then
  echo "[stack] gui=on"
  # No custom GUI layout: the one derived from the old scene opened this window half
  # off-screen.  The default layout opens correctly, and moving the camera with the
  # mouse is part of the walkthrough anyway.
  start server ign gazebo -r -v 3 "$WORLD"
else
  # --headless-rendering matters: without it the server still builds a rendering
  # context, and on this machine the physics then advances at a fraction of real time
  # (measured about 0.05x) while the clock keeps ticking, so the vehicle looks frozen.
  start server ign gazebo -s -r -v 3 --headless-rendering "$WORLD"
fi
if ! wait_for_topic /clock 60; then
  fail_start "/clock never appeared"
fi

start bridge ros2 run ros_gz_bridge parameter_bridge \
  --ros-args -p config_file:="$BRIDGE" -p use_sim_time:=true
sleep 3

if [ "$STAGE" = sim ]; then
  echo "[stack] scene and bridge ready (stage=sim)"
  exit 0
fi

if [ "$LOCALIZER" = amcl ]; then
  start odom_tf python3 -B "$HERE/odom_tf.py" --ros-args -p use_sim_time:=true
  if [ "$NAV2" = 1 ]; then export WITH_MAP=0; fi
else
  start truth python3 -B "$HERE/truth_localisation.py" --ros-args -p use_sim_time:=true
fi
sleep 3

# In manual mode the operator, not this script, supplies the starting pose, and that
# happens only after RViz is up.  Give them a generous window and say so before the
# long wait starts, so a terminal that looks stuck is not mistaken for a broken start.
if [ "$LOCALIZER" = amcl ] && [ "${INIT_POSE:-auto}" = manual ]; then
  [ -n "$DEADLINE_WAS_SET" ] || DEADLINE=600
  echo "[stack] AMCL has no starting pose yet.  When RViz appears, use 2D Pose Estimate:"
  echo "[stack] click at (-0.21, -0.77) and drag towards +x.  Waiting up to ${DEADLINE}s."
fi

if [ "$NAV2" != 1 ]; then
  echo "[stack] localisation-only mode ready"
  exit 0
fi

start nav2 ros2 launch "$HERE/run_nav2_fix.launch.py"

if [ "$GUI" = 1 ]; then
  # RViz is a window onto the same topics the controller uses; it publishes nothing.
  start rviz rviz2 -d "$HERE/rviz_fix.rviz"
fi

if [ "$LOCALIZER" = amcl ]; then
  # AMCL publishes nothing on map->odom until it has been given a starting pose.  It can
  # be seeded here (default) or left to the operator with INIT_POSE=manual, which is what
  # the tutorial uses: setting the pose is part of learning where the estimate comes from.
  if [ "${INIT_POSE:-auto}" = manual ]; then
    echo "[stack] AMCL is waiting for a starting pose (RViz: 2D Pose Estimate, or /initialpose)"
  else
    sleep 4
    python3 -B "$HERE/init_pose.py" > "$LOG_DIR/init_pose.log" 2>&1 || {
      cat "$LOG_DIR/init_pose.log" >&2
      fail_start "could not initialise AMCL"
    }
  fi
fi

i=0
while [ $i -lt "$DEADLINE" ]; do
  if grep -q "Managed nodes are active" "$LOG_DIR/nav2.log" 2>/dev/null; then
    echo "[stack] ready in ${i}s"
    exit 0
  fi
  sleep 2
  i=$((i + 2))
done
tail -20 "$LOG_DIR/nav2.log" >&2
fail_start "nav2 never became active"
