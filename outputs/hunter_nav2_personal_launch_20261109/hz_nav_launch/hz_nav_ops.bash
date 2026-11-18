#!/usr/bin/env bash
# Operator checks and the same foreground ROS action clients as the runbook.

_hz_nav_session() {
    local lock=/home/car/hz_nav_ws/logs/.hz_nav_nav2.lock token
    [[ -f "$lock" && ! -L "$lock" && -O "$lock" ]] || return 1
    if flock -s -n -E 42 -- "$lock" true; then
        return 1
    else
        [[ $? == 42 ]] || return 1
    fi
    IFS= read -r token < "$lock" || return 1
    [[ $token =~ ^[a-f0-9]{32}$ ]] || return 1
    printf '%s\n' "$token"
}

_hz_nav_lifecycle() {
    local timeout_s=$1 group=$2 command=$3 reply rc=0
    reply=$(timeout "$timeout_s" ros2 service call "/hz_nav/lifecycle_manager_$group/manage_nodes" \
        nav2_msgs/srv/ManageLifecycleNodes "{command: $command}") || rc=$?
    printf '%s\n' "$reply"
    if [[ $rc != 0 || $reply != *'success=True'* ]]; then
        printf '%s 管理组未返回 success=True，请保留当前窗口输出。\n' "$group" >&2
        return 1
    fi
}

_hz_nav_status() {
    local reply
    reply=$(timeout 8s ros2 topic echo /hz_nav/hunter_status hunter_msgs/msg/HunterStatus --once) || return 1
    printf '%s\n' "$reply" | grep -E '^(linear_velocity|steering_angle|vehicle_state|control_mode|error_code):'
}

_hz_nav_plan_pose() {
    python3 -B - "$@" <<'PY'
import math
import sys

try:
    x, y, qz, qw = (float(value) for value in sys.argv[1:])
    if not all(math.isfinite(value) for value in (x, y, qz, qw)):
        raise ValueError
except ValueError:
    sys.exit('请给出本次选点的 X、Y 和 AMCL 的 QZ、QW 四个有限数字。')
if abs(math.hypot(qz, qw) - 1.0) > 0.001:
    sys.exit('QZ、QW 不构成有效的二维朝向，请核对 AMCL 回执。')
print(f'{{header: {{frame_id: map}}, pose: {{position: {{x: {x}, y: {y}, z: 0.0}}, '
      f'orientation: {{z: {qz}, w: {qw}}}}}}}')
PY
}

