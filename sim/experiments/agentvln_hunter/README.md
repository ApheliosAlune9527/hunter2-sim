# AgentVLN on HUNTER 2.0 — Gazebo 仿真复现

本仓库是用户 2026-11-08 下达的 AgentVLN 复现任务的工作区。当前只做 HUNTER 2.0 + Gazebo Fortress 仿真；不连接实车域 88。
2026-11-09 的真实 VLM 增量已归档独立的场景、地图和复跑入口。下文保留 11 月 8 日规则基线的验收口径。 [直线停靠场景与 VLM 复跑](D:/rob-memory/sim/experiments/agentvln_hunter/README_straight_vlm.md)

总计划分四步：

1. 固定 Nav2 基线，并在同一仿真会话接通 RGB-D 相机（本文件记录的范围，已完成）。
2. 生成图像选路 / 到点技能。
3. 局部深度定位、反投影和遮挡纠偏。
4. 固定任务集验收、对照实验和交付。

状态（2026-11-08 11:00 America/Denver）：第 1 步已完成；第 2 步工程基线已完成（[README_step2.md](README_step2.md)）；第 3 步闭环已完成，三次重复全部停进停车区（[README_step3.md](README_step3.md)）；第 4 步已完成 36 轮验收（6 任务 × 2 模式 × 3 次）：视觉闭环任务成功 17/18、动作 status=4 17/18；已知坐标基线任务成功 16/18、动作 status=4 12/18。详见 [README_step4.md](README_step4.md) 与 `outputs/agentvln_hunter_20261108_step4/summary.md`。

---

## 1. 仿真环境和安全边界

- 主机：Windows 台式机；WSL2 Ubuntu-22.04，用户 aphelios。
- ROS 2 Humble；Gazebo Fortress 6.18.0；CycloneDDS。
- 环境文件：sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash
  - ROS_DOMAIN_ID=73
  - ROS_LOCALHOST_ONLY=1
  - RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  - 独立 IGN_PARTITION / Gazebo 分区
  - CYCLONEDDS MaxAutoParticipantIndex=64
- 不启动、不 source 实车工作区；不访问域 88。
- 启动和停止只操作本次登记的进程：run_fix_stack.bash / stop_fix_stack.bash 通过 LOG_DIR/processes.tsv 记录 PID、内核启动时间和命令行，停止时校验启动时间，无 pkill 回退。

注意：从 PowerShell 调 WSL 时，长命令里的变量符号会被 PowerShell 提前展开。应使用 .bash 脚本，或把完整命令放进单引号，不要直接拼多行内联命令。

---

## 2. Nav2 固定基线（已知坐标到点、取消、停稳）

### 2.1 启动入口

    cd /mnt/d/rob-memory
    export PARAMS=/mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/nav2_params_fix.yaml
    export LOCALIZER=amcl
    export WORLD=/mnt/d/rob-memory/sim/experiments/agentvln_hunter/scenes/lab_agentvln_world.sdf
    export BRIDGE=/mnt/d/rob-memory/sim/experiments/agentvln_hunter/config/agentvln_bridge.yaml
    export LOG_DIR=/tmp/agentvln_step1/camera4
    export GUI=0
    bash sim/experiments/lab_nav_fix_20261106/run_fix_stack.bash

PARAMS 必须显式指向 nav2_params_fix.yaml。入口默认是 nav2_params_carmatch.yaml（0.10 m/s、REEDS_SHEPP、允许倒车和未知区），不是本实验的固定基线。

地图：outputs/lab_nav_fix_20261106/lab_nav_map_fix.yaml（image 实际为同目录 lab_nav_map.pgm，241×465，0.05 m，origin (-5.09,-4.89)）。

### 2.2 运行中读回

verify_fix_config.py 在相机栈运行时 16/16 PASS、overall=True：

