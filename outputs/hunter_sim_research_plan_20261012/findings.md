# 核对记录

## 用户目标
- 研一，未来方向为移动操作；当前导师要求熟悉硬件、建图、导航，再学习与部署强化学习。
- 车辆多人共用；电脑端平台必须支持独立课题实验、重复测试和算法迭代，实车用于阶段性验证。
- 导师建议优化师兄已有成果或补齐缺项，并阅读 Verti-WM；是否要求完整论文复现尚不明确。
- 当前先做规划；连接小车后再每次 1～2 条命令，只读探查并等待输出。

## 本地硬件（只读查询）
- Windows 11 Pro，i5-11260H，约 16 GB RAM。
- NVIDIA GeForce RTX 3050 Laptop GPU；nvidia-smi 确认 4096 MiB 显存。
- 2026-10-12 查询空闲空间：C 约 79.5 GiB，F 约 243.0 GiB，数值会变化。

## 已有资料
- hz_ws 工作区备份：F:/Hunter小车AI知识库/hz_ws_backup_XhbvX74j/hz_ws.tar.gz。
- 已只读核对该备份里的 fast_livo、hesai_ros_driver 包名、安装产物、配置与启动助手；备份保留完整。
- E:/robot_lab/建图导航.txt 中列出二维建图、Nav2 和 FAST-LIVO2 的启动命令。文件存在不等于实车导航质量已经验证。
- 文档中的 hunter_description 模型、hunter_nav_odom_ws 导航配置尚未从实车读取；hz_ws 不是整个机器人系统的备份。

## 指定论文（主要事实，后续以全文为准）
- [Verti-WM 原文](https://arxiv.org/html/2609.23118v1)：越野导航世界模型，依赖地形高程/语义信息，基于 Chrono/Verti-Bench 与另一款四轮平台评估。
- 规划启示：普通室内 Gazebo 场景和 Hunter 模型只是基础平台，完整论文复现需另核数据、地形动力学、代码和算力；不能默认两者等价。
- 当前检索未确认明确的作者官方代码仓库、可获取数据或权重，不能据此断言未公开；已读章节未确认实际训练 GPU 型号，不能保证本机能完整复现。

## 平台资料
- [Hunter V2 社区模型及仿真](https://github.com/LCAS/hunter_robot)：URDF、前轮转向控制和 ROS 2 Gazebo 参考工程；软件依赖兼容性需核对。
- [厂商 Hunter 模型目录](https://github.com/agilexrobotics/ugv_gazebo_sim)：有模型资源，旧仿真启动方式不能直接当作当前 ROS 2 配置。
- [Gazebo 与 ROS 版本配对](https://gazebosim.org/docs/harmonic/ros_installation/)：新用户推荐 Ubuntu 24.04、ROS 2 Jazzy、Gazebo Harmonic。Humble 默认配对 Fortress；Humble 与 Harmonic 需要额外适配。个人电脑路线暂定新配对，实车 Humble 保持原状；最终选择须检查现有包兼容性。
- [Gazebo Harmonic 平台说明](https://gazebosim.org/docs/harmonic/)：Windows 原生支持仍有限；规划倾向独立 Ubuntu 环境，WSL2/原生 Linux 需先试运行。
- [WSL Linux 图形应用](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps)：Windows 可承载 Linux 图形应用，实际仿真图形性能尚未验证。
- [Gymnasium 环境接口](https://gymnasium.farama.org/introduction/basic_usage/)与 [Stable-Baselines3 PPO](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html)：可用于定义交互环境和训练入门策略；本计划选用它们是实施建议，不是性能优于其他算法的结论。
- [ROS 2 rosbag2](https://github.com/ros2/rosbag2)：原始话题记录可供离线回放；PCD 导出图不等价于同步传感器数据包，固定回放不能直接替代响应新动作的交互环境。

## 路线决策（规划建议，未实施）
- 两层平台：ROS/Gazebo 导航底座与强化学习实验接口。先建立可测量的传统导航基线，再训练和比较一个控制策略。
- 首期场景围绕实验室几何与障碍布局；越野地形、世界模型完整复现和机械臂联合控制作为条件明确后的扩展。
- 小车可用时做只读资产提取及分阶段实测；电脑承担日常迭代。复杂训练预留服务器入口，不将每轮训练绑定共享小车。
- 复制的启动助手绑定实车主机、绝对路径与硬件；仿真需新的独立启动配置与数据适配，不能直接执行该助手来获得仿真。

## 检索限制
- 首次宽泛检索出现第三方论文解读；规划的论文事实仅取自 arXiv 原文。
- 多源输出过长发生截断，后续只读取论文所需章节，避免据未看到的内容推断。
- Nav2 setup_guides 官方页面一次读取返回 InternalError；未把失败抓取当作已验证文档或运行证据。
