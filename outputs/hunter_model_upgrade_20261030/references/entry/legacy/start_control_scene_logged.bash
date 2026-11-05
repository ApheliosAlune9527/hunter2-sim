#!/usr/bin/env bash
set -eo pipefail

if [[ $# -gt 1 ]] || [[ $# -eq 1 && "$1" != '--check' ]]; then
  printf '错误：日志入口只接受无参数或 --check。\n' >&2
  exit 1
fi

control_entry=/mnt/f/rob-memory/sim/tools/start_control_scene.bash
if [[ "${1:-}" == '--check' ]]; then
  exec /bin/bash "$control_entry" --check
fi

# Validate the personal WSL environment before creating a log or launching.
source /mnt/f/rob-memory/wsl/hz_sim_env.bash
set -u
log_dir=/mnt/f/rob-memory/outputs/hunter_sim_execution_20261012/references/user_logs
if [[ ! -d "$log_dir" ]]; then
  printf '错误：个人日志目录不存在；未启动场景。\n' >&2
  exit 1
fi
log_file=$(mktemp "$log_dir/gazebo_graphics_utf8_XXXXXX.log")
printf '启动日志（UTF-8）：%s\n' "$log_file"

# Logging only: use the same paused scene and graphics settings as the
# user's no-flicker diagnostic run. No velocity or stepping operation.
# Merge Linux streams here so WSL host warnings stay outside this log.
QSG_INFO=1 QT_LOGGING_RULES=qt.qpa.gl=true LIBGL_DEBUG=verbose \
  /bin/bash "$control_entry" 2>&1 | /usr/bin/tee "$log_file"
