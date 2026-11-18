#!/usr/bin/env bash
# Stop exactly the processes started by run_lab_stack.bash, then sweep the
# leftovers.  The sweep matters: `ros2 launch` forks the nav2 nodes into their
# own sessions, so the pid recorded by the launcher does not own them and a
# second run would come up next to a stale map_server that still holds the node
# name (lifecycle transitions then fail with "Failed to change state").
set -uo pipefail
LOG_DIR=${LOG_DIR:-/tmp/lab_stack}

PATTERNS=(
  "[i]gn gazebo -s"
  "[p]arameter_bridge"
  "[t]ruth_localisation"
  "[o]dom_tf.py"
  "[r]un_nav2.launch.py"
  "[r]un_amcl.launch.py"
  "[/]nav2_map_server/map_server"
  "[/]nav2_amcl/amcl"
  "[/]nav2_planner/planner_server"
  "[/]nav2_controller/controller_server"
  "[/]nav2_behaviors/behavior_server"
  "[/]nav2_bt_navigator/bt_navigator"
  "[/]nav2_lifecycle_manager/lifecycle_manager"
  "[/]nav2_smoother/smoother_server"
  "[/]nav2_velocity_smoother/velocity_smoother"
  "[/]nav2_waypoint_follower/waypoint_follower"
)

for name in nav2 amcl truth odom_tf bridge server; do
  pidfile="$LOG_DIR/$name.pid"
  [ -f "$pidfile" ] || continue
  pid=$(cat "$pidfile")
  if kill -0 "$pid" 2>/dev/null; then
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
    echo "[stop] $name ($pid) signalled"
  fi
done
sleep 3

for pat in "${PATTERNS[@]}"; do
  pgrep -f "$pat" >/dev/null 2>&1 && pkill -TERM -f "$pat" 2>/dev/null
done
sleep 2
for pat in "${PATTERNS[@]}"; do
  pgrep -f "$pat" >/dev/null 2>&1 && pkill -KILL -f "$pat" 2>/dev/null
done
sleep 1

leftover=$(pgrep -fc "[i]gn gazebo -s|[p]arameter_bridge|[t]ruth_localisation|[/]nav2_"] || true)
echo "[stop] remaining stack processes: ${leftover:-0}"
