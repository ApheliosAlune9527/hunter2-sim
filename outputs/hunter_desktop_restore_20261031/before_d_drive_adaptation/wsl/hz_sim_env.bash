# Source this file from the personal WSL terminal. It starts no processes.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  printf '请用 source /mnt/f/rob-memory/wsl/hz_sim_env.bash 加载此文件。\n' >&2
  exit 1
fi

# Catch accidental use on the shared robot or a different Linux environment.
if [[ "${WSL_DISTRO_NAME:-}" != 'Ubuntu-22.04' || "${USER:-}" != 'aphelios' ]]; then
  printf '错误：仅允许在个人 WSL Ubuntu-22.04 的 aphelios 终端加载。\n' >&2
  return 1
fi
if [[ ! -r /proc/sys/kernel/osrelease ]] ||
   [[ "$(< /proc/sys/kernel/osrelease)" != *[Mm]icrosoft* ]]; then
  printf '错误：未确认当前系统为 WSL；未加载仿真环境。\n' >&2
  return 1
fi

source /opt/ros/humble/setup.bash || return 1

# Humble's Cyclone RMW selects loopback when ROS_LOCALHOST_ONLY is enabled.
# Clear inherited custom DDS configuration, which could override that choice.
unset CYCLONEDDS_URI
export ROS_DOMAIN_ID=73
export ROS_LOCALHOST_ONLY=1
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA

# Separate Gazebo Transport traffic logically; this is not a network sandbox.
unset IGN_RELAY
export IGN_PARTITION=hz_sim_aphelios_73
export IGN_IP=127.0.0.1

printf '已加载个人仿真环境：Humble / ROS 域 73 / 本机通信 / NVIDIA。\n'