hz_nav() {
    if [[ ${HZ_NAV_PROFILE:-} != check || ${ROS_DOMAIN_ID:-} != 88 ||
          ${RMW_IMPLEMENTATION:-} != rmw_fastrtps_cpp || ${ROS_LOCALHOST_ONLY:-} != 0 ||
          -v FASTRTPS_DEFAULT_PROFILES_FILE ]]; then
        printf '请先在检查终端加载本版 check 环境。\n' >&2
        return 1
    fi
    local role=${1:-help}
    if (( $# > 0 )); then shift; fi
    local root=/home/car/hz_nav_ws session pose reply rc=0
    case "$role" in
        loc-on|ready|plan|goal|nav-off|loc-off|snapshot)
            session=$(_hz_nav_session) || {
                printf '未发现本版运行中的个人 Nav2 窗口，停止本次操作。\n' >&2
                return 1
            }
            ;;
    esac
    case "$role" in
        scan)
            timeout 15s ros2 topic echo /hz_nav/scan sensor_msgs/msg/LaserScan \
                --qos-reliability best_effort --qos-durability volatile --once --field header ;;
        odom)
            timeout 8s ros2 topic echo /hz_nav/odom nav_msgs/msg/Odometry \
                --qos-reliability best_effort --qos-durability volatile --once ;;
        loc-on) _hz_nav_lifecycle 30s localization 0 ;;
        tf) timeout 6s ros2 run tf2_ros tf2_echo map base_link ;;
        ready)
            timeout 10s ros2 service call /hz_nav/request_nomotion_update std_srvs/srv/Empty '{}' &&
                _hz_nav_lifecycle 60s navigation 0 ;;
        pose)
            timeout 10s ros2 topic echo /hz_nav/amcl_pose geometry_msgs/msg/PoseWithCovarianceStamped \
                --qos-durability transient_local --qos-reliability reliable --once --field pose.pose ;;
        pick)
            timeout 60s ros2 topic echo /clicked_point geometry_msgs/msg/PointStamped --once ;;
        status) _hz_nav_status ;;
        plan)
            unset _HZ_NAV_PLANNED_POSE _HZ_NAV_PLANNED_SESSION
            pose=$(_hz_nav_plan_pose "$@") || return 2
            printf '只计算路径，等待规划结果。\n'
            reply=$(timeout 30s ros2 action send_goal /hz_nav/compute_path_to_pose \
                nav2_msgs/action/ComputePathToPose "{goal: $pose, planner_id: GridBased, use_start: false}") || rc=$?
            printf '%s\n' "$reply"
            if [[ $rc != 0 ]] || ! grep -qx 'Goal finished with status: SUCCEEDED' <<< "$reply"; then
                printf '规划未成功，未保存可发送目标。\n' >&2
                return 1
            fi
            _HZ_NAV_PLANNED_POSE=$pose
            _HZ_NAV_PLANNED_SESSION=$session
            printf '已在本检查终端记住该目标。请在 RViz 核对绿线和现场净空。\n'
            ;;
        goal)
            if (( $# != 0 )) || [[ ${_HZ_NAV_PLANNED_SESSION:-} != "$session" || -z ${_HZ_NAV_PLANNED_POSE:-} ]]; then
                printf '请在同一个检查终端重新执行 hz_nav plan，并等规划成功。\n' >&2
                return 1
            fi
            printf '发送会让实车行驶，遇阻可能倒车。\n本次目标 %s\n' "$_HZ_NAV_PLANNED_POSE"
            if [[ ! -t 0 ]]; then
                printf '请由现场操作人员在前台终端确认。\n' >&2
                return 1
            fi
            local confirmation feedback goal_lock="$root/logs/.hz_nav_goal.lock"
            read -r -p '确认同一路线、前后净空、有人可接管且同意本次行驶后，输入 SEND GOAL：' confirmation || return 1
            [[ "$confirmation" == 'SEND GOAL' ]] || return 1
            feedback=$(_hz_nav_status) || return 1
            printf '%s\n' "$feedback"
            if ! awk -F':[[:space:]]*' '
                $1 == "linear_velocity" {
                    valid = ($2 ~ /^[-+]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][-+]?[0-9]+)?$/)
                    still = valid && $2 + 0 >= -0.01 && $2 + 0 <= 0.01
                }
                $1 == "vehicle_state" { healthy = ($2 == "0") }
                $1 == "error_code" { no_error = ($2 == "0") }
                $1 == "control_mode" { can_mode = ($2 == "1") }
                END { exit !(still && healthy && no_error && can_mode) }
            ' <<< "$feedback"; then
                printf '底盘需静止（|v|≤0.01 m/s）、CAN 模式 1、状态和故障码均为 0。\n' >&2
                return 1
            fi
            if [[ $(_hz_nav_session) != "$session" ]]; then
                printf 'Nav2 会话已变化，请重新规划。\n' >&2
                return 1
            fi
            if [[ -L "$goal_lock" || ( -e "$goal_lock" && ( ! -f "$goal_lock" || ! -O "$goal_lock" ) ) ]]; then
                printf '目标锁路径异常 %s\n' "$goal_lock" >&2
                return 1
            fi
            pose=$_HZ_NAV_PLANNED_POSE
            unset _HZ_NAV_PLANNED_POSE _HZ_NAV_PLANNED_SESSION
            flock -n -F -E 42 -- "$goal_lock" \
                ros2 action send_goal /hz_nav/navigate_to_pose nav2_msgs/action/NavigateToPose \
                "{pose: $pose, behavior_tree: '$root/config/navigate_no_spin.xml'}" --feedback
            rc=$?
            if [[ $rc == 42 ]]; then
                printf '另一个本版目标客户端仍在运行。请核对原窗口。\n' >&2
            fi
            return "$rc"
            ;;
        snapshot)
            local snapshot
            snapshot=$(mktemp -d "$root/logs/nav2_snapshot_$(date +%Y%m%d_%H%M%S)_XXXXXXXX") || return 1
            if cp -a -- "$root/config" "$root/launch" "$root/maps" "$root/rviz" "$snapshot/" &&
                timeout 20s ros2 param dump /hz_nav/controller_server --no-daemon --spin-time 3 \
                    > "$snapshot/controller_runtime.yaml"; then
                printf '本次快照 %s\n' "$snapshot"
            else
                printf '快照未完成，已保存的内容保留在 %s\n' "$snapshot" >&2
                return 1
            fi
            ;;
        nav-off)
            unset _HZ_NAV_PLANNED_POSE _HZ_NAV_PLANNED_SESSION
            _hz_nav_lifecycle 60s navigation 4 ;;
        loc-off) _hz_nav_lifecycle 30s localization 4 ;;
        *) printf '用法 hz_nav scan|odom|loc-on|tf|ready|pose|pick|status|plan X Y QZ QW|goal|snapshot|nav-off|loc-off\n' ;;
    esac
}