- 规划器：DUBIN；minimum_turning_radius=1.669；allow_unknown=false。
- 控制器：allow_reversing=false；use_rotate_to_heading=false；desired_linear_vel=0.25。
- xy_goal_tolerance=0.20；yaw_goal_tolerance=0.35。
- footprint：[[-0.184,-0.393],[0.834,-0.393],[0.834,0.393],[-0.184,0.393]]。
- BT：navigate_no_spin.xml / navigate_through_poses_no_spin.xml，无倒车恢复。
- /map 元数据与 /scan 正常。

证据：outputs/agentvln_hunter_20261108_step1/nav2_verify_camera.json。

### 2.3 已知坐标结果

全部使用 LOCALIZER=amcl，并在每轮开始用 --reinit-amcl --amcl-init-std 0.05 --amcl-init-yaw-std 0.05 从已知初始位姿重新种子化。

| 任务 | 目标 (map) | 动作状态 | 最终误差 | 朝向误差 | 仿真耗时 | 停稳 |
| --- | --- | --- | --- | --- | --- | --- |
| near_straight | (0.79, -0.77, 0.0) | 4 SUCCEEDED | 0.1651 m | -0.0283 rad | 4.28 s | v_max 0.00735 m/s，真值位移 0.0001 m |
| short_straight | (1.885, 0.435, 0.522) | 4 SUCCEEDED | 0.0958 m | 0.1245 rad | 11.26 s | v_max 0.00904 m/s，真值位移 0.0002 m |
| mid_offset | (3.185, 1.235, 0.5335) | 4 SUCCEEDED | 0.1045 m | 0.1114 rad | 17.05 s | v_max 0.00569 m/s，真值位移 0.0001 m |
| long_run | (4.285, 2.535, 0.634) | 4 SUCCEEDED | 0.1406 m | 0.0910 rad | 23.91 s | 停稳 |
| cancel | near_straight，预算 2.0 s | 5 CANCELED | 0.5325 m | 0.033 rad | 2.02 s | 取消 ack 1 个 goal，终态 5，等待 0.021 s；v_max 0.00920 m/s，真值位移 0.0002 m |

short_straight 这一轮 AMCL 的 drift.final_m 约 0.202 m，虽仍成功，但说明该地图/激光配置下 AMCL 会在运动中积累明显横向漂移；这不是可以忽略的“完美定位”基线。

### 2.4 AMCL 初始先验失败样例（必须保留的教训）

第一次在相机场景上跑 nav_camera_once.py 1.885 0.435 0.522 时，栈启动时的 AMCL 先验较松，车开出 0.53 m 后 AMCL 横向误差约 0.117 m，规划器在当前位置找不到可行 Dubin 路径，动作 status=6 ABORTED，车停在 (0.3205,-0.7283)，最终误差 1.9496 m。

处理：用 tools/reset_and_seed.py 把车 teleport 回 spawn，并以协方差 0.0025 重新发 /initialpose；AMCL 落点 (-0.2113,-0.7679,-0.0002)，与真值误差 2.5 mm。随后同一目标成功（见 §3.4）。

结论：在当前稀疏 2D 地图上，已知坐标基线必须先给紧先验；规划失败是定位漂移的后果，不是地图不连通、目标碰撞或 DUBIN 参数错误（前面已用连通分量、costmap、footprint 净空和手动 ComputePathToPose 逐项排除）。该限制会在第 2–4 步继续影响闭环，需要在任务开始时固定初始位姿并记录定位误差。

失败证据：outputs/agentvln_hunter_20261108_step1/nav_camera_loose_seed_fail/。

---

## 3. RGB-D 相机接通与验收

### 3.1 场景和桥接

