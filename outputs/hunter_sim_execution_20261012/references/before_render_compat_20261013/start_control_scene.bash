#!/usr/bin/env bash
set -eo pipefail

if [[ $# -gt 1 ]] || [[ $# -eq 1 && "$1" != '--check' ]]; then
  printf '错误：此控制场景入口不接受额外的仿真启动参数。\n' >&2
  exit 1
fi

source /mnt/f/rob-memory/wsl/hz_sim_env.bash
set -u
# Resolve the installed systems instead of inherited custom plugin directories.
unset IGN_GAZEBO_SYSTEM_PLUGIN_PATH IGN_GAZEBO_RESOURCE_PATH IGN_GAZEBO_SERVER_CONFIG_PATH
scene_dir=/mnt/f/rob-memory/sim/scenes
sha256sum --quiet --check "$scene_dir/hz_hunter_control.sha256"
python3 -B /mnt/f/rob-memory/sim/tools/check_control_scene.py

if [[ "${1:-}" == '--check' ]]; then
  printf '控制场景文件检查通过；未启动 ROS 节点或 Gazebo，未发送速度。\n'
  exit 0
fi

python3 -B /mnt/f/rob-memory/sim/tools/check_ros_isolation.py
printf '正在打开个人 Gazebo 控制场景，初始状态为暂停。\n'
printf '只加载虚拟后轮驱动与前轮转向；本入口不发送速度，未接入 ROS 桥接或实车驱动。\n'
# No run flag, argument forwarding, publisher, bridge or hardware executable.
exec /usr/bin/ign gazebo -v 3 \
  --gui-config "$scene_dir/hz_hunter_preview_gui.config" \
  "$scene_dir/hz_hunter_control.sdf"
