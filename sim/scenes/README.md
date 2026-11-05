# 当前默认场景：HUNTER 完整模型（2026-10-30）

`hz_hunter_full.sdf` 与 `hz_hunter_full_gui.config` 是当前完整模型验收场景。推荐入口及两条 PowerShell 命令见 [sim/README.md](../README.md)；默认暂停，本轮请勿点击播放。常用 `start_control_scene_logged.ps1` / `.bash` 现已打开完整模型，旧 `start_control_scene.bash` 和简化世界保留作历史回归。旧 `run_straight_test.bash` 不能用于完整模型。

厂家 HUNTER2 分体 CAD 加本车上装具有 4 个滚动、2 个转向关节，涂装和部分覆盖件尚未按照片一比一复原。该场景没有加载旧实验室地图。传感器设置为雷达 720 × 32 / 10 Hz、RGBD 640 × 480 / 5 Hz、IMU 100 Hz；设置频率不代表实测运行速度，暂停时不连续出帧。IMU 调整依据见[2026-11-05 测量与验证记录](../../outputs/hunter_imu_frequency_20261105/README.md)。ARS548、GNSS 只有外形和 TF；质量、摩擦、IMU 与名义外参未标定。

静态 native + ROS + TF + 2D scan 验收见 [check.json](../../outputs/hunter_model_upgrade_20261030/references/full_sensors/84f73c45b8fb/check.json)；[完整模型近景](../../outputs/hunter_model_upgrade_20261030/references/full_preview/e431bbcda444/render.png) 已视觉核对，预览仿真时间为 0。两组证据分别记录传感器静态验收与暂停外形预览。

以下原文保留旧预览与控制世界的历史说明。

---

# 个人模型初次预览

hz_hunter_preview.sdf是基本平地与简化物理骨架的预览场景，源于已生成和核对的个人模型。它不是实验室地图，也未使用知识库或共享旧地图。车体模型保留7个连杆、6个关节，起始轮心高度0.18m，轮底距地约0.015m。

预览世界只使用本机已安装的Fortress Physics、UserCommands和SceneBroadcaster系统；预览车体没有运动控制插件。当前未启动ROS桥接、底盘驱动、导航或速度发布器。

GUI配置复制自个人WSL已安装软件的默认配置，另保存到此目录；仅调整窗口、相机初始视角和首次欢迎框。原配置未修改。WorldControl的start_paused=true，入口不使用-r，不接受额外启动参数。

启动入口为 `F:\rob-memory\sim\tools\start_paused_scene.bash`。先加载个人环境、核对文件摘要与插件名单，再用无运动指令的检查节点验证当前ROS上下文的域73与回环地址。检查节点销毁后，才打开Gazebo。`--check`模式只校验环境和文件，不创建ROS节点、不启动Gazebo。

文件摘要保存在hz_hunter_preview.sha256。修改场景或GUI后需重新检查并更新清单；入口会拒绝摘要不符的文件。通信检查记录位于/home/aphelios/hz_sim_ws/reports/ros_isolation_latest.json，原始DDS配置日志位于其trace_path。

ROS检查证实该检查上下文实际选择了127.0.0.1接口，不能据此宣称操作系统防火墙或Gazebo Transport网络沙箱已实现。Gazebo继续使用个人逻辑分区和回环公告地址。当前没有可接入实车控制的桥接或驱动。

2026-10-13用户截图确认GUI已显示平地和简化车体，播放按钮与0.00%符合暂停状态。截图已归档至执行记录；这只确认初次渲染，不代表物理运行稳定、帧率已测量或车辆参数已实测。

随后用户反馈重力落地后未见穿模、漂移或翻倒，截图原样归档；按定性观察记录通过。精确运行时间、漂移量和姿态变化未测量，不能据此认定动力学已校准。

## 独立虚拟控制场景

hz_hunter_control.sdf从上述未修改的预览场景派生，骨架、碰撞、质量和地面保持相同；只增加已安装的Fortress 6.18.0 AckermannSteering模型插件。生成工具为sim/tools/create_control_scene.py，校验预览摘要后生成新文件，拒绝覆盖已有场景。此后运行不需要重新构建ROS包。

后轮两个车轮关节受驱动，前轮两个转向关节受控制，前轮绕轴自由滚动。后轮驱动是本轮仿真假设，不代表真实车的驱动结构已经确认。所有惯性、轮胎接触和载荷仍为初始值。

Gazebo Transport话题固定为/hz_sim/cmd_vel、/hz_sim/odom、/hz_sim/tf；帧名为hz_sim/odom和hz_sim/base_link。没有ROS桥接、硬件SDK或CAN访问。沿用个人IGN_PARTITION和公告地址；它们是逻辑分区与公告设置，不能作为操作系统网络隔离的证明。

初始限制为线速度±0.30m/s、角速度±0.30rad/s、线/角加速度分别±0.20m/s²和±0.20rad/s²。该版本插件将同一个速度/加速度参数应用于线量和角量。steering_limit=0.40按插件L/sin(limit)算法产生约1.669m最小后轴转弯半径、最大内侧轮角约0.444rad，在骨架±0.58rad限位内。它不是将每个前轮直接限制到±0.40rad。参数是本轮保守虚拟测试设置，并非实车极限或实测结果。

入口sim/tools/start_control_scene.bash校验摘要、插件/关节/话题/范围和暂停GUI；--check仅处理文件。常规入口先运行并销毁短时ROS检查节点，再打开暂停的Gazebo。没有-r参数，不转发额外参数，也不发布速度。控制器加载已确认，运动质量仍待后续虚拟测试。

用户第一次启动控制场景时，OGRE2在GL3PlusTextureGpu::copyTo抛出UnimplementedException。实际渲染日志显示NVIDIA D3D12/OpenGL4.2、存在GL_NV_copy_image但缺少GL_ARB_copy_image；对应OGRE2源码需要OpenGL4.3或ARB扩展，NV路径仍是未实现注释。为保持当前WSL版本，另存hz_hunter_control_gui.config，只把界面渲染引擎改为已安装的ogre，并在入口明确传入--render-engine-gui ogre。原预览GUI与系统默认配置未改，控制世界SDF摘要保持原值。

修正后8项文件/入口检查通过。工具端短时启动并保持暂停，收到paused=true和sim_time=0，通过Gazebo截图服务确认网格/车体图像，新ogre.log仍显示RTX3050；随后只关闭工具端创建的进程组。证据位于执行记录references/render_checks/8c8acbfb1a。本次确认短时启动与显示，不代表长期运行性能或虚拟运动质量已经验证。

用户随后重新打开并确认窗口正常保留。当前只读状态仍为暂停、仿真时间0，尚未向虚拟控制器发送速度。首次低速直行的范围已写入执行记录，先说明会使虚拟车移动并等待用户明确授权；不会将虚拟测试授权扩大为实车动作。

Fortress此控制器会保留最近一次速度目标，源码没有命令过期停止逻辑。后续虚拟运动测试必须采用有时限且含停止/暂停收尾的独立工具；本轮尚未提供发布命令。插件的轮式里程计根据后轮转角和左右前轮角的平均值积分，不是世界坐标真值，后续需要与仿真位姿对照。官方版本源码副本及来源见执行记录references/upstream。