- 世界：sim/experiments/agentvln_hunter/scenes/lab_agentvln_world.sdf
  - 从 outputs/lab_nav_20261105/lab_nav_world_drive.sdf 复制，保留原 Nav2/scan/车辆插件。
  - 在 base_link 上增加 rgbd_camera：name=agentvln_camera，pose=0.644 0.015 0.475 0 0 0，5 Hz，640×480，horizontal_fov=0.9706402426459841，clip 0.1–20 m。
  - 增加三个纯视觉、无碰撞标记：red (1.5,-1.05,0.90)、green (1.5,-0.75,0.90)、blue (1.5,-0.45,0.90)，边长 0.12 m。
  - sha256：26fd9e5b77d7e85803da8c16b7376d908df46290cd0f4b8f0b69c7e372fc2bd7。
- 桥接：sim/experiments/agentvln_hunter/config/agentvln_bridge.yaml
  - 复制 lab_bridge_fix.yaml，追加三条 GZ→ROS：
    - /hz_sim/agentvln/camera/image → sensor_msgs/msg/Image（ignition.msgs.Image）
    - /hz_sim/agentvln/camera/depth_image → sensor_msgs/msg/Image（ignition.msgs.Image）
    - /hz_sim/agentvln/camera/camera_info → sensor_msgs/msg/CameraInfo（ignition.msgs.CameraInfo）
  - sha256：d7adcb93c8fb48e8066ff42a96281820fe2b6a5a4aab33f65dc144de268582e7。
- 标记清单：config/scene_markers.json。
- 生成脚本：tools/prepare_scene.py。

### 3.2 TF 和坐标约定

- 静态 TF：base_link -> agentvln_camera_optical_frame，平移 (0.644, 0.015, 0.640)，四元数 xyzw=(-0.5, 0.5, -0.5, 0.5)。
- 光学系：x 向右、y 向下、z 向前；相对 base_link 的轴映射为
  - optical x → base (0,-1,0)
  - optical y → base (0,0,-1)
  - optical z → base (1,0,0)
- 为什么 z 是 0.640 而不是模型内的 0.475：Map/odom 是 2D 地面系，base_link 在 map 中 z=0；Gazebo 模型原点离地 0.165 m，相机相对模型 z=0.475 m，因此光学中心世界高度为 0.640 m。按 0.475 投影时三个标记落在画面外（v≈-54），按 0.640 为 v≈92，与实测一致。
- 内参近似：fx=fy=606.7595825195312、cx=320、cy=240、畸变 0，深度图使用同一内参、单位米。来源：outputs/hunter_sensor_parameters_20261030/README.md。
- 投影：u = fx*X/Z + cx，v = fy*Y/Z + cy；反投影：p_camera = z * K^-1 * [u,v,1]^T，再用图像时刻的 map -> optical TF 变到 map。

关键修复：静态 TF 的一个 StaticTransformBroadcaster 在 depth=1 下多次 sendTransform 会互相覆盖。odom_tf.py 和 truth_localisation.py 已改为一次 sendTransform([laser_tf, camera_tf]) 同时发布；否则 AMCL 晚订阅时只有相机边，base_link->laser 丢失，scan 被 TF 过滤器丢弃。

### 3.3 验收结果（camera_verify3）

脚本：tools/verify_camera.py。启动后预热 3 s，只接受与 /clock 年龄在 0–1.5 s 内的新帧；在图像自身 stamp 上查 TF，不用 latest 掩盖时序。

- 话题：/hz_sim/agentvln/camera/image、/depth_image、/camera_info，实测 5.0 Hz。
- 3 帧同步：RGB/depth/CameraInfo stamp 完全一致；图像年龄 0.008–0.012 s。
- 图像：RGB 640×480 rgb8；深度 640×480 32FC1；frame_id 均为 agentvln_camera_optical_frame。
- 内参：K/P 的 fx=fy=606.7595825195312，cx=320，cy=240；D 全 0；P 与 K 一致。
- 静态 TF：平移误差 0；旋转误差 0（实际四元数 (0.5,-0.5,0.5,-0.5) 与期望互为相反数，表示同一旋转）；光轴映射精确。
- RGB 均值 179.798、std 52.58（非黑）。
- 深度有效像素比例 0.946865；min 1.0060 m、median 3.3673 m、max 19.9154 m。
- overall=true。

