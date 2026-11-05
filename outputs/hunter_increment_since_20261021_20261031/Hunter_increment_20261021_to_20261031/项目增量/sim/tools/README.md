# 当前推荐：HUNTER 完整模型暂停入口（2026-10-30）

请使用 [sim/README.md](../README.md) 中的 PowerShell 检查与启动两条命令。`start_hunter_full_scene.ps1` 只接受 `-Check` 或无参数；默认暂停，本轮请勿点击播放。常用旧名 `start_control_scene_logged.ps1` / `.bash` 已转向完整模型，检查模式不启动 ROS 或 Gazebo。每次会话保留独立原始 UTF-8 Gazebo / ROS 日志及 `session.json`，关闭窗口或 Ctrl+C 后只收尾本次创建的进程组。

完整模型使用厂家 HUNTER2 分体 CAD 和本车上装，4 个滚动、2 个转向关节；涂装和部分覆盖件未按照片一比一复原。雷达 720 × 32 / 10 Hz、RGBD 640 × 480 / 5 Hz、IMU 50 Hz 是设置频率，不是实测运行速度；暂停时传感器不连续出帧。ARS548、GNSS 只有外形与 TF。质量、摩擦、IMU 与名义外参未标定。这是模型传感器验收场景，没有加载旧实验室地图。

静态原生传感器、ROS、TF、2D scan 的验收记录见 [full_sensors/check.json](../../outputs/hunter_model_upgrade_20261030/references/full_sensors/84f73c45b8fb/check.json)；仿真时间 0 的 [近景截图](../../outputs/hunter_model_upgrade_20261030/references/full_preview/e431bbcda444/render.png) 已视觉核对。旧 `run_straight_test.bash` 只针对旧简化世界，不能用于新完整模型。旧原始控制入口和运动回归文件保持历史用途。

以下原文为历史记录；其中旧 logged 入口的行为现已由上述新说明替代。

---

# 个人Gazebo检查与虚拟直行

这些入口用于个人WSL Ubuntu-22.04的aphelios用户。用户已于2026-10-14明确授权虚拟车低速运动测试；任何实车动作仍未授权。未加载硬件SDK、CAN或ROS/Gazebo桥接。

若终端提示符是PS C:\...>，当前处于Windows PowerShell，直接运行bash可能调用w64devkit等Windows工具，无法识别/mnt/f路径。请显式通过WSL执行；终端A使用`wsl.exe -d Ubuntu-22.04 -u aphelios --exec /bin/bash /mnt/f/rob-memory/sim/tools/start_control_scene.bash`打开暂停场景。窗口正常显示后，在另一个PowerShell终端B使用`wsl.exe -d Ubuntu-22.04 -u aphelios --exec /bin/bash /mnt/f/rob-memory/sim/tools/run_straight_test.bash`运行已授权的虚拟直行。后者会使虚拟车移动。WSL内的aphelios@...提示符则可直接使用后文Bash入口。

`start_control_scene.bash`打开已检查的暂停场景，GUI使用ogre兼容渲染，保留NVIDIA选择；不发布速度。保留该窗口，在另一个WSL终端运行`run_straight_test.bash`，它会使虚拟车移动。测试期间不要手动点击播放或修改模型/物理属性。

直行固定为目标0.10m/s、2000步驱动、零目标1000步收尾，步长0.001s，共推进3个仿真秒；结束再次清零并请求暂停。仿真时间与终端等待的实际时间不同，进程连接和场景查询会增加等待时间。没有可自选的速度、话题、时长或运行参数。

运行前读取实际世界SDF、暂停状态和服务公告。要求唯一控制服务和SDF服务来自同一进程、公告为127.0.0.1；运行模型、插件、话题和物理步长须与本阶段配置一致，已有速度发布者或桥接进程时拒绝运行。`run_straight_test.bash --check`只查询状态和文件，不创建速度发布器、不推进物理；它也读取上次中断记录，在同一服务器仍需重启时明确拒绝，避免只读检查通过而运动入口随后拒绝的提示差异。

