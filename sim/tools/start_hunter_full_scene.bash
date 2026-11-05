#!/usr/bin/env bash
set -eo pipefail

if [[ $# -gt 1 ]] || [[ $# -eq 1 && "$1" != '--check' ]]; then
  printf '错误：完整模型入口只接受无参数或 --check。\n' >&2
  exit 1
fi

source /mnt/d/rob-memory/wsl/hz_sim_env.bash
source /home/aphelios/hz_sim_ws/install/setup.bash
set -u
unset IGN_GAZEBO_SYSTEM_PLUGIN_PATH IGN_GAZEBO_RESOURCE_PATH IGN_GAZEBO_SERVER_CONFIG_PATH
export PYTHONIOENCODING=utf-8
if [[ "${1:-}" == '--check' ]]; then
  exec python3 -B /mnt/d/rob-memory/sim/tools/check_full_entry.py
fi

python3 -B /mnt/d/rob-memory/sim/tools/check_full_entry.py >/dev/null
python3 -B /mnt/d/rob-memory/sim/tools/check_ros_isolation.py
exec python3 -B /mnt/d/rob-memory/sim/tools/full_scene_session.py
