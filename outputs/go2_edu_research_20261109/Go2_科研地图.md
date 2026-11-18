# Go2 科研地图：一台 Go2 EDU 能做什么

整理日期：2026-11-09。数据来源：老师共享的 [Unitree 论文库](https://drive.google.com/drive/folders/1kdnYQYLmXowZmfyf9rPgQZ9GcDibHaWS?usp=sharing) + Unitree 官方资料 + 本实验室已有 Hunter/AgentVLN 资产。

> 结论先行：**Go2 已经从"怎么让它走"变成"让它去做什么"的平台。** 库里四足论文的主战场是运动控制/RL（190 篇主类），但 Go2 相关论文里最多的是**导航（62）**，其次是**运动 RL（47）**、**VLN/VLA（34）**、**loco-manipulation（26）**。一台 Go2 EDU 足以支撑"导航 + 语言 + 学习型避障 + 状态估计"这条线；多机、操作、高动态运动需要额外硬件或仿真。

---

## 0. 数据与方法（先看可信度）

### 0.1 实际清点结果

| 目录 | 你给的消息 | 我实际清点（2026-11-09） | 编号范围 |
|---|---|---|---|
| 四足 `paper-video-quadruped` | 576 篇 | **666 个论文文件夹** | 1–671（有 6 个空号） |
| 人形 `paper-video-humanoid` | 437 篇 | **632 个论文文件夹** | 1–632（有 1 个空号） |
| 合计 | 1013 | **1298** |  |

差异原因：老师消息里的数字大概率是上一次统计；网盘里实际又多了约 285 个条目。另外库内有重复条目（例如 `200.Jailbreaking LLM-Controlled Robots` 与 `218.Jailbreaking LLM-Controlled Robots` 是同一篇），所以"文件夹数"略高于"去重论文数"。

> 建议向老师确认一句："网盘现在四足 666、人形 632，以哪个版本为准？" 这不影响下面的趋势判断。

### 0.2 方法

1. 用 Google Drive 的 `embeddedfolderview` 接口抓取两个目录的**全部**条目（标题、编号、文件夹链接）。
2. 下载两份双语摘要 docx（各 3–4 MB），抽取文本。
3. 以标题关键词做**多标签粗分类**（14 类），再按优先级取主类；对"摘要里出现 Go2"的条目单独抽取。
4. 对重点论文回读摘要原文，核对平台、传感器、算力、实验设置。

**局限：**

- 分类是关键词规则，不是人工精读；"导航 62 篇"应理解为"标题/摘要里出现导航相关词且提到 Go2 的条目"，不是严格文献计量。
- 双语摘要是老师团队写的**中文介绍**，不是论文原摘要；有些条目有重复、合并、机器翻译痕迹。
- 没有年份字段。库内编号大致按收录时间递增（早期 Laikago/Go1，后期 Go2），但只能作趋势参考。
- 部分论文有"视频"子目录，本轮没有逐个下载视频。

---

## 1. 库的整体形状

### 1.1 四足（666）

| 主类 | 数量 | 说明 |
|---|---:|---|
| 运动控制 / RL | 190 | 步态、地形、sim2real、parkour、CPG |
| 导航 | 143 | SLAM、规划、避障、探索、社会导航 |
| VLN / VLA / Agent | 84 | 语言导航、VLM 规划、Agent 框架 |
| Loco-manipulation | 78 | 带臂、用腿操作、负载运输 |
| 控制/MPC/状态估计 | 43 | 传统控制、MPC、WBC |
| 感知 | 30 | 检测、分割、点云、视觉 |
| 其他 | 98 | 人形迁移、硬件、安全、应用等 |

### 1.2 人形（632）

| 主类 | 数量 |
|---|---:|
| 人形全身控制 | 335 |
| 操作 / 移动操作 | 141 |
| VLN / VLA | 43 |
| 运动 RL | 34 |
| 导航 | 12 |
| 其他 | 67 |

人形库和你们当前的 Go2 没有直接硬件关系，但有两点价值：

1. **方法迁移**：人形全身控制里的 RL、motion tracking、sim2real 方法，可以迁移到四足；
2. **选题避坑**：如果以后要买人形，这份库已经是现成的路线图。

### 1.3 Go2 的存在感

- 四足摘要文本里 **441 行**提到 Go2，去重后 **228 个摘要块**；清洗掉句子碎片、并只保留能匹配到论文文件夹的条目后，得到 **217 条**（对应 217 个论文文件夹）；
- 这 217 条里，有编号的 213 条中有 210 条（98.6%）位于 200 号以后（按全部 217 条算约 97%）。**如果编号大致按收录时间递增**（库内前 100 号确实是 Laikago/Go1 时代的工作），这说明新收录的论文里 Go2 占比极高，**Go2 是"新一代"论文的默认平台**；
- 按主类：导航 62、运动 RL 47、VLN/VLA 34、loco-manipulation 26、控制/状态估计 12、感知 4、其他 32。

> 换句话说：**你想得到的四足研究，2024 年以后几乎都有人在 Go2 上做过了。** 选题不能靠"用 Go2 做 X"来成立，必须找到 X 里面还没解决的具体问题。

---

## 2. Go2 在论文里被用来做什么（带证据）

### 2.1 导航与探索（62 篇）

| 论文 | 用 Go2 做了什么 | 对你的意义 |
|---|---|---|
| [469. Autonomous Navigation System for Library Service Robot Based on Unitree Go2 Edu](https://drive.google.com/drive/folders/1wa4G2h_wZpsN760qDT3DmfyBWVWgJPYc) | 直接基于 Go2 EDU + ROS2 + SLAM 做图书馆自主导航 | 最接近"开箱即用"的工程复现对象 |
| [298. REASAN](https://drive.google.com/drive/folders/1_8b3VjnTUgKy3-rkEzEZ8QzMBqFGhMU1) | Go2 + Livox MID-360 + Jetson AGX Orin 64GB，端到端反应式安全导航 | 说明"机载 Orin + 外置雷达"是常见研究配置 |
| [149. Sailing Through Point Clouds](https://drive.google.com/drive/folders/1OApyLy6CwSY34rx6vtVr68St7iF8wYD3) | 点云 CBF 局部规划器，在 B1 和 Go2 上验证 | 安全滤波路线的入门 |
| [620. MSR-SLAM](https://drive.google.com/drive/folders/1R_0GQQybGI5bF7-3-qY0pwK5pr3Aq5Du) | Go2 + 16 线 LiDAR，GPS 拒止环境 LiDAR-惯性 SLAM | 建图/定位基线 |
| [477. Deskewed LiDAR Odometry](https://drive.google.com/drive/folders/1ggg8hGwUKaqoiBleh2H-DPQ8-Xsd8_MT) | 起伏地形下的去畸变 LiDAR 里程计 | 四足特有的运动畸变问题 |
| [340. Contact-Anchored Proprioceptive Odometry](https://drive.google.com/drive/folders/14Q_g4cDyj6rbs_t-GLDIer3v-Bswe8_V) | 用足端接触做本体里程计 | 无雷达时的备选 |
| [295. GuangMing-Explorer](https://drive.google.com/drive/folders/1stNxc_tNztCePmVQvgKAh9YQZbHsr_5O) | 基于 Go2 的自主探索完整平台 | 探索方向的可复现系统 |
| [519. Learning Agile Navigation in Crowded Environments](https://drive.google.com/drive/folders/1tAhJuRnNPZdMpF9RF_dUzjf6ne-s1YFp) | VOP-Nav，Go2 室内外动态人群导航 | 社会导航入门 |
| [618. Scaffolding Foundation Models into Physical-World Agents](https://drive.google.com/drive/folders/1xoidJVXmYrPk3NHsfAOLW7n-qXSWzEjM) | NavMCP，Go2 实机长时程导航成功率 78.3% | 长时程 + 基础模型的最新参照 |
| [664. CoSMO](https://drive.google.com/drive/folders/1RmV9uRpCDcw8u_5kJcLnQy5mlmEfCoAf) | 共形语义地图 + 安全导航，Go2 实测覆盖率 90.73% | 语义地图 + 安全保证 |
| [613. AVALON](https://drive.google.com/drive/folders/1XrQ13iiGhMYDgxKNiVDNXHf-IivOMQW_) | 零样本室内导航 + 人类拓扑记忆，Go2 上 5/5 成功 | 无需预建图 |

**这条线的现状**：传统 Nav2 已经"够用"；论文的增量主要在**语义、长时程、动态人群、安全保证、零样本**。单纯"用 Nav2 让 Go2 走"没有新意。

### 2.2 运动控制 / 强化学习（47 篇）

| 论文 | 贡献 | 备注 |
|---|---|---|
| [473. StairMaster](https://drive.google.com/drive/folders/1a6U1yTaiQEe7Y9s5ZEvj-TDCjA4W2Dlm) | Go2 零样本爬 55° 镂空楼梯 | 感知运动 + sim2real 的强基线 |
| [595. Transporting Unsecured Stacked Payloads](https://drive.google.com/drive/folders/1blQXuDl1Ytqae4q3I_y6tql-Uzo7_qqW) | Go2 运输无固定堆叠负载，实机成功率 0.850 | 负载/多目标 RL |
| [228. Bipedalism for Quadrupedal Robots](https://drive.google.com/drive/folders/1c_67c0EDpTVgjwXRpnl0TxDtXN1rqSUF) | 让 Go2 用后腿站立，腾出前腿做 loco-manipulation | 不需要机械臂的操作路线 |
| [220. McARL](https://drive.google.com/drive/folders/1dwElnIoeRI2Y13uEUyikFDXWLEGGY-2_) | Go1 训练的策略零样本迁移到 Go2，3.5 m/s | 跨形态迁移 |
| [468. Kine2Go](https://drive.google.com/drive/folders/13KU3-mQqL4oM5PAsHmJj1geshhWtapLd) | Go2 多步态运动学数据集 | 数据/基准方向 |
| [592. SG-CPG](https://drive.google.com/drive/folders/1eAaMiTF8fZ2u3a-fDoSNeGVCStMZ3YU-) | 执行器退化下的自适应 CPG | 可靠性/容错 |
| [606. PROMO](https://drive.google.com/drive/folders/1f1m4ADymH43IFU7ewth-7OkIkjII4PJU) | 偏好条件多目标 RL | 多目标权衡 |

**这条线的现状**：最卷。没有 NVIDIA GPU 训练条件的话，不建议把"从零训练步态策略"作为主课题；可以**用官方/公开权重做下游**，把 RL 放在"调度/局部决策"层。

### 2.3 VLN / VLA / Agent（34 篇）

| 论文 | 关键事实 |
|---|---|
| [202. NaVILA](https://drive.google.com/drive/folders/1w9WI5wdhZszzae3AJ580W6pIAdVNoOda) | 高层 VLA 生成中层动作 + 低层视觉运动策略；Go2 实机 |
| [392. AgentVLN](https://drive.google.com/drive/folders/1QjJT00H9hmv_NOP_xWMcmsnJy1UQq9S7) | Go2 + Intel D455；VLM-as-Brain + 技能库 + QD-PCoT；面向边缘部署 |
| [323. VLingNav](https://drive.google.com/drive/folders/1lR26w_p_PdlNoGNI-MNXectlC53ueyKp) | 自适应推理 + 语言记忆 + 在线 RL；Go2 + D457 + 远端 4090 |
| [404. DecoVLN](https://drive.google.com/drive/folders/1zOk6uXfa9H3Ev91rTu8caRKPayxBroZP) | Go2 视频流到单张 RTX4090 服务器；记忆选择 + 纠错微调 |
| [514. JOP-VLN](https://drive.google.com/drive/folders/17maStNutA0GkD2tvRKGVIDJuZ0mq6S5I) | 模仿 + DAgger + GRPO；Go2 实机少样本微调 |
| [582. Talk2Escape](https://drive.google.com/drive/folders/1PC6p7rOpojrAmbHT9MyTD66hdXWko-DW) | 失败检测 + 对话式求助 + 恢复；Go2 实机 |
| [273. Co-NavGPT](https://drive.google.com/drive/folders/1u1Xsx2ttFxTZXDb0YYYXctmlBpmxWLvI) | 多机器人 VLM 全局规划；Go2 实机验证 |

**这条线的现状**：**推理框架已经很多，真机长时程可靠性仍然是缺口。** 你们的 AgentVLN-Hunter 资产可以直接迁移，这是最快的起点。

### 2.4 Loco-manipulation（26 篇）

- 带 D1/Z1 臂的移动操作；
- 用腿操作（Bipedalism）；
- 负载运输（PAMORT）；
- 站起/趴下/推门等"用身体"的任务。

**对一台无臂 Go2**：可做"用前腿/身体"的 loco-manipulation，但不要指望精细抓取；有臂则进入另一个硬件预算。

### 2.5 安全、对抗与效率（少量但重要）

| 论文 | 事实 |
|---|---|
| [200/218. Jailbreaking LLM-Controlled Robots](https://drive.google.com/drive/folders/1DsYzVeWtCPohP43C0vAG9JJ3Y7arE7i2) | RoboPAIR 在黑盒 GPT-3.5 控制的 Go2 上实现 100% 越狱成功率 |
| [219. Speculative Edge-Cloud Decoding](https://drive.google.com/drive/folders/1DK6082PV0q8gl0wZFMZl1Pjthu3v0IyN) | Go2 上部署 VLM 控制，边缘-云推测解码提速 21% |

这两篇提示了一个**低竞争、适合单机**的方向：**LLM/VLM 控制机器人的安全与实时性**。

---

## 3. 八条研究路线：单台 Go2 的可行性

评分：★ 越少越容易；"补设备"指除基础 Go2 EDU 外还需要什么。

| # | 路线 | 代表工作 | 单机可行性 | 需要补 | 周期 |
|---|---|---|---|---|---|
| 1 | 自主导航 / 探索 / 语义地图 | 469, 295, 664, 613 | ★★☆ | 无（有 L1/L2 即可） | 4–6 周 |
| 2 | 学习型局部导航 + 安全滤波 | 298, 149, 519, 554 | ★★★ | 仿真 GPU | 6–8 周 |
| 3 | VLN / VLA / Agent 导航 | 202, 392, 323, 404, 582 | ★★★ | 远端 GPU 或 API | 6–10 周 |
| 4 | 单机多 Agent 调度 | 322, 392, 582 | ★★☆ | API 预算 | 8–12 周 |
| 5 | 感知运动（楼梯/parkour） | 473, 417 | ★★★★ | Isaac Lab + NVIDIA | 10–14 周 |
| 6 | 步态 RL / sim2real | 220, 595, 606, 592 | ★★★★ | Isaac Lab + NVIDIA | 10–16 周 |
| 7 | 状态估计 / 本体感知 | 340, 477, 620 | ★★☆ | 无 | 4–6 周 |
| 8 | 社会导航 / HRI | 519, 379 | ★★★ | 标注人员/场景 | 6–10 周 |
| 9 | Loco-manipulation | 228, 595 | ★★★★ | 臂或纯腿操作训练 | 10–16 周 |
| 10 | 多机协同 | 273 | ★★★★★ | 第二台狗或纯仿真 | 8–12 周 |

### 3.1 路线 1：自主导航 / 探索 / 语义地图（最稳的起点）

**问题**：四足在真实室内环境里，定位漂移、动态障碍、楼梯/门槛、语义目标（"去饮水机旁边"）仍然不可靠。

**最小实验**：

- 场景：实验室一层，20 m × 20 m，含走廊、门、桌椅、2–3 个语义目标；
- 任务：给定坐标导航（20 次）、语义目标导航（20 次）、动态行人干扰（10 次）；
- 基线：Nav2 + AMCL；改进：LIO 里程计 + 语义地图 + 失败重定位；
- 指标：SR、SPL、碰撞、接管次数、重定位次数、到点误差。

**产出**：一张可复用的室内地图、一套失败分类、一篇 workshop 级别的系统报告。

### 3.2 路线 2：学习型局部导航 + 安全滤波

**问题**：RL 局部策略在仿真里很好，真机上遇到分布外障碍/动态人时是否比 Nav2 更稳？CBF/安全滤波能否在不牺牲效率的前提下降低碰撞？

**最小实验**：

- 仿真（Isaac/MuJoCo）训练或直接用公开策略；
- 真机三种控制器：Nav2 DWA/MPPI、RL 策略、RL + CBF 滤波；
- 场景：静态杂乱、动态行人、低矮障碍（线缆/箱子）；
- 指标：成功率、碰撞次数、路径长度、平均速度、推理延迟、平滑度（jerk）。

**风险**：RL 训练需要 NVIDIA；真机安全边界要严格。建议先用公开权重做推理对比，不从头训练。

### 3.3 路线 3：VLN / VLA / Agent 导航（你们最强的资产）

**现状**：你们已经在 Hunter 上跑通了 AgentVLN 的本地 VLM 部署（Qwen2.5-VL-3B，llama.cpp + Vulkan，Windows 回环服务 `127.0.0.1:18081`）、Gazebo 场景、Nav2、评测脚本。**迁到 Go2 的增量主要是：**

1. 运动接口：`/cmd_vel` → `SportClient.Move` 桥；
2. 传感器：Hunter 的相机/雷达外参 → Go2 的相机/LiDAR 外参；
3. 场景：轮式能过的门/走廊 → 四足的台阶/门槛/地毯；
4. 安全：四足的急停/摔倒恢复/姿态控制。

**最小实验**：

- 任务：10–20 条室内路线指令（中英双语），每条 3 个地标；
- 基线：单 Agent + 工具 + 记忆（Hunter 现有栈）；
- 改进：拓扑记忆 + 触发式复核 + 失败恢复；
- 指标：SR、SPL、nDTW、接管、调用次数/token、延迟。

**这是最短路径**：不用从零搭栈，直接把 Hunter 的 VLM 服务、任务编排、评测脚本搬过来，替换执行层。

### 3.4 路线 4：单机多 Agent 调度（最适合"一篇论文"的选题）

**问题**：在相同观测、相同工具、相同推理预算下，"按需调用感知/规划/复核角色"是否比"单 Agent"或"固定多 Agent"更好？

**为什么适合**：

- 一台 Go2 就能做闭环；
- 库内直接对比单/多 Agent 的工作很少（322 是建筑任务规划，不是导航）；
- 你们已有 AgentVLN 的单 Agent 基线，加角色和调度器即可；
- 评测可以同时报成功率与成本，故事完整。

**最小实验**：

| 方案 | 调用方式 | 目的 |
|---|---|---|
| B0 | 单 Agent + 工具 + 记忆 | 分工是否真的有用 |
| B1 | 每步固定调用全部角色 | 固定协作的上限与成本 |
| B2 | 规则触发（路口/停滞/低置信） | 简单策略是否够 |
| B3 | 轻量 RL/bandit 学调度 | 学习是否优于规则 |

指标：SR、SPL、恢复率、接管、调用次数、token、P50/P95 延迟、任务时长。

**风险**：API 成本；必须控制"总调用预算"这个变量，否则审稿人会说"你只是多花了钱"。

### 3.5 路线 5–6：感知运动 / 步态 RL（有条件再做）

- 需要 Isaac Lab + NVIDIA GPU（本机没有）；
- 适合有服务器/云预算、且愿意做 sim2real 的组；
- 不建议作为第一个课题。

### 3.6 路线 7：状态估计 / 本体感知（低成本高价值）

- Go2 的足端力、IMU、关节编码器都是现成的；
- 可以做"无雷达/弱雷达"的里程计、打滑检测、负载估计；
- 与导航栈结合紧密，容易出工程论文。

### 3.7 路线 8：社会导航 / HRI（需要人）

- 场景：走廊会人、电梯、导盲/陪伴；
- 需要 IRB/知情同意（如果涉及人）；
- 一台狗 + 几个演员即可做小规模。

### 3.8 路线 9–10：操作 / 多机（门槛最高）

- 操作：加 D1 臂（6 DoF + 夹爪）或走后腿操作路线；
- 多机：第二台 Go2（成本高）或纯仿真 + 单机验证（论文里必须写清楚）。

---

## 4. 一台 Go2 EDU 的可行性矩阵

| 方向 | 单机可做 | 需要额外 | 本机算力 | 建议优先级 |
|---|---|---|---|---|
| 室内导航/建图 | ✅ | 无 | 笔记本够 | 高 |
| 语义/目标导航 | ✅ | 无 | 笔记本/Orin | 高 |
| VLN/VLA 推理 | ✅ | 远端 GPU 或 API | 需要服务器 | 高 |
| 单机多 Agent | ✅ | API 预算 | 笔记本 | 高 |
| 学习型避障 | ✅（推理） | 训练 GPU | 服务器 | 中高 |
| 状态估计 | ✅ | 无 | 笔记本 | 中 |
| 社会导航 | ✅ | 场景/人员 | 笔记本 | 中 |
| 步态 RL | ⚠️ 部署可以 | 训练 GPU | 服务器 | 中低 |
| 感知运动/parkour | ⚠️ | 训练 GPU + 安全场地 | 服务器 | 低 |
| Loco-manipulation | ⚠️ | 臂/训练 | 服务器 | 低 |
| 多机协同 | ❌ 实机 | 第二台狗 | — | 仿真先行 |

---

## 5. 三个可执行选题（含与现有资产的衔接）

### 选题 A（推荐）：长时程语义导航中的"记忆—复核—重规划"触发机制

**一句话**：在有限推理预算下，机器人什么时候该查记忆、什么时候该回头看一眼、什么时候该重新规划？

**为什么现在做**：

- 库内 VLN 论文多，但真机长时程可靠性仍是缺口（NavMCP 78.3%、DecoVLN 强调复合误差、Talk2Escape 专门研究失败求助）；
- 你们已有 AgentVLN-Hunter 的单 Agent 基线、VLM 服务和评测脚本；
- 一台 Go2 足够，不需要第二台或机械臂。

**方法骨架**：

```text
指令 → 规划 Agent（子目标 + 进度）
     → 感知/定位（相机 + LiDAR + 里程计）
     → 拓扑记忆（节点：观测、位姿、时间、置信）
     → 触发式复核（低置信/停滞/偏离/路口）
     → 重规划 or 继续
     → SportClient 执行（限速/超时/急停）
```

**对照**：B0 单 Agent、B1 固定多角色、B2 规则触发、B3 学习触发（可选）。

**评测**：

- 任务：12–20 条路线，每条 3–5 个地标，含 2 个"歧义点"；
- 指标：SR、SPL、nDTW、接管、碰撞、恢复率、调用次数、token、P50/P95 延迟；
- 消融：去记忆、去复核、固定触发。

**8–10 周计划**：

| 周 | 工作 |
|---|---|
| 1 | Go2 上手、数据链路、SportClient 桥 |
| 2 | 把 Hunter 的 VLM 服务接到 Go2 相机 |
| 3 | 单 Agent 基线跑通 5 条路线 |
| 4 | 拓扑记忆 + 触发式复核 |
| 5 | 扩到 12 条路线，采失败数据 |
| 6 | 规则触发 vs 固定协作对比 |
| 7 | 消融 + 补实验 |
| 8–10 | 写作/复跑/可视化 |

**风险**：VLM 延迟（用本地 3B 或缓存）；相机标定；动态行人不可控（用演员/时段控制）。

### 选题 B：学习型局部导航 vs 传统导航的安全—效率权衡

**一句话**：在真实四足上，RL 局部策略 + CBF 安全滤波，能否在动态杂乱环境里超过 Nav2，同时把碰撞降到可接受？

**为什么**：库内这类工作多，但"同一台狗、同一场景、同一评测"的公平对比少；CBF 与 RL 的结合是热点。

**最小实验**：3 个控制器 × 3 类场景 × 10 次；指标 SR/碰撞/路径/速度/延迟。

**风险**：训练算力；真机安全。建议先用公开策略推理，不从头训练。

### 选题 C：单机多 Agent 的"按需协作"调度

**一句话**：把"感知/规划/复核"拆成角色，用规则或轻量 RL 决定何时调用，能否在相同预算下提高长时程导航成功率？

**为什么**：与选题 A 同源，但更聚焦"调度"这一决策问题；库内 322 给了单/多 Agent 对照的实验设计，392/582 给了工具与求助机制。

**注意**：不要把它说成"多智能体强化学习"；如果只训练调度器，就老老实实叫"RL 调度的多 Agent 导航"。

---

## 6. 设备与算力清单

### 6.1 最低配置（能开始）

- Go2 EDU 本体 + 遥控器 + 一块电池 + 快充；
- 一台 Ubuntu 22.04 笔记本（16 GB RAM，独显非必需）；
- 网线、交换机（可选）；
- 一个安全的室内场地。

### 6.2 推荐配置（能发论文）

| 项 | 建议 | 用途 |
|---|---|---|
| 机载计算 | Orin NX 16GB 扩展坞 | 机载感知/小模型 |
| 深度相机 | Intel D435i（若未配） | VLN/避障/点云 |
| 外置雷达 | Livox MID-360 | 建图/定位，Unitree SLAM |
| 训练 GPU | RTX 4090 / A100（实验室服务器） | Isaac Lab、VLM 微调 |
| 推理 GPU | 4090 或 3090 | 本地 VLM 服务 |
| 网络 | 5 GHz Wi-Fi 6 路由器 + 有线 | 低延迟 |
| 安全 | 围挡、急停人、备用电池 | 实验 |

### 6.3 本机的现实

- CPU/内存够做开发、可视化、ROS2；
- AMD RX 9070 XT 可以跑 llama.cpp Vulkan（你们已经在 Hunter 项目里验证过 Qwen2.5-VL-3B）；
- **不能跑 CUDA/Isaac Lab**；训练放服务器。

---

## 7. 阅读路线（24 篇，按顺序）

### 第一周：平台与导航（6 篇）

1. [469. Library Service Robot on Go2 EDU](https://drive.google.com/drive/folders/1wa4G2h_wZpsN760qDT3DmfyBWVWgJPYc) — 看别人怎么把 Go2 EDU 做成导航系统
2. [298. REASAN](https://drive.google.com/drive/folders/1_8b3VjnTUgKy3-rkEzEZ8QzMBqFGhMU1) — 机载配置与安全导航
3. [149. Sailing Through Point Clouds](https://drive.google.com/drive/folders/1OApyLy6CwSY34rx6vtVr68St7iF8wYD3) — CBF 局部规划
4. [620. MSR-SLAM](https://drive.google.com/drive/folders/1R_0GQQybGI5bF7-3-qY0pwK5pr3Aq5Du) — LiDAR-惯性 SLAM
5. [477. Deskewed LiDAR Odometry](https://drive.google.com/drive/folders/1ggg8hGwUKaqoiBleh2H-DPQ8-Xsd8_MT) — 四足运动畸变
6. [340. Contact-Anchored Proprioceptive Odometry](https://drive.google.com/drive/folders/14Q_g4cDyj6rbs_t-GLDIer3v-Bswe8_V) — 本体里程计

### 第二周：长时程与语义导航（6 篇）

7. [618. NavMCP](https://drive.google.com/drive/folders/1xoidJVXmYrPk3NHsfAOLW7n-qXSWzEjM) — 长时程 + 基础模型
8. [664. CoSMO](https://drive.google.com/drive/folders/1RmV9uRpCDcw8u_5kJcLnQy5mlmEfCoAf) — 语义地图 + 安全
9. [613. AVALON](https://drive.google.com/drive/folders/1XrQ13iiGhMYDgxKNiVDNXHf-IivOMQW_) — 零样本 + 拓扑记忆
10. [295. GuangMing-Explorer](https://drive.google.com/drive/folders/1stNxc_tNztCePmVQvgKAh9YQZbHsr_5O) — 自主探索平台
11. [519. VOP-Nav](https://drive.google.com/drive/folders/1tAhJuRnNPZdMpF9RF_dUzjf6ne-s1YFp) — 动态人群
12. [237. Autonomous Navigation and 3D Reconstruction](https://drive.google.com/drive/folders/1ge8P9bJ4rEWtfGlQHmhJ_CKah5n19PLC) — ROS2 + SLAM 工程

### 第三周：VLN/VLA（6 篇）

13. [202. NaVILA](https://drive.google.com/drive/folders/1w9WI5wdhZszzae3AJ580W6pIAdVNoOda) — 分层 VLA
14. [392. AgentVLN](https://drive.google.com/drive/folders/1QjJT00H9hmv_NOP_xWMcmsnJy1UQq9S7) — 你们已在 Hunter 上复现
15. [323. VLingNav](https://drive.google.com/drive/folders/1lR26w_p_PdlNoGNI-MNXectlC53ueyKp) — 自适应推理 + 记忆
16. [404. DecoVLN](https://drive.google.com/drive/folders/1zOk6uXfa9H3Ev91rTu8caRKPayxBroZP) — 记忆选择 + 纠错
17. [582. Talk2Escape](https://drive.google.com/drive/folders/1PC6p7rOpojrAmbHT9MyTD66hdXWko-DW) — 失败求助
18. [514. JOP-VLN](https://drive.google.com/drive/folders/17maStNutA0GkD2tvRKGVIDJuZ0mq6S5I) — 模仿 + RL 训练

### 第四周：运动、安全与多机（6 篇）

19. [473. StairMaster](https://drive.google.com/drive/folders/1a6U1yTaiQEe7Y9s5ZEvj-TDCjA4W2Dlm) — 感知运动
20. [595. PAMORT](https://drive.google.com/drive/folders/1blQXuDl1Ytqae4q3I_y6tql-Uzo7_qqW) — 负载运输
21. [228. Bipedalism](https://drive.google.com/drive/folders/1c_67c0EDpTVgjwXRpnl0TxDtXN1rqSUF) — 用腿操作
22. [200. RoboPAIR](https://drive.google.com/drive/folders/1DsYzVeWtCPohP43C0vAG9JJ3Y7arE7i2) — LLM 控制安全
23. [219. Speculative Decoding](https://drive.google.com/drive/folders/1DK6082PV0q8gl0wZFMZl1Pjthu3v0IyN) — 边缘实时性
24. [273. Co-NavGPT](https://drive.google.com/drive/folders/1u1Xsx2ttFxTZXDb0YYYXctmlBpmxWLvI) — 多机

**读法**：每篇只记 7 项——任务、平台/传感器、输入输出、方法、训练条件、评测、代码/权重。特别标注"是否 Go2 实机""是否需要额外 GPU/雷达"。

---

## 8. 90 天计划

| 阶段 | 周 | 目标 | 交付 |
|---|---|---|---|
| P0 上手 | 1–2 | 网络、DDS、读数据、控速、急停、建图 | 配置表、验收记录、30 s 数据 |
| P1 平台 | 3–4 | Go2 导航栈：LIO + Nav2 + `/cmd_vel` 桥 | 单点导航 20 次结果 |
| P2 迁移 | 5–6 | Hunter 的 VLM/Agent 栈接到 Go2 | 5 条路线单 Agent 基线 |
| P3 方法 | 7–9 | 记忆/复核/重规划触发 | B0/B1/B2 对照 |
| P4 扩展 | 10–12 | 扩到 12–20 条路线、消融、复跑 | 论文初稿/组会报告 |

**里程碑判据**：

- 第 4 周：导航成功率 ≥80%（静态室内，20 次）；
- 第 6 周：单 Agent VLN 在 5 条路线上 SR ≥60%；
- 第 9 周：B2 规则触发相对 B0 有可复现提升（≥10 个百分点或成本显著下降）；
- 第 12 周：结果可复跑、失败可解释。

---

## 9. 风险与学术边界

1. **不要把"用 Go2"当创新**。库里 217 篇用 Go2；创新必须在问题、机制、评测或分析上。
2. **不要混淆仿真/实机**。多机只做了仿真就写"多机协同已在真实环境验证"会被拒。
3. **不要忽略额外传感器**。很多论文的 Go2 配了 MID-360、D455、Orin 64GB、远端 4090；你的复现条件不同，结论要加限定。
4. **不要直接复用 Hunter 参数**。四足 footprint、高度、转弯、台阶都不同。
5. **安全第一**。LLM/VLM 控制的机器人有对抗风险（RoboPAIR 已在 Go2 上验证 100% 越狱）；上线前要有限速、白名单动作、人工急停。
6. **数据合规**。涉及人的实验要知情同意；室内地图可能含敏感布局。

---

## 10. 数据文件说明

| 文件 | 内容 |
|---|---|
| `data/papers_index.csv` | 1298 条：语料、编号、标题、主类、标签、Drive 链接 |
| `data/go2_papers.csv` | 217 条提到 Go2 的四足论文（编号、标题、主类、标签、链接） |
| `data/summary.json` | 分类统计原始数字 |
| `data/quadruped_index.json` / `humanoid_index.json` | 原始目录索引 |
| `data/quad_abstracts.txt` / `hum_abstracts.txt` | 双语摘要纯文本（便于 grep） |

> 所有链接均为 Google Drive 文件夹，需要能访问 Google Drive 的网络环境。

---

## 附：与 Hunter 项目的复用清单

| Hunter 资产 | 能否直接用于 Go2 | 需要改什么 |
|---|---|---|
| AgentVLN 任务编排 | ✅ 大部分 | 执行层接口、坐标系 |
| Qwen2.5-VL-3B 本地服务 | ✅ | 无需改，Go2 客户端调用同一 HTTP |
| Nav2 参数 | ❌ 不能直接用 | footprint、速度、转弯、costmap |
| AMCL/定位 | ⚠️ | 四足里程计噪声不同，需重调 |
| 评测脚本（SR/SPL/接管） | ✅ | 换成 Go2 的到点/碰撞判定 |
| Gazebo 场景 | ⚠️ | 轮式能过的门/坡，四足要重新验证 |
| 失败分类体系 | ✅ | 增加"摔倒/姿态异常/足端打滑" |

**最短路径**：第 5–6 周把 Hunter 的 VLM 服务与任务编排接到 Go2，执行层换成 `SportClient` 桥，先跑 5 条路线，再决定是加记忆/复核，还是转做安全/实时性。