底层工具只链接Gazebo Transport和protobuf消息库，不使用ROS运动消息。C++侧采用固定操作、固定话题和有限步数；multi_step请求超时后不重发，因为迟到的请求仍可能执行。Python侧无论测试中断或失败，都分别尝试零目标和暂停收尾。若收尾失败或多步测试中断，记录要求重新启动自己电脑中的场景，再开始新测试；同一服务器进程的再次运动请求会被拒绝。任何工具都不能保证进程被强制终止或仿真服务失联时仍能收到收尾消息。

2026-10-15发现一次步进实际执行而回复丢失：仿真推进2000步/2秒、车体前进0.174648m，客户端却超时，服务端记录Host unreachable。Transport11.4.2在执行回调之后才建立反向回复连接。现每个世界控制操作先在同一Node上读取同一服务器、同一端点的SDF，确认回复路径；仅此只读请求可在超时后再试一次，明确拒绝则立即终止，握手未通过时不发送世界控制。握手期间世界状态变化也拒绝步进。世界控制仍只尝试一次，回复超时仍按失败收尾，不能把已经执行的步骤重发。

原生状态等待6秒、只读握手最多2×5秒、控制回复5秒及步进完成22秒均有上限，Python单操作外层上限相应由35秒改为50秒。它是通信等待上限，不是让虚拟车连续运动50秒；驱动与停止仍为固定2000/1000步。

test_transport_reply_warmup.cc/.py在独立分区提供纯消息接口，没有Gazebo物理世界或速度发布；验证握手先于控制、首个只读回复迟到时只重试读取、读取被拒绝时控制请求为0。修改后这三项及原9项协调器检查通过。独立Gazebo完整直行也通过，记录references/straight_fixtures/ef5feefc937b：前进0.199698m、末端轮式速度0、推进3秒并暂停。当前用户GUI仅执行保持暂停的通信验证，仍为2秒/2000步，失败运动日志未改；不能据此宣称用户界面中的完整运动已验证。

记录在/home/aphelios/hz_sim_ws/reports/straight_*下，处于F盘的WSL虚拟磁盘内。每次保留传输stdout/stderr、运行前后世界SDF与状态、世界位姿变化、仿真时间及末端轮式里程计速度。straight_last_motion.json保留最近的运动结果，不会被仅检查模式覆盖。位姿来自仿真生成的当前世界SDF，角度/位移具有导出精度限制；轮式里程计速度是估计值。

2026-10-14独立无界面分区首次测试：前进0.199698m、侧移及偏航变化记录为0、末端轮式速度0、仿真推进3s，零目标/暂停收尾成功。该服务器与用户原窗口的服务器进程UUID不同；测试后只关闭创建的测试进程组。详细证据位于执行记录references/straight_fixtures/85327111c742。本结果不代表实车动力学或长期控制性能已经验证。

图形诊断时，在Windows PowerShell直接用`2>&1 | Tee-Object`收集WSL输出曾出现中文乱码和NativeCommandError包装；WSL主机提示与Linux输出使用不同的编码路径。后续可使用`powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'F:\rob-memory\sim\tools\start_control_scene_logged.ps1'`。这个入口临时设置终端UTF-8编码，在WSL内部合并并记录Linux日志，每次生成独立gazebo_graphics_utf8_*.log，退出后恢复终端编码。它沿用用户重启后不再闪烁时的诊断日志设置和原暂停场景；日志开关不是已证实的闪烁修复。当前正常的窗口不必为切换日志入口而重启。附加`-Check`仅执行原入口的文件检查，不启动GUI、ROS节点或运动。

用户可见直行曾因步骤前世界已在运行而拒绝固定步请求，随后清零与暂停成功；该次不能记为通过。用户随后重启并确认整窗不再闪烁，工具只读确认当前实际GUI为D3D12 RTX3050、世界暂停且仿真时间0。暂停窗口的显示正常不等于用户可见直行已通过，下一次运动仍须遵循固定测试与收尾检查。

源文件修改后需检查并更新straight_trial.sha256；入口拒绝源码/二进制摘要不符。build_trial_transport.bash只编译本地传输工具并生成摘要，不执行运动。数据模型不需重新colcon构建。
