# Source this file in each robot terminal; do not execute it as a script.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    printf '%s\n' '请用 source /home/car/hz_ws/hz_mapping_tools/hz_env.sh' >&2
    exit 1
fi

_hz_mapping_setup() {
    local hzToolsDir=/home/car/hz_ws/hz_mapping_tools
    local hzSetupFile
    export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
    python3 -B "$hzToolsDir/hz_diagnose.py" --env-only || return 1
    for hzSetupFile in /opt/ros/humble/setup.bash /home/car/d435i_ws/install/local_setup.bash /home/car/hz_ws/install/local_setup.bash; do
        if [[ ! -r "$hzSetupFile" ]]; then
            printf '缺少环境文件：%s\n' "$hzSetupFile" >&2
            return 1
        fi
        source "$hzSetupFile" || return 1
    done
    export ROS_DOMAIN_ID=88 RMW_IMPLEMENTATION=rmw_fastrtps_cpp ROS_LOCALHOST_ONLY=0
    export ROS_HOME=/home/car/hz_ws/.ros ROS_LOG_DIR=/home/car/hz_ws/logs/ros
    export RCUTILS_LOGGING_BUFFERED_STREAM=0 OVERRIDE_LAUNCH_PROCESS_OUTPUT=screen
    export hzLaunch="$hzToolsDir/hz_mapping.launch.py"
}

if _hz_mapping_setup; then
    unset -f _hz_mapping_setup
else
    unset -f _hz_mapping_setup
    return 1
fi
