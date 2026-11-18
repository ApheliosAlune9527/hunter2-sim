# 第 3 步证据索引（agentvln_hunter, 2026-11-08）

场景版本：`scenes/lab_agentvln_targets.sdf` sha256
`d55f97be801c249b731e3a2c8ce4e84d788b93c74cafb2ec46617c0586dad385`，
布局 `config/target_layout.json` sha256
`d059d67d4a0403c1d6c40624e2a862709d81051985b84ae727c65b6c3619c41d`。

## 当前有效（最终场景）

| 目录 | 内容 | 结论 |
| --- | --- | --- |
| `pipeline_v10/` | 完整闭环：初始观察 → 再观察到 (2.0, 0.5, 0.522) → 两箱深度查询 → 选远箱 → 反投影 (5.324, 1.941) → 直进停靠 (4.363, 1.508, 0.424) → 验收 | status 4，停车区距离 0.266 m，朝向误差 0.048 rad，停稳 0.036 m，成功 |
| `pipeline_v11/` | 同上，第 2 次重复 | 0.262 m / 0.048 rad / 0.035 m，成功 |
| `pipeline_v12/` | 同上，第 3 次重复 | 0.261 m / 0.014 rad / 0.033 m，成功 |
| `spawn_view_v2/` | spawn 处相机帧与已知道具投影（牌面 u=168.7, v=90.6） | 投影与深度一致 |

每个 pipeline 目录包含：`initial.png`（spawn 帧）、`reobserve_1.png`（再观察末帧）、
`annotated.png`（带深度标注与选中箱）、`observation.png`（原图）、`depth.npy`
（32FC1，米）、`report.json`（阶段、连通域、深度查询、停靠候选、执行与验收）。

## 失败样例（同一场景演化过程，保留原因）

| 目录 | 结论 |
| --- | --- |
| `pipeline/` | 红牌立柱进代价地图，再观察首段规划失败（safe end） |
| `pipeline_v2/` | 同上，AMCL 仍漂移 0.126 m |
| `pipeline_v3/` | 观察位姿 (3.185, 1.235) 只见 1 个连通域（近箱挡住远箱） |
| `pipeline_v4/` | 目标 (2.4, 1.0) 与出发朝向差 20°，S 弯不可行，开出 0.3 m 后失败 |
| `pipeline_v5/` `pipeline_v6/` | 停靠朝向与接近方向差 0.4–0.5 rad，最后 0.6 m 需要 1.31 m 转弯半径，失败 |
| `pipeline_v7/` | 近箱压在接近线上，25 个候选全部压箱被剔除 |
| `pipeline_v8/` | 到点成功（朝向误差 0.012 rad），停车区距离 0.321 m 超差 |
| `pipeline_v9/` | AMCL 种子丢失，规划从上一次终点出发，车未动 |
| `probe_at_short/` | 早期短位姿观察（仅作诊断） |

## 更早（旧场景，仅作历史）

`camera_check/`、`observation*/ `、`dock_query*/`、`spawn_view/` 采集于近箱尚在
(4.70, 1.15)、红牌落地、观察位姿 (3.185, 1.235) 的版本；`dock_query_v3/` 是唯一
在那版场景里用 `NavigateToPose` 停进停车区的样例（底盘真值 (4.190, 1.779)，
停车区距离 0.064 m），保留用于对比"从外部给定观察位姿"与"闭环自行到达观察位姿"
的差别。它们不能与当前场景的哈希混用。

## 复现

见 `sim/experiments/agentvln_hunter/README_step3.md` 第 5 节。
