#!/usr/bin/env bash
# Source to define hznav, or pass a role directly to bash hznav.bash.
hznav() (
    set -o pipefail

    local role=${1:-help}
    if (( $# > 0 )); then
        shift
    fi

    fail() {
        printf 'hznav: %s\n' "$*" >&2
        return 1
    }

    case "$role" in
        help|-h|--help)
            cat <<'HELP'
用法  hznav 角色
check       检查小车主机、个人文件及 ROS 包来源
sensors     启动雷达、模型 TF 和二维扫描
scan        读取一帧二维扫描的 header
base        经现场确认后启动真实底盘
nav2        加载个人 Nav2 组件和地图
loc-on      启用地图和 AMCL 定位组
rviz        打开个人 RViz 配置
tf          检查 map 到 base_link 的变换
ready       原地更新 AMCL，随后启用导航组
pose        读取当前 AMCL 位姿
pick        等待 RViz 红图钉选点
plan X Y QZ QW   只计算路径
status      读取底盘速度、控制模式和故障状态
goal X Y QZ QW   经现场确认后发送真实导航目标
snapshot    保存个人配置和控制器运行参数
nav-off     关闭导航组
loc-off     关闭定位组
HELP
            return 0
            ;;
        plan|goal)
            if (( $# != 4 )); then
                fail "用法 hznav $role X Y QZ QW"
                return 2
            fi
            ;;
        check|sensors|scan|base|nav2|loc-on|rviz|tf|ready|pose|pick|status|snapshot|nav-off|loc-off)
            if (( $# != 0 )); then
                fail "$role 不需要额外参数"
                return 2
            fi
            ;;
        *)
            fail "未知角色 $role。用 hznav help 查看。"
            return 2
            ;;
    esac

    local -r workspace=/home/car/hz_nav_ws
    local -r logs="$workspace/logs"
    local -r robot_install=/home/car/hunter_nav_odom_ws/install
    local -r lidar_install=/home/car/hesai_xt32_ws/install
    local -r map_yaml="$workspace/maps/lab_odom_06_nav.yaml"
    local -r nav_params="$workspace/config/nav2_params.yaml"
    local -r tree="$workspace/config/navigate_no_spin.xml"
    local -r rviz_config="$workspace/rviz/lab_odom_06_map_view.rviz"

    if [[ $(id -un) != car || $(hostname -s) != car-NUC15JNKU7X4 ]]; then
        fail '请在 ToDesk 的 car@car-NUC15JNKU7X4 Ubuntu 终端使用。'
        return 1
    fi
    if [[ ! -d "$logs" || ! -w "$logs" ]]; then
        fail "找不到可写的个人日志目录 $logs"
        return 1
    fi

    require_files() {
        local file
        for file in "$@"; do
            if [[ ! -f "$file" || ! -r "$file" ]]; then
                fail "文件缺失或不可读 $file"
                return 1
            fi
        done
    }

    load_setup() {
        require_files "$1" || return 1
        source "$1" || fail "环境加载失败 $1"
    }

    require_package() {
        local package=$1 expected=$2 prefix
        prefix=$(ros2 pkg prefix "$package") || return 1
        case "$prefix" in
            "$expected"|"$expected"/*) printf '%s -> %s\n' "$package" "$prefix" ;;
            *) fail "$package 解析到 $prefix，期望位于 $expected" ;;
        esac
    }

    confirm_on_site() {
        local phrase=$1 description=$2 reply
        printf '%s\n' "$description" >&2
        if [[ ! -t 0 ]]; then
            fail '该操作需要现场人员在终端亲自确认。'
            return 1
        fi
        printf '确认现场可用遥控器或急停接管、车辆停稳、前后净空后，输入 %s 确认本次操作。直接回车取消。\n> ' "$phrase" >&2
        if ! IFS= read -r reply || [[ "$reply" != "$phrase" ]]; then
            fail '本次操作已取消。'
            return 1
        fi
    }

    load_setup /opt/ros/humble/setup.bash || return 1
    export ROS_DOMAIN_ID=88 RMW_IMPLEMENTATION=rmw_fastrtps_cpp ROS_LOCALHOST_ONLY=0 || return 1
    export ROS_HOME="$workspace/.ros" ROS_LOG_DIR="$logs" TMPDIR="$logs" PYTHONDONTWRITEBYTECODE=1 || return 1

    case "$role" in
        sensors) load_setup "$lidar_install/setup.bash" || return 1 ;;
        base|rviz|status|goal) load_setup "$robot_install/setup.bash" || return 1 ;;
    esac
    # This unset affects only this invocation, like env -u in the original TXT.
    unset FASTRTPS_DEFAULT_PROFILES_FILE || return 1

    lifecycle() {
        exec timeout "$1" ros2 service call "/hz_nav/lifecycle_manager_$2/manage_nodes" \
            nav2_msgs/srv/ManageLifecycleNodes "{command: $3}"
    }

    read_status() {
        timeout 8s ros2 topic echo /hz_nav/hunter_status hunter_msgs/msg/HunterStatus --once |
            grep -E '^(linear_velocity|steering_angle|vehicle_state|control_mode|error_code):'
    }

    local target_values goal_pose
    if [[ "$role" == plan || "$role" == goal ]]; then
        target_values=$(python3 -B - "$@" <<'PY'
import math
import sys

try:
    x, y, qz, qw = (float(arg) for arg in sys.argv[1:])
    if not all(math.isfinite(value) for value in (x, y, qz, qw)):
        raise ValueError
except ValueError:
    sys.exit("hznav: X、Y、QZ、QW 必须是有限数字。")
if abs(math.hypot(qz, qw) - 1.0) > 0.001:
    sys.exit("hznav: QZ、QW 不是有效的二维朝向，请核对 AMCL 回执。")
print(*(f"{value:.16e}" for value in (x, y, qz, qw)))
PY
        ) || return 2
        local x y qz qw
        read -r x y qz qw <<<"$target_values"
        goal_pose="{header: {frame_id: map}, pose: {position: {x: $x, y: $y, z: 0.0}, orientation: {z: $qz, w: $qw}}}"
    fi

    case "$role" in
        check)
            require_files \
                "$workspace/launch/01_sensors.launch.py" "$workspace/launch/bringup_launch.py" \
                "$workspace/launch/localization_launch.py" "$workspace/launch/navigation_launch.py" \
                "$workspace/config/hesai_xt32.yaml" "$workspace/config/hunter_nav.urdf" \
                "$map_yaml" "$workspace/maps/lab_odom_06.pgm" "$nav_params" "$tree" \
                "$workspace/config/navigate_through_poses_no_spin.xml" "$rviz_config" || return 1
            require_package nav2_bringup /opt/ros/humble || return 1
            (
                load_setup "$lidar_install/setup.bash" || return 1
                unset FASTRTPS_DEFAULT_PROFILES_FILE || return 1
                require_package hesai_ros_driver "$lidar_install"
            ) || return 1
            (
                load_setup "$robot_install/setup.bash" || return 1
                unset FASTRTPS_DEFAULT_PROFILES_FILE || return 1
                require_package hunter_base "$robot_install" || return 1
                ros2 interface show hunter_msgs/msg/HunterStatus >/dev/null
            ) || return 1
            printf '入口和包路径检查通过。\n地图 %s\n参数 %s\n' "$map_yaml" "$nav_params"
            ;;
        sensors)
            require_files "$workspace/launch/01_sensors.launch.py" || return 1
            require_package hesai_ros_driver "$lidar_install" || return 1
            exec ros2 launch "$workspace/launch/01_sensors.launch.py"
            ;;
        scan)
            exec timeout 15s ros2 topic echo /hz_nav/scan sensor_msgs/msg/LaserScan \
                --qos-reliability best_effort --qos-durability volatile --once --field header
            ;;
        base)
            require_package hunter_base "$robot_install" || return 1
            confirm_on_site 'START BASE' \
                '启动真实底盘会连接 can0、启用电脑控制并尝试解除制动。' || return 1
            exec ros2 run hunter_base hunter_base_node --ros-args \
                -r __ns:=/hz_nav -p use_sim_time:=false \
                -p port_name:=can0 -p robot_model:=hunter2 -p simulated_robot:=false \
                -p odom_frame:=odom -p base_frame:=base_link \
                -p odom_topic_name:=/hz_nav/odom -p publish_odom_tf:=true \
                -r /cmd_vel:=/hz_nav/blocked_cmd_vel -r /hunter_status:=/hz_nav/hunter_status
            ;;
        nav2)
            require_files "$workspace/launch/bringup_launch.py" "$map_yaml" "$nav_params" || return 1
            exec ros2 launch "$workspace/launch/bringup_launch.py" \
                namespace:=hz_nav use_namespace:=true slam:=False \
                "map:=$map_yaml" "params_file:=$nav_params" use_sim_time:=false autostart:=false
            ;;
        loc-on) lifecycle 30s localization 0 ;;
        rviz)
            require_files "$rviz_config" || return 1
            exec ros2 run rviz2 rviz2 -d "$rviz_config" \
                --ros-args -r __ns:=/hz_nav -r /initialpose:=/hz_nav/initialpose
            ;;
        tf)
            exec timeout 6s ros2 run tf2_ros tf2_echo map base_link
            ;;
        ready)
            timeout 10s ros2 service call /hz_nav/request_nomotion_update std_srvs/srv/Empty '{}' ||
                return 1
            lifecycle 60s navigation 0
            ;;
        pose)
            exec timeout 10s ros2 topic echo /hz_nav/amcl_pose geometry_msgs/msg/PoseWithCovarianceStamped \
                --qos-durability transient_local --qos-reliability reliable --once --field pose.pose
            ;;
        pick)
            exec timeout 60s ros2 topic echo /clicked_point geometry_msgs/msg/PointStamped --once
            ;;
        plan)
            exec timeout 30s ros2 action send_goal \
                /hz_nav/compute_path_to_pose nav2_msgs/action/ComputePathToPose \
                "{goal: $goal_pose, planner_id: GridBased, use_start: false}"
            ;;
        status) read_status ;;
        goal)
            require_files "$tree" || return 1
            printf '本次目标 map  x=%s y=%s qz=%s qw=%s\n' "$1" "$2" "$3" "$4"
            confirm_on_site 'SEND GOAL' \
                '发送目标会让实车行驶。确认同一目标的绿线和净空，原行为树遇阻可能倒车。' ||
                return 1
            local feedback
            if ! feedback=$(read_status); then
                fail '未读到底盘状态，目标已取消。'
                return 1
            fi
            printf '%s\n' "$feedback"
            if ! awk -F':[[:space:]]*' '
                $1 == "linear_velocity" {
                    valid_speed = ($2 ~ /^[-+]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][-+]?[0-9]+)?$/)
                    stopped = valid_speed && $2 + 0 >= -0.01 && $2 + 0 <= 0.01
                }
                $1 == "vehicle_state" { healthy = ($2 == "0") }
                $1 == "error_code" { no_error = ($2 == "0") }
                $1 == "control_mode" { can_mode = ($2 == "1") }
                END { exit !(stopped && healthy && no_error && can_mode) }
            ' <<<"$feedback"; then
                fail '底盘状态未通过。需处于 CAN 控制、状态和故障码为 0、线速度绝对值不超过 0.01 m/s。'
                return 1
            fi
            exec ros2 action send_goal /hz_nav/navigate_to_pose nav2_msgs/action/NavigateToPose \
                "{pose: $goal_pose, behavior_tree: '$tree'}" --feedback
            ;;
        snapshot)
            local snapshot
            snapshot=$(mktemp -d "$logs/nav2_snapshot_$(date +%Y%m%d_%H%M%S)_XXXXXXXX") || return 1
            if cp -a -- "$workspace/config" "$workspace/launch" "$workspace/maps" "$workspace/rviz" "$snapshot/" &&
                timeout 20s ros2 param dump /hz_nav/controller_server --no-daemon --spin-time 3 \
                    > "$snapshot/controller_runtime.yaml"; then
                printf '配置和控制器参数已保存到 %s\n' "$snapshot"
            else
                fail "快照未完成，已有内容保留在 $snapshot"
            fi
            ;;
        nav-off) lifecycle 60s navigation 4 ;;
        loc-off) lifecycle 30s localization 4 ;;
    esac
)

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    hznav "$@"
fi
