# Go2 EDU 上手 + 科研地图（2026-11-09）

本目录是"实验室买了 Go2 EDU，先把它摸清楚 + 看科研上能做什么"的一次性调研。
**没有连接实机**：所有实机操作都要等狗到场后按第 10 节清单验收。

## 先读哪份

| 想解决的问题 | 打开 |
|---|---|
| 组会汇报，只要一页 | [Go2_组会汇报.md](Go2_组会汇报.md) |
| 怎么开机、连网、读数据、控速、建图、导航 | [Go2_EDU_上手指南.md](Go2_EDU_上手指南.md) |
| 科研上别人用 Go2 做了什么、我们能做什么、选什么题 | [Go2_科研地图.md](Go2_科研地图.md) |
| 狗到场第一天照着做 | [Go2_第一天验收清单.md](Go2_第一天验收清单.md) |
| 跑状态/录制/控速脚本 | [tools/README.md](tools/README.md) |
| 查某篇论文 | [data/papers_index.csv](data/papers_index.csv) / [data/go2_papers.csv](data/go2_papers.csv) |

## 三个最重要的数字

- 老师给的论文库，实际清点是 **四足 666 篇 + 人形 632 篇 = 1298 篇**（消息里说的 576/437 是旧统计）。
- 其中 **217 篇** 四足论文能匹配到 Go2 相关摘要；按主类：导航 62、运动 RL 47、VLN/VLA 34、loco-manipulation 26。
- Go2 相关论文 94% 位于库内 200 号以后——**Go2 已经是新一代四足论文的默认平台**。

## 三个最重要的判断

1. **先做平台，再做论文。** 第一周只做：有线网络 + DDS + 读数据 + `SportClient` 控速 + 急停 + 一张地图。不要一上来跑别人的仓库。
2. **最短的科研路径是"把 Hunter 的 AgentVLN 栈迁到 Go2"**。你们已经有 Qwen2.5-VL-3B 本地服务、任务编排、Nav2、评测脚本；Go2 只换执行层（`/cmd_vel` → `SportClient.Move`）和传感器外参。
3. **一台 Go2 足够做导航/VLN/学习型避障/状态估计；不够做多机实机、精细操作、从零训练步态。** 训练要 NVIDIA GPU，本机 AMD 9070 XT 只能做推理/开发。

## 目录

```
outputs/go2_edu_research_20261109/
├── README.md                       ← 本文件
├── Go2_EDU_上手指南.md              ← 使用手册（配置/网络/数据/控制/建图/仿真/安全/排障）
├── Go2_科研地图.md                  ← 论文库分析 + 8 条路线 + 3 个选题 + 90 天计划
├── Go2_第一天验收清单.md            ← 一页纸，打印带到实验室
├── data/
│   ├── papers_index.csv            1298 条：语料/编号/标题/主类/标签/Drive 链接
│   ├── go2_papers.csv              217 条 Go2 相关论文
│   ├── summary.json                分类统计
│   ├── quadruped_index.json        四足目录原始索引
│   ├── humanoid_index.json         人形目录原始索引
│   ├── quad_abstracts.txt          四足双语摘要纯文本
│   └── hum_abstracts.txt           人形双语摘要纯文本
├── tools/
│   ├── go2_status.py               只读状态（已用假狗验证）
│   ├── go2_record.py               录 CSV（已用假狗验证）
│   ├── go2_move.py                 安全速度控制（编译/空跑通过，待实机）
│   ├── go2_cmdvel_bridge.py        /cmd_vel → SportClient 桥（ROS2 联调通过，待实机）
│   ├── fake_go2.py                 本地假狗（DDS 发布）
│   └── README.md
├── refs/
│   ├── GO2_User_Manual.pdf         代理商 85 页手册（*.pdf 已被 gitignore）
│   └── GO2_User_Manual.txt         抽取文本
└── drive_index/                    抓取/解析脚本与中间数据
```

## 数据是怎么来的

1. `drive_index/fetch_drive.py` + `parse_efv.py`：抓 Google Drive 目录（`embeddedfolderview`，能一次拿全 666/632 条，不受网页懒加载 50 条限制）。
2. `drive_index/parse_abstracts.py` + `extract_go2.py`：解析双语摘要，抽 Go2 相关块。
3. `drive_index/analyze_papers.py`：标题关键词多标签分类。
4. `drive_index/match_go2.py`：把 Go2 块匹配回论文文件夹，生成 `go2_papers.csv`。

**分类是关键词规则，不是人工精读**；引用具体数字时请保留"约/按标题统计"的限定。

## 已验证 / 未验证

| 项 | 状态 |
|---|---|
| Drive 目录抓取（666/632） | ✅ 已跑通 |
| 双语摘要抽取 | ✅ 已跑通（原文有重复/机翻，已注明） |
| 论文分类 + Go2 子集 | ✅ 已生成 |
| `go2_status.py` / `go2_record.py` | ✅ 在 WSL 里用 `fake_go2.py` 通过真实 DDS 收发验证 |
| `go2_move.py` | ✅ 编译 + `--dry-run` 通过；❌ 未接实机 |
| `go2_cmdvel_bridge.py` | ✅ 在 WSL ROS2 Humble 中收 `/cmd_vel`、限幅、超时停车通过；❌ 未接实机 |
| 实机网络/DDS/控制 | ❌ 未验证（狗不在本机网络） |
| Isaac Lab 训练 | ❌ 本机无 NVIDIA GPU |

## 下一步（狗到场后）

1. 填 `Go2_EDU_上手指南.md` 第 1 节的配置表（重点：有没有 Docking Station / Orin / 深度相机 / 外置雷达）。
2. 按 `Go2_第一天验收清单.md` 走一遍，把勾选结果和命令输出存到本目录的 `logs/`。
3. 跑 `tools/go2_status.py`，确认 `/lowstate` 与 `/sportmodestate` 有数据。
4. 再决定是"先搭导航栈"还是"先迁 AgentVLN"。
