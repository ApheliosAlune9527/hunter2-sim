#!/usr/bin/env bash
set -eo pipefail
if [[ $# -gt 1 ]] || [[ $# -eq 1 && "$1" != '--check' ]]; then
  printf '错误：此直行测试不接受额外速度、话题或启动参数。\n' >&2
  exit 1
fi
source /mnt/d/rob-memory/wsl/hz_sim_env.bash
set -u
# Desktop adaptation: the *_d.sha256 copies hold the baseline digests with
# /mnt/d paths; the originals keep their 2026-10-21 bytes as evidence.
sha256sum --quiet --check /mnt/d/rob-memory/sim/scenes/hz_hunter_control_d.sha256
sha256sum --quiet --check /mnt/d/rob-memory/sim/tools/straight_trial_d.sha256
python3 -B /mnt/d/rob-memory/sim/tools/check_control_scene.py
if [[ "${1:-}" == '--check' ]]; then
  exec python3 -B /mnt/d/rob-memory/sim/tools/straight_trial.py --check
fi
printf '注意：将让Gazebo虚拟车以0.10m/s目标直行2个仿真秒，再以零目标收尾1秒并暂停。\n'
printf '仅作用于个人Gazebo；不点击播放，不接入ROS桥接或实车驱动。\n'
exec python3 -B /mnt/d/rob-memory/sim/tools/straight_trial.py
