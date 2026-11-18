#!/usr/bin/env bash
# Run a fresh, isolated simulator from the scene's original spawn.
set -eo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project=$(cd -- "$here/../../.." && pwd)
vln="$project/sim/experiments/agentvln_hunter"
fix="$project/sim/experiments/lab_nav_fix_20261106"
out=${1:?Supply a new results directory}
instruction=${2:-停在较远的蓝箱前，车头正对箱面}
record=${RECORD:-0}
if [[ "$record" == 1 && ! -t 0 ]]; then
    printf '录制模式需要在 WSL 交互终端运行。\n' >&2
    exit 2
fi
world="$vln/scenes/lab_agentvln_bigfar_straight.sdf"
bridge="$vln/config/agentvln_bridge.yaml"
source /opt/ros/humble/setup.bash
source /home/aphelios/hz_sim_ws/install/setup.bash
set -u
export ROS_DOMAIN_ID=74 ROS_LOCALHOST_ONLY=1 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI='<CycloneDDS><Domain><Discovery><MaxAutoParticipantIndex>64</MaxAutoParticipantIndex></Discovery></Domain></CycloneDDS>'
export IGN_PARTITION="hz_agentvln_reverse_$(cat /proc/sys/kernel/random/uuid)" IGN_IP=127.0.0.1
unset IGN_RELAY GZ_RELAY ROS_DISCOVERY_SERVER
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
export LOCALIZER=amcl HZ_NAV2_MAP_YAML="$vln/config/straight_nav_map/lab_nav_map_fix.yaml"

exec 9>/tmp/hz_reverse_dock_domain74.lock
flock -n 9
nodes=$(timeout 10s ros2 node list --no-daemon --spin-time 2.0)
[[ -z "$nodes" ]] || { echo "ROS domain 74 is in use: $nodes" >&2; exit 1; }
(cd "$project" && sha256sum --check --strict "$vln/config/straight_vlm.sha256")
curl.exe --noproxy '*' --silent --show-error --fail --max-time 5 http://127.0.0.1:18081/health
printf '\n'
mkdir -- "$out"
out=$(realpath -- "$out")
export ROS_LOG_DIR="$out/ros" PARAMS="$out/nav2_reverse.yaml"
printf 'domain=%s\nlocalhost_only=%s\nrmw=%s\npartition=%s\nlocalizer=%s\nworld=%s\nbridge=%s\n' \
    "$ROS_DOMAIN_ID" "$ROS_LOCALHOST_ONLY" "$RMW_IMPLEMENTATION" "$IGN_PARTITION" \
    "$LOCALIZER" "$world" "$bridge" > "$out/session.txt"
python3 -B "$here/prepare.py" "$out"

pids=()
start_time() { awk '{print $22}' "/proc/$1/stat" 2>/dev/null; }
start() {
    local name=$1 pid stamp
    shift
    setsid "$@" 9>&- > "$out/$name.log" 2>&1 </dev/null &
    pid=$!
    pids+=("$pid")
    stamp=$(start_time "$pid")
    printf '%s\t%s\t%s\n' "$name" "$pid" "$stamp" >> "$out/processes.tsv"
}

stop() {
    local result=$? pid member stamp
    trap - EXIT
    set +e
    local owned=()
    for pid in "${pids[@]}"; do
        while read -r member; do
            [[ -n "$member" ]] || continue
            stamp=$(start_time "$member")
            if [[ -n "$stamp" ]] && grep -azFxq -- "IGN_PARTITION=$IGN_PARTITION" "/proc/$member/environ" 2>/dev/null; then
                owned+=("$member:$stamp")
            fi
        done < <(ps -s "$pid" -o pid=)
    done
    for member in "${owned[@]}"; do
        pid=${member%%:*}
        [[ "$(start_time "$pid")" == "${member#*:}" ]] && kill -TERM "$pid" 2>/dev/null
    done
    sleep 2
    for member in "${owned[@]}"; do
        pid=${member%%:*}
        [[ "$(start_time "$pid")" == "${member#*:}" ]] && kill -KILL "$pid" 2>/dev/null
    done
    for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null; done
    for pid in "${pids[@]}"; do ps -s "$pid" -o pid=,stat=,args=; done > "$out/remaining_processes.txt"
    printf '已清理本轮仿真。结果目录 %s\n' "$out"
    exit "$result"
}
trap stop EXIT
trap 'exit 130' INT TERM

printf '虚拟车会话：ROS 域 %s，仅本机，Gazebo 分区 %s\n' "$ROS_DOMAIN_ID" "$IGN_PARTITION"
# Keep the sensor renderer off the Vulkan VLM device in this session only.
printf 'sensor_renderer=llvmpipe\n' >> "$out/session.txt"
start gazebo env LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe LP_NUM_THREADS=8 \
    ign gazebo -s -r -v 3 --headless-rendering "$world"
if [[ "$record" == 1 ]]; then
    printf 'preview_renderer=system_default\n' >> "$out/session.txt"
    gui_config=()
    if [[ -r /home/aphelios/.ignition/gazebo/6/gui.config ]]; then
        sed -E \
            -e 's@<camera_pose>[^<]*</camera_pose>@<camera_pose>-0.8 -0.5 6.4 0 1.12 0.30</camera_pose>\n    <camera_clip><near>0.1</near><far>40</far></camera_clip>@' \
            -e 's@<background_color>[^<]*</background_color>@<background_color>0.52 0.52 0.52 1</background_color>@' \
            /home/aphelios/.ignition/gazebo/6/gui.config > "$out/record_gui.config"
        gui_config=(--gui-config "$out/record_gui.config")
    fi
    start gui env -u LIBGL_ALWAYS_SOFTWARE -u GALLIUM_DRIVER -u LP_NUM_THREADS \
        MESA_D3D12_DEFAULT_ADAPTER_NAME='Radeon RX 9070 XT' ign gazebo -g -v 3 "${gui_config[@]}"
    printf '\n录屏预览已启动，车辆保持在出生点。等待开始信号。\n'
    read -r
fi
start bridge ros2 run ros_gz_bridge parameter_bridge --ros-args -p config_file:="$bridge"
start odom_tf python3 -B "$fix/odom_tf.py" --ros-args -p use_sim_time:=true
start nav2 ros2 launch "$fix/run_nav2_fix.launch.py"
start forward ros2 run nav2_planner planner_server --ros-args -r __ns:=/forward \
    --params-file "$out/forward.yaml"
if [[ "$record" != 1 && ${GUI:-0} == 1 ]]; then
    start gui ign gazebo -g -v 3
fi
if python3 -B -u "$here/episode.py" "$out" "$instruction" 2>&1 | tee "$out/episode.log"; then
    result=0
else
    result=$?
fi
if [[ "$record" == 1 ]]; then
    printf '\n本轮动作已结束。停止录屏后按回车关闭本轮 Gazebo。\n'
    read -r || true
fi
exit "$result"
