> 台式机适配（2026-10-31）：当前运行根目录为 `D:\rob-memory` / `/mnt/d/rob-memory`，旧来源与历史记录保留原路径。WSL 3.0.3 和原 Ubuntu 22.04 已恢复，完整模型包已在个人工作区重新构建，入口只读检查通过；OpenGL 查询确认使用 RX 9070 XT 硬件加速。Gazebo GUI 与传感器运行尚未在台式机验收。详见 [台式机恢复记录](../outputs/hunter_desktop_restore_20261031/README.md)。

> 场景集成与复位实测（2026-11-05）：完整车体已与实验室候选场景合并，并通过无头加载、落位与复位检查。与入口直接相关的三条结论：**(1)** 生产场景 `hz_hunter_full.sdf` 写的 `z=0.167` 比轮子接触半径 `0.165` 高 2 mm，模型起初悬空，复位后会落下；**(2)** `reset {all: true}` **不是**恢复初始位姿，连续两次复位实测 x 由 `6.80000 → 6.80116 → 6.80261`，每次累积约 1.2～1.45 mm，不能用作强化学习的重复复位；**(3)** 应改用 `/world/<world>/set_pose` 服务，两次调用之间漂移为 0，但会稳定停在请求点前约 0.98 mm（固定偏置，可补偿）。重置流程应为「`set_pose` → 读回实际位姿 → 以实测值作为 episode 初态」。证据见 [lab_scene_with_vehicle_check.json](../outputs/hunter_research_platform_20261031/lab_scene_candidate/lab_scene_with_vehicle_check.json)，方法与可通行性重算见 [科研仿真平台阶段记录](../outputs/hunter_research_platform_20261031/README.md)。

# HUNTER 完整模型：默认暂停入口

在 Windows PowerShell 先检查，再打开完整模型：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'D:\rob-memory\sim\tools\start_hunter_full_scene.ps1' -Check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'D:\rob-memory\sim\tools\start_hunter_full_scene.ps1'
```

当前默认暂停，本轮请勿点击播放。终端保持前台等待；关闭 Gazebo 窗口或按 Ctrl+C 后，会话会收尾自己创建的 Gazebo 与 ROS 进程组。`-Check` 只检查个人环境、文件、安装包与库，不启动 ROS 节点或 Gazebo。入口不接受其他参数或自选世界。

完整外形采用厂家 HUNTER2 分体 CAD 与本车上装，保留 4 个滚动关节、2 个转向关节。涂装和部分覆盖件尚未按照片一比一复原。这是模型与传感器验收场景，没有加载旧实验室地图。

传感器配置为激光雷达 720 × 32、10 Hz，RGBD 640 × 480、5 Hz，IMU 50 Hz；这些是设置频率，不是实测运行速度。暂停时传感器不会连续出帧。ARS548 与 GNSS 当前只有外形和 TF，没有专用输出。质量、摩擦和传感器物理安装位置未经过实测验证。

小车建图配置的注释按 CH104 100 Hz 假设编写；目前仿真 IMU 配置为 50 Hz，尚未确认实车实际输出频率，也没有验证动态建图时序。仿真未复用配置中的时间偏移和噪声参数。

RGBD 相机的水平视场依据小车个人建图配置中的 D435i 彩色相机焦距 `fx=606.7595825195312` 设置。当前 Ogre1 渲染环境使用居中、方形像素近似，仿真输出为 `fx=fy=606.7595825195312`、`cx=320`、`cy=240`；这与原彩色配置的 `fy=606.700439453125`、`cx=329.2454833984375`、`cy=243.96548461914062` 不完全相同。RGB 与深度共用该近似，深度模组参数尚未核实。

仿真 `imu_link` 表示 CH104 建图数据帧。相机光学帧和 IMU 数据帧依据收到的 FAST-LIVO2 建图外参，相对于导出模型中的名义雷达安装帧设置。相机外壳及安装框相对原名义模型平移 `(-13.65, -2.5, -6)` mm，保持外壳网格和内部相对位置，以免光心被其自身网格遮挡。此对齐不是实车物理安装的测量结果，建图参数的实际物理精度也未经独立验证。来源、哈希和适用范围见 [参数记录](../outputs/hunter_sensor_parameters_20261030/README.md)。

静态验收已检查原生传感器、ROS、TF 和 2D scan，证据见 [静态传感器记录](../outputs/hunter_sensor_parameters_20261030/runtime/de3d74e70301/check.json) 和 [相机投影记录](../outputs/hunter_sensor_parameters_20261030/probes/8ff47460e971/check.json)。[完整模型近景](../outputs/hunter_model_upgrade_20261030/references/full_preview/e431bbcda444/render.png) 是此次相机外壳位置调整之前的暂停预览；两个静态传感器检查均使用当前模型。

ROS 观察节点及话题统一位于 `/hz_sim/full/`，桥接配置为 9 个 Gazebo → ROS 单向观察接口（公共 `/clock` 除外），没有速度桥接或控制服务桥接。正常启动先验证个人 ROS 域 73 与回环选择，再创建完整会话。已有完整会话或个人分区已有仿真时会拒绝重复启动，请先关闭自己的旧仿真窗口。

每次会话的 Gazebo、ROS 原始 Linux UTF-8 日志，以及包含启动参数、自建 PID 和关闭结果的 `session.json`，位于 `D:\rob-memory\outputs\hunter_desktop_restore_20261031\sessions\` 的独立子目录。PowerShell 入口临时切换控制台 UTF-8，退出时恢复编码。

常用旧名 `start_control_scene_logged.ps1` / `.bash` 已转向此完整模型。原件备份在 [legacy](../outputs/hunter_model_upgrade_20261030/references/entry/legacy/)。旧 `start_control_scene.bash`、旧世界与 `run_straight_test.bash` 保留作历史回归；`run_straight_test.bash` 只适用于旧简化世界，不能用于这个完整模型。

入口固定文件的 SHA256 封存在 `tools/hunter_full_entry_manifest.json`。`tools/check_full_entry.py` 同时调用完整场景和观察接口契约，核对源包所有 `source_manifest.outputs` 与已安装运行资源；唯一不要求安装到 share 的输出是构建期 `CMakeLists.txt`，它在源包仍必须通过 SHA256 检查。安装资源允许 colcon 的符号链接，但目标必须是个人 `/home/aphelios/hz_sim_ws/src/hz_hunter_full_description/` 中的同相对路径文件，并逐一通过相同的 SHA256 检查。`tools/seal_full_entry.py` 只重新计算固定本地文件列表的哈希，不运行软件。