标记投影、测距、反投影：

| 标记 | 地图坐标 | u | v | 颜色均值 | 深度中值 | 反投影地图误差 |
| --- | --- | --- | --- | --- | --- | --- |
| red | (1.5,-1.05,0.90) | 474.74 | 91.96 | [237,9,9] | 1.0060 m | 0.06326 m |
| green | (1.5,-0.75,0.90) | 303.93 | 92.06 | [9,228,9] | 1.0060 m | 0.06215 m |
| blue | (1.5,-0.45,0.90) | 133.36 | 92.16 | [9,9,242] | 1.0060 m | 0.06559 m |

深度中值比标记中心期望 z 小约 0.060 m，恰好等于标记半边长 0.06 m：深度打在朝向相机的正面，不是中心；这是几何上正确的偏差，不是深度单位错误。反投影点 x≈1.439–1.440，也落在正面上。

证据目录 outputs/agentvln_hunter_20261108_step1/camera_verify3/：report.json、rgb.png、annotated.png、depth_vis.png、depth.npy、camera_info.json。annotated.png 已目视确认三色标记清晰可见并带 u/v/z 标注。

camera_verify/ 和 camera_verify2/ 是修复 TF 高度/时序前的失败尝试，保留作对照；只有 camera_verify3/ 是验收通过版本。

### 3.4 同一会话内 Nav2 + 相机行驶取帧

脚本：tools/nav_camera_once.py。先 reset_and_seed.py 回到 spawn 并紧种子化，再发 NavigateToPose(1.885,0.435,0.522)，同时订阅 RGB、/ground_truth、/amcl_pose。

结果（outputs/agentvln_hunter_20261108_step1/nav_camera/report.json）：

- 动作状态 4 SUCCEEDED；墙钟 13.094 s。
- 最终真值 (1.7695,0.4058,0.6922)；最终误差 0.1192 m；朝向误差 0.1702 rad；AMCL 误差 0.0705 m。
- 停车后 1 s 真值位移 0.0146 m（< 0.05 m 停稳判据）。
- 相机帧 70 帧；stamp 跨度 13.8 s；行驶中 66 帧；最大真值位移 2.3159 m。
- start.png 为起步视角（三色标记在画面内），mid.png 为行驶中（标记位置随车移动变化），last.png 为终点近距离墙面。三帧字节数/哈希不同，证明不是重复积压帧。

这一条同时满足“同一 Gazebo/ROS 会话里 Nav2 可用、RGB 与深度同步采样、静止与行驶中都有新帧”。

---

## 4. 文件索引

新增代码/配置（sim/experiments/agentvln_hunter/）：

- scenes/lab_agentvln_world.sdf：相机场景副本。
- config/agentvln_bridge.yaml：含相机三条桥接。
- config/scene_markers.json：红/绿/蓝标记坐标和尺寸。
- tools/prepare_scene.py：从基线世界生成场景（含 <static>true</static> 修复）。
- tools/verify_camera.py：相机同步、内参、TF、标记投影/测距/反投影验收。
- tools/nav_camera_once.py：一次 Nav2 到点并记录行驶帧。
- tools/reset_and_seed.py：teleport + 紧 AMCL 先验。
- tools/nav_goal_once.py：单次 NavigateToPose / 取消。
- tools/map_slice.py、map_bottleneck.py、check_map_connectivity.py、check_pose_footprint.py、query_costmap.py、try_plan.py：地图、代价地图、规划和净空诊断。
- tools/list_gz_models.bash、gz_model_poses.bash、check_scene_tree.py、probe_tf_z.bash：Gazebo 场景/TF 探测。

修改的既有文件：

