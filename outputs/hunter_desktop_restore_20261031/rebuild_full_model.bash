#!/usr/bin/env bash
set -eo pipefail

if [[ "${WSL_DISTRO_NAME:-}" != 'Ubuntu-22.04' || "$(id -un)" != 'aphelios' ]]; then
  printf 'Only the recovered personal Ubuntu-22.04/aphelios workspace is allowed.\n' >&2
  exit 1
fi
if [[ "$(< /proc/sys/kernel/osrelease)" != *[Mm]icrosoft* ]]; then
  printf 'This build is restricted to the personal WSL environment.\n' >&2
  exit 1
fi

root=/mnt/d/rob-memory
workspace=/home/aphelios/hz_sim_ws
report="$root/outputs/hunter_desktop_restore_20261031"
exec 9>"$workspace/.desktop-full-model-build.lock"
flock -n 9 || { printf 'Another full-model build is in progress.\n' >&2; exit 1; }
source /opt/ros/humble/setup.bash
python3 -B "$report/prepare_native_model.py"
cd "$workspace"
colcon --log-base "$report/colcon_logs" build \
  --base-paths src/hz_hunter_full_description \
  --packages-select hz_hunter_full_description \
  --event-handlers console_direct+
printf 'Full model data package built. No simulator or ROS node was started.\n'
