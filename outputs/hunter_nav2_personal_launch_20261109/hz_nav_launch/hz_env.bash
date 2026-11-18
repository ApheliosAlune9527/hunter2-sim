#!/usr/bin/env bash
# Load only the overlay used by this terminal in the proven runbook.
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
    printf '请在小车新终端使用 source %s check\n' "$0" >&2
    exit 1
fi

_hz_nav_load_environment() {
    local profile=${1:-check} root=/home/car/hz_nav_ws overlay=
    if [[ $(id -un) != car || $(hostname -s | tr '[:upper:]' '[:lower:]') != car-nuc15jnku7x4 ]]; then
        printf '请在小车 car@car-NUC15JNKU7X4 的 Ubuntu 终端加载环境。\n' >&2
        return 1
    fi
    if [[ -n ${HZ_NAV_PROFILE:-} && $HZ_NAV_PROFILE != "$profile" ]]; then
        printf '此终端已加载 %s，请为 %s 新开终端。\n' "$HZ_NAV_PROFILE" "$profile" >&2
        return 1
    fi
    unset hzLaunch HZ_NAV_PROFILE
    case "$profile" in
        sensors) overlay=/home/car/hesai_xt32_ws/install/setup.bash ;;
        base|rviz|check) overlay=/home/car/hunter_nav_odom_ws/install/setup.bash ;;
        nav2) ;;
        *) printf '环境角色应为 sensors、base、nav2、rviz 或 check。\n' >&2; return 1 ;;
    esac
    if [[ $(realpath -e -- "$root" 2>/dev/null) != "$root" || ! -O "$root" ||
          $(realpath -e -- "${BASH_SOURCE[0]}" 2>/dev/null) != "$root/hz_nav_launch/hz_env.bash" ||
          ! -r "$root/hz_nav_launch/hz_nav.launch.py" ]]; then
        printf '请先将本版个人入口安装到 %s/hz_nav_launch。\n' "$root" >&2
        return 1
    fi
    local directory
    for directory in "$root/.ros" "$root/logs"; do
        if [[ -L "$directory" ]] || ! mkdir -p -- "$directory" || [[ ! -d "$directory" || ! -O "$directory" || ! -w "$directory" ]]; then
            printf '个人目录不可用 %s\n' "$directory" >&2
            return 1
        fi
    done

    source /opt/ros/humble/setup.bash || return 1
    export ROS_DOMAIN_ID=88 RMW_IMPLEMENTATION=rmw_fastrtps_cpp ROS_LOCALHOST_ONLY=0
    export ROS_HOME="$root/.ros" ROS_LOG_DIR="$root/logs" TMPDIR="$root/logs" PYTHONDONTWRITEBYTECODE=1
    if [[ -n "$overlay" ]]; then
        if [[ ! -r "$overlay" ]] || ! source "$overlay"; then
            printf '工作空间环境加载失败 %s\n' "$overlay" >&2
            return 1
        fi
    fi
    unset FASTRTPS_DEFAULT_PROFILES_FILE
    if [[ ${ROS_DISTRO:-} != humble || $ROS_DOMAIN_ID != 88 ||
          $RMW_IMPLEMENTATION != rmw_fastrtps_cpp || $ROS_LOCALHOST_ONLY != 0 ]]; then
        printf '加载后通信环境与 Humble、域 88、Fast DDS 不一致。\n' >&2
        return 1
    fi
    if [[ "$profile" == check ]]; then
        source "$root/hz_nav_launch/hz_nav_ops.bash" || return 1
    fi
    export HZ_NAV_PROFILE="$profile"
    hzLaunch="$root/hz_nav_launch/hz_nav.launch.py"
}

if _hz_nav_load_environment "$@"; then
    unset -f _hz_nav_load_environment
    return 0
else
    unset -f _hz_nav_load_environment
    return 1
fi