- sim/experiments/lab_nav_fix_20261106/odom_tf.py：一次发布两条静态 TF；相机 TF z=0.640。
- sim/experiments/lab_nav_fix_20261106/truth_localisation.py：同上。
- sim/experiments/lab_nav_fix_20261106/run_nav_eval_fix.py：新增 --amcl-init-std / --amcl-init-yaw-std（默认 0.5 / 0.2618）。
- sim/experiments/lab_nav_fix_20261106/verify_fix_config.py：运行中读回参数（未改逻辑）。

输出证据（outputs/agentvln_hunter_20261108_step1/）：

- nav2_verify_camera.json：相机栈上的 16/16 Nav2 参数读回。
- baseline_near_tight.json、baseline_short_tight.json、baseline_mid_long_tight.json、baseline_cancel.json：已知坐标基线。
- camera_verify3/：相机验收通过版本。
- nav_camera/：同会话到点 + 行驶取帧。
- nav_camera_loose_seed_fail/：松先验导致的规划失败对照。
- camera_verify/、camera_verify2/：早期失败尝试。

复现命令（栈已停止后）：

    # 1) 启动（见 §2.1）
    # 2) Nav2 参数
    python3 -B sim/experiments/lab_nav_fix_20261106/verify_fix_config.py

    # 3) 相机验收（约 5 s；世界需要是相机场景）
    python3 -B sim/experiments/agentvln_hunter/tools/verify_camera.py --out outputs/agentvln_hunter_20261108_step1/camera_verify3

    # 4) 紧先验 + 单目标 + 行驶取帧
    python3 -B sim/experiments/agentvln_hunter/tools/reset_and_seed.py -0.21 -0.77 0 0.0025
    python3 -B sim/experiments/agentvln_hunter/tools/nav_camera_once.py 1.885 0.435 0.522 --out outputs/agentvln_hunter_20261108_step1/nav_camera

    # 5) 停止
    LOG_DIR=/tmp/agentvln_step1/camera4 bash sim/experiments/lab_nav_fix_20261106/stop_fix_stack.bash

---

## 5. 交付与验收状态（2026-11-08 11:40 America/Denver）

### 5.1 已通过的模块

| 步骤 | 模块 | 证据 | 结果 |
| --- | --- | --- | --- |
| 1 | 固定 Nav2 基线 | `outputs/agentvln_hunter_20261108_step1/nav2_verify_camera.json` | 运行中读回 16/16 参数（DUBIN、R=1.669、不允许未知区/倒车、footprint、BT） |
| 1 | 已知坐标到点 / 取消 / 停稳 | `.../baseline_*.json` | 4 个目标 status 4（误差 0.096–0.165 m）；取消 status 5、ack 1、停稳 |
| 1 | RGB-D 相机接通 | `.../camera_verify3/report.json` | overall=true；深度有效率 0.9469；三色标记投影/测距/反投影误差 0.062–0.066 m |
| 1 | 同一会话行驶取帧 | `.../nav_camera/report.json` | 70 帧、66 帧在行驶中、最大位移 2.32 m、终点误差 0.119 m |
| 2 | 候选生成与图像选路 | `outputs/agentvln_hunter_20261108_step2/candidate_view/report.json` | 15 采样 → 7 个可通行且可见候选，编号投影叠加 |
| 2 | 颜色选择闭环 / 转弯 | `.../agent_loop_color`、`agent_loop_turn` | 1 段与 2 段均成功，终点误差 0.31 m / 0.099 m |
| 3 | 深度定位 + 直进停靠 | `outputs/agentvln_hunter_20261108_step3/pipeline_v10–v12` | 3/3 停进停车区（0.261–0.266 m），status 4，停稳 0.033–0.036 m |
| 3 | 对照：关纠偏 / 关深度查询 | `.../ablation_no_reobserve`、`.../ablation_no_depth_query` | 关纠偏失败（只见 1 域）；关深度查询仍成功（0.268 m） |
| 4 | 6 任务 × 2 模式 × 3 次 | `outputs/agentvln_hunter_20261108_step4/` | 视觉闭环任务成功 17/18、动作 4 17/18；已知坐标基线 16/18、动作 4 12/18 |

