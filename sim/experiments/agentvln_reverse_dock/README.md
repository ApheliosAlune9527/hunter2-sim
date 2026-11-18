# HUNTER 2.0 AgentVLN 倒车停靠联合验收

本入口复用 D 盘 AgentVLN 主线的双蓝箱场景、RGB-D、TF 和观察逻辑。从世界原始出生点 `(-0.21, -0.77, 0)` 开始，AMCL 只在起点用已知出生位姿初始化。同一轮依次行驶观察、在线选箱、估计箱面、行驶调整、直进停靠。

## 决策与验收

1. 出生点画面只有一只蓝箱时，用原观察位候选规划前进路径。画面出现两只可分离的箱子后，在观察位停稳并保存同步 RGB-D、相机内参、相机到地图的 TF 和编号图。
2. 本地 Qwen2.5-VL-3B-Instruct F16 接收编号 RGB、中文指令和实测深度排序，返回画面左右位置与候选编号。程序核对编号与左右位置、指令与测距顺序。回执有误就结束本轮。图像推理服务的临时 HTTP 错误可在停车状态重试两次。
3. 根据选中区域的深度和同帧 TF 拟合箱面，用箱面法线和车头包络生成停车目标。标称车头间隔为 0.35 m。固定的调整区入口来自原房间里的独立倒车试验，实时轨迹由规划器计算。
4. 倒车技能移植自侧线的 Reeds–Shepp 规划、RPP 分段跟踪和足迹净空审计。每段结束先用速度和真值位移确认停稳，再从实际 AMCL 位姿规划下一段。摆正且直进可行时立即直进停靠。中间点允许在 0.105 m 内停车，所以执行的倒车段至少规划 0.50 m。停车后需要更多调整时，只有通过净空检查的新路线才会执行。
5. Gazebo 真值用于定位误差监测、停止确认和独立终态验收。规划与控制使用 AMCL TF 和轮式里程计。场景静态矩形用来筛查规划路径并审计实际轨迹。几何审计采用与侧线一致的固定车体矩形和障碍包络，Gazebo 接触事件标记为 `not_measured`。

规划净空阈值为 0.13 m，实测接近 0.07 m 时取消动作并停车。定位误差门限为 0.15 m 和 0.12 rad，定位或里程计反馈过期也会停车。终态验收要求目标正确、Nav2 成功、横向偏差不超过 0.11 m、朝向误差不超过 0.13 rad、车头距箱面 0.23–0.50 m 并停稳。

## 配置与复跑

在 WSL Ubuntu 22.04 的 `aphelios` 终端运行。Windows 侧同一基座模型服务使用 `127.0.0.1:18081`，启动器先查健康状态。启动器独占 ROS 域 74，CycloneDDS 只走本机，Gazebo 分区每轮新建。速度桥的唯一方向为 `/cmd_vel` 到虚拟底盘的 `/hz_sim/lab/cmd_vel`。传感器使用 CPU 渲染，VLM 继续使用 Windows Vulkan 显卡服务。

```bash
bash /mnt/d/rob-memory/sim/experiments/agentvln_reverse_dock/run_episode.bash "/mnt/d/rob-memory/outputs/agentvln_reverse_dock_$(date +%Y%m%d_%H%M%S)_amcl"
```

启动时校验冻结输入。生成的两份配置、输入哈希、运行时参数读回、进程登记和每轮报告随本轮结果保存。原 `agentvln_hunter` 的入口与冻结 Nav2 参数可继续用于只前进对照。副本里的 Dubins 和 Reeds–Shepp 在两个进程里运行，报告另存同一 AMCL 位姿与同一测量箱面的 Dubins 停靠可规划性检查。

