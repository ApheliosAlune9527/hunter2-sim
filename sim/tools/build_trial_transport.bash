#!/usr/bin/env bash
set -eo pipefail
source /mnt/d/rob-memory/wsl/hz_sim_env.bash
set -u
if [[ $# -ne 0 ]]; then exit 1; fi
mkdir -p /home/aphelios/hz_sim_ws/tools
g++ -O2 -Wall -Wextra /mnt/d/rob-memory/sim/tools/gz_trial_transport.cc \
  $(pkg-config --cflags --libs ignition-transport11 ignition-msgs8) \
  -o /home/aphelios/hz_sim_ws/tools/gz_trial_transport
# Writes the desktop copy only; straight_trial.sha256 keeps its baseline bytes.
sha256sum /home/aphelios/hz_sim_ws/tools/gz_trial_transport \
  /mnt/d/rob-memory/sim/tools/gz_trial_transport.cc \
  /mnt/d/rob-memory/sim/tools/straight_trial.py \
  > /mnt/d/rob-memory/sim/tools/straight_trial_d.sha256
printf '个人Gazebo传输工具已编译，未运行运动操作。\n'
