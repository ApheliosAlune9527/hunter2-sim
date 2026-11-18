# HUNTER 2.0 直线停靠场景与 VLM 复跑

本目录提供正式的复跑输入与入口。原批次的图片、轨迹、模型决策和失败样例保存在运行证据目录。 [原批次运行记录](D:/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy/README.md) · [逐轮数据](D:/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy/validation_summary.json)

## 归档的输入

| 用途 | 文件 |
|---|---|
| 验收过的场景 | [lab_agentvln_bigfar_straight.sdf](D:/rob-memory/sim/experiments/agentvln_hunter/scenes/lab_agentvln_bigfar_straight.sdf) 与 [墙体 STL](D:/rob-memory/sim/experiments/agentvln_hunter/scenes/lab_walls.stl) |
| 蓝箱、观察位姿和停车区 | [target_layout_straight.json](D:/rob-memory/sim/experiments/agentvln_hunter/config/target_layout_straight.json) |
| 冻结地图与桥接 | [地图 YAML](D:/rob-memory/sim/experiments/agentvln_hunter/config/straight_nav_map/lab_nav_map_fix.yaml)、同目录 PGM、[相机与速度桥](D:/rob-memory/sim/experiments/agentvln_hunter/config/agentvln_bridge.yaml) |
| 文件校验 | [SHA256 清单](D:/rob-memory/sim/experiments/agentvln_hunter/config/straight_vlm.sha256) |

场景以验收过的 SDF 为固定输入，归档版只把墙体 URI 指向同目录的 STL。布局 JSON 只更新场景路径。墙体、地图 YAML 和 PGM 与原始文件字节一致，启动时校验这些文件以及原冻结 Nav2 参数。复跑使用现有 WSL 和 HUNTER CAD 资源，源路径仍以工作区 `D:/rob-memory` 为准。`outputs/` 用于写入新结果，也存放供历史回放的录制帧。

## 运行

Windows 本地服务使用论文的基座 **Qwen2.5-VL-3B-Instruct F16** 和 RX 9070 XT。服务地址为 `127.0.0.1:18081`。如服务已停止，使用 [Windows 启动脚本](D:/AgentVLN-runtime/qwen25vl-3b/start_qwen_vl.ps1) 启动，再确认 `/health` 返回 `status: ok`。

以下命令在个人 WSL Ubuntu 22.04 的 `aphelios` 终端运行，操作的是 Gazebo 虚拟车。启动前确认域 73 与 Gazebo 分区 `hz_sim_aphelios_73` 空闲。

```bash
repo=/mnt/d/rob-memory
experiment="$repo/sim/experiments/agentvln_hunter"
fix="$repo/sim/experiments/lab_nav_fix_20261106"
tools="$experiment/tools"
source "$fix/lab_nav_fix_env.bash"
source /home/aphelios/hz_sim_ws/install/setup.bash
ros2 node list --no-daemon
ign topic -l
```

确认没有在运行的仿真会话后，启动归档场景。`LOG_DIR` 用于登记本次会话的进程。

```bash
LOG_DIR=$(mktemp -d /tmp/agentvln_vlm_straight_XXXXXXXX)
export LOG_DIR
bash "$tools/start_straight_stack.bash"
ros2 param get /map_server yaml_filename
```

地图路径应为 `/mnt/d/rob-memory/sim/experiments/agentvln_hunter/config/straight_nav_map/lab_nav_map_fix.yaml`。

先从标称观察位姿复跑一轮，以单独验证选箱和直进停靠。脚本同时保存一帧可用于配对回放的 RGB-D 数据。

```bash
mkdir -p "$repo/outputs"
trial=$(mktemp -d "$repo/outputs/agentvln_hunter_straight_XXXXXXXX")
python3 -B "$tools/reset_and_seed.py" 2.0 0.5 0.522 0.0025 --ros-args -p use_sim_time:=true && \
  python3 -B "$tools/step5_replay.py" --layout "$experiment/config/target_layout_straight.json" --out "$trial/frame" && \
  python3 -B "$tools/run_straight_dock.py" --mode vlm --out "$trial/dock"
```

从标准起点验证完整进场时，将复位位姿改为 `(-0.21, -0.77, 0)`，先用 `--mode observe` 到达观察位姿，再采帧及运行 `--mode vlm`。每个 `--out` 使用独立的新路径。两个模式分别保存动作终态和停稳证据。

完成行驶后只关闭本次登记的仿真进程。以下配对回放可在关仿真后使用刚采集的帧运行。

```bash
bash "$fix/stop_fix_stack.bash"
python3 -B "$tools/compare_replay.py" --frame "$trial/frame" --out "$trial/replay"
```

如需复查原批次的 2×2 数据，可把 `--frame` 改为原记录的 `/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy/natural_frame`。清理历史录制帧后，可按上面的入口重新采集。

## 归档复验

新入口校验了 7 项输入的 SHA256。运行中读回的地图来自归档 YAML，`/map` 为 241×465 格、0.05 m 分辨率，包含 64,691 个未知格、41,446 个空闲格和 5,928 个占用格。使用新采集的 RGB-D 从固定观察位姿完成一次模型选箱与直进，动作终态为 4，距停车区中心 **0.065 m**，1 秒真值位移 **0.1 mm**。新帧配对中，编号两组均为 2/2，原图两组均为 1/2。此轮为归档复验，原批次成绩单列。已清理本次登记的 4 组仿真进程。 [地图读回](D:/rob-memory/outputs/agentvln_hunter_20261109_repro_check/map_readback.json) · [在线复验](D:/rob-memory/outputs/agentvln_hunter_20261109_repro_check/virtual_dock/report.json) · [新帧配对](D:/rob-memory/outputs/agentvln_hunter_20261109_repro_check/replay_new_frame/report.json) · [清理回执](D:/rob-memory/outputs/agentvln_hunter_20261109_repro_check/stop_receipt.log)

## 数字口径

- **自由工具调度回放 0/4。** 在线流程由分阶段协议引导，模型实际发出两次深度查询并给出最终编号。配对回放每格仅 `n=2`，用同一帧的远、近两条指令核对选箱接口。该样本的深度工具收益尚未建立。
- **4.06 倍来自实拍颜色分割。** 同一标称布局的解析投影面积比为 3.97 倍。固定观察位姿实拍的两箱光轴深度差为 0.189 m，自然进场帧为 0.241 m。27 组位姿扰动的解析最小差为 0.151 m。
- **停靠留有间隔。** 标称停车位的车头中心沿地图 x 方向到远箱西侧平面的间隔约 0.72 m。车头中心到箱体最近点约 0.76 m。在线几何另沿车头接近方向对所测箱面保留 0.83 m 的目标余量。停车误差统计的是车体参考点到独立停车区中心的距离。

[解析几何记录](D:/rob-memory/outputs/agentvln_hunter_20261108_step5_unblock/geometry_check.json) · [实拍测量](D:/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy/straight_frame/report.json) · [四组配对回放](D:/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy/paired_2x2_natural_f16/report.json)