实验副本沿用侧线的 1.669 m 最小转弯半径，线速度上下限为 ±0.12 m/s，关闭原地转向，启用 RPP 碰撞检测。全局代价地图给足迹增加 0.075 m padding，并使用 0.68 m 膨胀半径。静态场景启用 `first_map_only`，以免重复送达同一地图时 AMCL 重建激光模型。 [Nav2 Humble 的地图处理](https://github.com/ros-navigation/navigation2/blob/humble/nav2_amcl/src/amcl_node.cpp#L1285-L1319)

`report.json` 含在线模型请求、箱面拟合、每段前进与倒车距离、换向停稳、几何净空、定位误差和终态。失败也保留当轮目录。退出时按本轮进程登记和分区清理，`remaining_processes.txt` 供复查。

## 录屏预览

在 WSL 交互终端给同一入口加 `RECORD=1`，并使用新的输出目录。Gazebo 先用斜俯视角显示原始出生点，终端等待开始信号，此时可以取景并启动录屏。预览窗口使用系统默认渲染，优先选择 Radeon，仿真传感器仍使用 CPU 渲染。窗口的视角和背景配置随该轮输出保存。回到终端按回车后，本轮使用相同的 AMCL、在线 VLM 和倒车停靠流程。任务结束后，窗口继续显示最终位姿，停止录屏后按回车清理本轮。
## 2026-11-10 联合验收

最后一轮使用 CPU 渲染、AMCL 和在线 VLM，从原始出生点完整通过。出生点图像只检测到一只蓝箱，行驶后观测到两只。模型响应为 `side=left, candidate_id=0`，同帧实测光轴深度为近箱 4.082 m、远箱 4.303 m。箱面拟合来自选中区域，报告按场景真值确认目标为远蓝箱。记录里的车体位姿重置数为 0，相邻动作段之间的真值位置连续。

| 项目 | 实测 |
| --- | --- |
| 观察前进、驶入调整区 | 1.083 m、2.219 m |
| 四段倒车 | 0.423 m、0.428 m、0.686 m、0.423 m |
| 末段 | 正向 1.629 m，路线结尾规划直进 0.629 m |
| 各段动作与停稳 | 10 段均为 `SUCCEEDED` 且停稳，终点 1 s 内真值位移 0.2 mm |
| 全程最小几何净空 | 14.9 cm，最近处为红牌的视觉避让包络 |
| 桌边几何净空 | 最小 16.4 cm。旧录屏在同一障碍处回算为 6.7 cm 重叠 |
| 最终横向偏差、朝向、车头距箱面 | 1.0 cm、4.8°、44.6 cm |
| AMCL 与真值的最大位置差 | 9.2 cm |
| 同一调整区位姿的 Dubins 对照 | 当前候选入口中无通过规划净空检查的路线 |

[完整通过的报告](D:/rob-memory/outputs/agentvln_reverse_dock_20261110_014756_amcl/report.json) · [终端记录](D:/rob-memory/outputs/agentvln_reverse_dock_20261110_014756_amcl/episode.log) · [现场编号图](D:/rob-memory/outputs/agentvln_reverse_dock_20261110_014756_amcl/observation_numbered.png)

调试轮分别保留了 [模型选错后停稳](D:/rob-memory/outputs/agentvln_reverse_dock_20261110_013348_amcl/report.json)、[末段定位反馈过期后取消](D:/rob-memory/outputs/agentvln_reverse_dock_20261110_013619_amcl/report.json)、[推理端图像编码分配失败](D:/rob-memory/outputs/agentvln_reverse_dock_20261110_014044_amcl/report.json)、[Gazebo 渲染设备异常](D:/rob-memory/outputs/agentvln_reverse_dock_20261110_014404_amcl/gazebo.log) 和 [退距不足时停车](D:/rob-memory/outputs/agentvln_reverse_dock_20261110_014522_amcl/report.json) 的证据。最终配置目前有一轮完整通过，样本仅覆盖本房间的远箱任务和无界面模式。录像与近箱在线停靠尚待单独验证。

关闭后域 74 无节点，本轮登记的进程均已退出。主线场景、地图、桥接、原入口及冻结参数的哈希核对一致。

---

## 2026-11-10 追记：停车走廊与横向余量的调整

04:20 那一轮在最后一段停车时被安全逻辑取消，原因是parking段的**规划净空只有 0.185 m**，
控制器在 1.2 rad 的末段转弯里切内弯约 0.10 m、航向偏 0.20 rad，执行到的位置净空掉到 **0.0665 m**，
低于BRAKE_GAP=0.07（障碍为北墙 walls/w_141_304）。几何原因：北墙在 y≈3.0，停靠线在 y≈2.38，
车体左沿只剩 0.22 m，而 1.02 m 长的车在 R=1.669 的右转里左前角会外甩约 0.4 m。

按