细节：第 2 步见 [README_step2.md](README_step2.md)，第 3 步见 [README_step3.md](README_step3.md)，
第 4 步见 [README_step4.md](README_step4.md) 与
`outputs/agentvln_hunter_20261108_step4/summary.md`。

### 5.2 失败样例（都保留在证据目录里）

| 样例 | 现象 | 根因 |
| --- | --- | --- |
| `step1/nav_camera_loose_seed_fail/` | 开出 0.53 m 后 status 6 | AMCL 松先验导致横向漂移 0.117 m，规划器找不到 Dubin 路径 |
| `step2/agent_loop_mid/` | 最终偏到 (4.55, 2.62)，误差 1.945 m | 候选间距与剩余距离不匹配，最后一段冲过头 |
| `step3/pipeline/` | 再观察首段 status 6 | 红牌立柱穿过激光平面进入代价地图 |
| `step3/pipeline_v3/` | 观察位姿只见 1 个连通域 | 观察点距近箱 1.3 m，近箱挡住远箱 |
| `step3/pipeline_v4/` | 开出 0.3 m 后规划失败 | 目标与出发朝向差 20°，Dubin 需要 S 弯 |
| `step3/pipeline_v5,v6/` | 停靠段停在 0.6–0.7 m 外 | 停靠朝向与接近方向差 0.4–0.5 rad，末端需要 1.31 m 转弯半径 |
| `step3/pipeline_v7/` | 25 个候选全部压近箱 | 近箱压在观察位姿与远箱的连线上 |
| `step3/pipeline_v8/` | 停车区距离 0.321 m（差 21 mm） | 期望停靠点按箱面中心算，与深度落点差 0.13 m |
| `step3/pipeline_v9/` | 车没动，规划从上次终点出发 | /initialpose 丢失，AMCL 沿用旧位姿 |
| `step4/*_baseline_r*/` | status 6 但车已停在停车区（0.08–0.12 m） | Smac Dubin 死区：到点残差在 0.2 m 容差内，动作仍 abort |
| `step4/A1_visual_r2`、`A2_baseline_r2` 等 | 停车区距离 0.306–0.376 m | 0.30 m 停车区 + 0.20 m 到点容差叠加余量不足 |

### 5.3 缺失条件（未做，不伪造）

- **没有 VLM**：本地无可用推理后端（无 ROCm/Vulkan/NVIDIA 驱动、无 torch/transformers/
  ollama/llama.cpp、HF 缓存为空）。目标检测与选路是颜色规则，属工程基线；指令文本
  只作为报告字段，不参与决策。
- **没有接触事件**：本 Gazebo Fortress 构建不广播 contact 话题（teleport 进墙也无消息），
  碰撞只能报轮廓净空与停车区距离代理，接触记 `not_measured`。
- **没有 SPL**：未构造同约束下的独立最短参考路径，只报真值路径长度。
- **没有"关编号"对照**：该项需要 VLM 才有意义（规则选择器与画面编号无关）；
  候选报告本身同时保存编号和像素坐标，接上 VLM 后可直接补这一项。
- **未知起点定位**：所有轮次都用紧先验（协方差 0.0025）在已知起始位姿重新种子化，
  运动后 AMCL 仍有 0.05–0.13 m 漂移；真实未知起点未验证。

### 5.4 下一步可做

1. 接本地 VLM（先单帧图像 + 编号选择 + 结构化输出验收，再接实时链路），补"关编号"对照。
2. 提高停靠精度：同一目标多帧深度中值，或到点后用深度复测做一次微调。
3. 加接触传感（换支持 contact 的构建或加 bumper），把 `not_measured` 补上。
4. 用规划器输出构造同约束最短参考路径，计算实验室 SPL。
