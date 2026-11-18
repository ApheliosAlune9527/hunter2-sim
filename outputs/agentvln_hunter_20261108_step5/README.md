# 本轮增量（VLM 接入）证据索引 — 2026-11-08

方案：`sim/experiments/agentvln_hunter/PLAN_vlm_step.md`

## 1. 本机推理后端核对（第 1 步）

`vlm_backend_probe.log`（19:12 复查）：无 rocminfo/rocm-smi、无 vulkaninfo、无
nvidia-smi；torch / transformers / llama_cpp / ollama / qwen_vl_utils 全部 False；
`$HOME/.cache/huggingface` 为空；无 llama.cpp 可执行文件。

结论：**本机仍无可用图像推理后端**。按方案把"实际 VLM 验收"标为**待测**
（`selection_trials/vlm_probe/result.json` = `backend_unavailable`），先交回放素材与接口。

## 2. 回放接口（第 1 步后半）

`sim/experiments/agentvln_hunter/tools/step5_agent.py`：输入一帧（rgb.png、depth.npy、
report.json 里的编号/bbox/像素区域）+ 一句指令，输出结构化决策。可用的决策：

| decision | 字段 | 含义 |
| --- | --- | --- |
| `query_depth` | `candidate_id` | 查询该候选区域的深度；执行器从深度图取 25×25 中值并回传 `depth_median_m`/`unit`/`valid_pixels`/`valid_fraction` |
| `select_target` | `candidate_id` | 选定目标编号，结束选择 |
| `request_reobserve` | `reason` | 要求换位观察（在线闭环里由执行器换成可达观察位姿） |
| `finish` | `reason` | 结束 |

后端 `--backend`：`area`（无深度，小像面积=远）、`depth`（先查两处再取大深度）、
`replay`（逐条执行 `--decisions` 的 JSON，这就是 VLM 输出槽）、`vlm`（当前返回
`backend_unavailable`）。每一步（动作、工具返回、耗时）都写进 `result.json` 的
`trace`，`model_calls` 单独计。

## 3. 能区分面积规则和深度查询的素材（第 2 步）

| 场景 | 世界 / 布局 | 近箱 | 远箱 |
| --- | --- | --- | --- |
| bigfar | `lab_agentvln_bigfar.sdf` `46123765…` / `9e4a7e03…` | (4.50,1.20) 0.30×0.30×0.80，1.73 m，33 104 px | (5.10,2.60) 0.80×0.80×1.40，2.62 m，**66 907 px** |
| swap | `lab_agentvln_bigfar_swap.sdf` `72aa8e61…` / `e7962f4d…` | (4.50,1.20) 0.80×0.80×1.40 | (5.10,2.60) 0.30×0.30×0.80 |

bigfar 里**远箱在图像里大 2.02 倍**；swap 把两箱对调，远箱反过来更小。

## 4. 选择试验（同一帧、同一指令、只改判据来源）

| 场景 | 指令 | 面积代理（无深度） | 深度查询 |
| --- | --- | --- | --- |
| bigfar | 较远的蓝箱 | 选 #1（实际 blue_near，1.73 m）✗ | 选 #0（blue_far，2.62 m）✓ |
| bigfar | 较近的蓝箱 | 选 #0（实际 blue_far，2.62 m）✗ | 选 #1（blue_near，1.73 m）✓ |
| swap | 较远的蓝箱 | 选 #1（blue_far）✓ | 选 #1（blue_far）✓ |
| swap | 较近的蓝箱 | 选 #0（blue_near）✓ | 选 #0（blue_near）✓ |

合计：**面积代理 2/4，深度 4/4**。面积规则在 bigfar 上两问全错、在 swap 上两问全对
——说明它跟着"看起来多大"走；深度查询两场景都稳定。这就是接 VLM 之后的对照基线。

每轮目录含 `result.json`（含 trace、候选→真值标签、查询值、耗时）：
`selection_trials/{far,near}_{area,depth}/`、`selection_trials_swap/...`、
帧目录 `bigfar_frame/`、`bigfar_swap_frame/`。

## 5. 回放通路验证

`selection_trials/replay_far/decisions.json` 是一份人工写的"VLM 输出"（查两处深度 →
选 #0），用 `--backend replay` 跑通：执行器返回 0→2.6172 m、1→1.7304 m，选中 #0
（blue_far，正确）。这条路径就是接真模型时要走的槽位。

## 5.1 在线跑（第 3 步开始，未通过）

用 step-5 场景（swap）把选箱决策接回 `step3_pipeline.py`（新增 `--select depth|area`、
`--instruction far|near`，并按指令切换停车区）：

| 运行 | 选中目标 | 结果 |
| --- | --- | --- |
| `online_depth` | 3.06 m（远箱，正确） | 停靠段 status 6，停靠点 (3.93,1.92)，车停在 (3.53,1.70)，距停车区 0.69 m |
| `online_area` | 3.00 m（swap 场景下面积规则也指向远箱） | status 6，停在 (3.00,1.24) |
| `online_depth2`（回退扫描版重试） | 3.02 m（远箱） | 3 次尝试都 status 6，车一直停在 (3.05,1.23) |

原因已定位：`nav2.log` 里是 `RegulatedPurePursuitController detected collision ahead!` +
`Controller patience exceeded`。swap 场景的近箱（大箱 0.8×0.8）在 (4.5,1.2)，距远箱
停靠点 (3.98,1.84) 只有 0.8 m，正好压在停靠走廊的局部代价地图里，控制器拒绝前进。
换句话说：**选择环节已经跑通，停靠环节被新场景的布局卡住**，与选箱判据无关。

## 6. 状态

- 已完成：后端核对、回放接口（4 种后端 + 结构化决策 + trace）、回放通路验证、
  两组场景与回放帧、面积 vs 深度的配对数字。
- 待测：真实 VLM 单帧推理与在线闭环（无后端）。
- 下一步：
  1. 调整 step-5 场景布局：把近箱移出远箱停靠走廊（保持它在相机视野内），或把观察位姿
     南移让更低的近箱仍可入画，使在线停靠可用；
  2. 用 `--backend replay` 的决策 JSON 驱动一次完整在线跑（查深度 → 选箱 → 停靠）；
  3. 有后端后把同一份输入喂给模型，对比选择正确率与耗时。
