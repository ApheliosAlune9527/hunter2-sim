#!/usr/bin/env bash
# Determine which rendering mode produces a usable gpu_lidar scan.
# usage: test_scan_render.bash {server|headless|gui}
set -o pipefail

MODE="${1:-server}"
ROOT=/mnt/d/rob-memory
WORLD="$ROOT/outputs/lab_nav_20261105/lab_nav_world_drive.sdf"
BRIDGE="$ROOT/sim/config/lab_nav_bridge.yaml"
OUT=/tmp/lab_scan_test
mkdir -p "$OUT"
LOG="$OUT/scan_$MODE.log"
: > "$LOG"

# shellcheck disable=SC1091
source "$ROOT/wsl/hz_sim_env.bash" >/dev/null 2>&1
# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash >/dev/null 2>&1
# shellcheck disable=SC1091
source /home/aphelios/hz_sim_ws/install/setup.bash >/dev/null 2>&1

case "$MODE" in
  server)   GZ_ARGS=(-s -r -v 3) ;;
  headless) GZ_ARGS=(-s -r -v 3 --headless-rendering) ;;
  gui)      GZ_ARGS=(-r -v 3) ;;
  *) echo "unknown mode $MODE" >&2; exit 2 ;;
esac

pkill -f "[i]gn gazebo" 2>/dev/null
pkill -f "[l]ab_nav_bridge" 2>/dev/null
sleep 3

setsid nohup ign gazebo "${GZ_ARGS[@]}" "$WORLD" > "$OUT/gz_$MODE.log" 2>&1 < /dev/null &
sleep 30

setsid nohup ros2 run ros_gz_bridge parameter_bridge \
  --ros-args -p "config_file:=$BRIDGE" -p use_sim_time:=true \
  > "$OUT/bridge_$MODE.log" 2>&1 < /dev/null &
sleep 10

echo "[scan-test] gz header fields:"
timeout 12 ign topic -e -t "${NS:-}/hz_sim/lab/scan" -n 1 2>/dev/null \
  | grep -E "^(angle_min|angle_max|range_min|range_max|count|ranges)" | head -8

python3 -B - "$MODE" <<'PY' 2>&1 | tee -a "$LOG"
import math, sys, time
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

mode = sys.argv[1]
rclpy.init()
node = Node("scan_probe", parameter_overrides=[rclpy.parameter.Parameter(
    "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
box = {}


def cb(msg):
    vals = [v for v in msg.ranges if math.isfinite(v)]
    if vals and "s" not in box:
        box["s"] = (len(vals), round(min(vals), 3), round(sum(vals) / len(vals), 2),
                    round(max(vals), 2))
        box["hdr"] = (round(msg.range_min, 3), round(msg.range_max, 3),
                      [round(v, 3) for v in msg.ranges[:3]])


node.create_subscription(LaserScan, "/hz_sim/lab/scan", cb, 5)
deadline = time.time() + 25
while time.time() < deadline and "s" not in box:
    rclpy.spin_once(node, timeout_sec=0.2)
print(f"RESULT mode={mode} scan={box.get('s')} ros_hdr={box.get('hdr')}")
node.destroy_node()
rclpy.shutdown()
PY

pkill -f "[l]ab_nav_bridge" 2>/dev/null
pkill -f "[i]gn gazebo" 2>/dev/null
sleep 2
echo "[scan-test] done mode=$MODE"
