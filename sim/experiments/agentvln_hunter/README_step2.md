# 第 2 步：图像选路与到点技能

状态：2026-11-08 完成工程基线。第 1 步固定 Nav2 + RGB-D 已验收；本步验证“从图像编号选路，再让 Nav2 一段一段到点”的接口和闭环。

## 1. 范围与场景

- 世界仍为 sim/experiments/agentvln_hunter/scenes/lab_agentvln_world.sdf。
- 地图仍为 outputs/lab_nav_fix_20261106/lab_nav_map_fix.yaml。
- 场景里有第 1 步加的 red/green/blue 三个 0.12 m 纯视觉色块，位于 x=1.5、y=-1.05/-0.75/-0.45、z=0.90，无碰撞。它们就是本步的“有辨识度道具”。本步没有再加墙牌；墙牌留到第 3 步按指令语义补。
- 路线覆盖：起步直道到 (1.73,-0.33)，再左转到 (3.27,0.73)，转向角约 0.674 rad（38.6°），HUNTER 可通行。

注意：short/mid 在 PGM 里的原始值可能是 205（unknown），但 live global costmap 已把它们压成 cost 0，且第 1 步已实际到点成功。因此候选过滤以 live costmap 的 cost==0 加 ComputePathToPose 试规划为准，不以 PGM==254 一刀切。

## 2. 候选生成与筛选

代码：sim/experiments/agentvln_hunter/tools/candidate_builder.py

- 在机器人前方扇形采样：距离默认 1.4/1.7/2.0 m，方位默认 -26/-13/0/+13/+26°，最多 18 个。
- 每个候选先做：
  1) footprint 采样：底盘矩形 [[-0.184,-0.393],[0.834,-0.393],[0.834,0.393],[-0.184,0.393]]，按 0.07 m 网格采样，要求所有点 cost==0；
  2) ComputePathToPose 试规划：planner_id=GridBased，显式 start，use_start=true，status==4 且 path.poses>=2；
  3) 路径 cost 检查：按 0.10 m 采样路径，要求 cost==0；
  4) 用图像 stamp 的 TF 投到 RGB，剔除相机后方、画面外、被深度遮挡的候选。
- 通过后返回 Candidate，包含地图位姿 (x,y,yaw)、路径长、试规划状态、footprint 通过、像素 u/v、深度中值、遮挡标记。

起步实测 build_stats：sampled=15、footprint_rejected=6、plan_rejected=2、path_rejected=0、valid=7、visible=6。

## 3. 图像投影与编号

代码：sim/experiments/agentvln_hunter/tools/candidate_view.py

- 用 tf2 将 map 点变到相机光学系：lookup_transform(agentvln_camera_optical_frame, map, image_stamp)，再 do_transform_point。方向写反会得到 u 恒定、v 负几千，这是实际踩过的错误。
- 内参：fx=fy=606.7595825195312、cx=320、cy=240；u=fx*X/Z+cx，v=fy*Y/Z+cy。
- 编号从左到右，叠加圆圈、竖线、编号；selected 用黄色。
- 图像验收：frame 343.0 s、age 0.008、640×480；selected id=3，地图 (1.7214,-0.3259,0.228)，u=117.75、v=305.11，path_length=2.005 m，plan_status=4，expected_range=1.382 m，depth_median=5.176 m（背景，非遮挡）。

### 3.1 地面点不可见，显示信标抬高到 0.5 m

相机水平安装，光心高 0.64 m。走廊内地面点在距离相机 1.6 m 以上时，v 已经超过 480；1.4–2.0 m 的地面候选全部落在画面外（ground_in_frame=false）。为了让“编号候选”在图像上可点选，候选显示点使用 z=0.5 m 的信标，地图执行位姿仍是地面 (x,y,0)。图像上的圆圈/竖线是选路信标，不是要查询深度的目标点；第 3 步的目标深度查询会直接针对目标区域，不用这些信标的高度。

这是本步的工程适配，必须写进复现说明，不能把它当成真实相机俯仰或地面检测结果。

## 4. 结构化决策与执行器

代码：sim/experiments/agentvln_hunter/tools/agent_loop.py

每段流程：

1. wait_new_frame：只接受比上一段新、age<=1.5 s、且 map->base_link 在该图像 stamp 可查的帧；
2. 生成/投影/编号候选；
3. 输出 decision.json；
4. 执行器校验 candidate_id 存在、当前帧 stamp 一致；
5. 再次 ComputePathToPose 试规划；
6. NavigateToPose 只执行这一段；
7. 零速 1 s 测停稳；
8. 取新图，进入下一段。

decision 结构（与以后接 VLM 的接口一致）：

    {
      "decision": "select_candidate",
      "candidate_id": 3,
      "frame_stamp_s": 588.6,
      "instruction": "向左靠近蓝色标记",
      "selector": "color_blue",
      "reason": "color: nearest visible candidate to blue marker in image",
      "candidate_map_pose": [1.7385, -0.3237, 0.2238],
      "distance_to_target_m": 0.326
    }

允许的 decision：select_candidate、request_reobserve、finish。执行器没有直接发速度的接口；所有运动都经过 Nav2。

## 5. 实际运行结果

### 5.1 规则选择（oracle 目标，工程基线）

命令：

    python3 -B tools/agent_loop.py --instruction "沿走廊前进并向左靠近观察点"       --target 1.7 0.0 --max-steps 3 --out outputs/agentvln_hunter_20261108_step2/agent_loop

结果：success=true，steps_executed=1，final_truth (1.6368,-0.3178,0.3600)，final_error 0.3240 m（阈值 0.55），amcl_error 0.1099 m，wall 10.275 s。动作 status=4，路径 2.005 m，停稳位移 0.037–0.044 m。

### 5.2 颜色标记选择（没有 VLM 时的图像驱动基线）

命令：

    python3 -B tools/agent_loop.py --instruction "向左靠近蓝色标记"       --target 1.7 0.0 --selector color_blue --max-steps 3       --out outputs/agentvln_hunter_20261108_step2/agent_loop_color

- 检测蓝色区域：u=143.33、v=89.07、area=7024.5 px、占画面 2.287%；
- 选 candidate_id=3，地图 (1.7385,-0.3237,0.2238)；
- success=true，steps_executed=1，final_truth (1.6309,-0.3070,0.2942)，final_error 0.3147 m，amcl_error 0.0951 m，wall 10.518 s；
- 动作 status=4，路径 2.005 m，停稳 0.0441 m。

这是一条**图像驱动的规则基线**，不是 VLM。标为 engineering baseline，避免把颜色检测当成论文的 VLM-as-Brain。

### 5.3 两段“直道+转弯”演示

命令：

    python3 -B tools/agent_loop.py --instruction "沿走廊前进，绕过墙后向左转，前往转弯后的观察点"       --target 3.286 0.688 --finish-tolerance 0.60 --max-steps 3       --out outputs/agentvln_hunter_20261108_step2/agent_loop_turn

| 段 | 候选地图位姿 | 试规划 | 动作状态 | 路径长 | 时间 | 段后真值 | 段误差 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | (1.7318,-0.3294,0.225) | 4，29 poses | 4 | 2.005 m | 8.661 s | (1.6029,-0.3288,0.3573) | 0.1289 m |
| 1 | (3.2715,0.7334,0.5801) | 4，29 poses | 4 | 2.029 m | 8.372 s | (3.1690,0.6982,0.6756) | 0.1084 m |

最终：success=true，final_truth (3.1915,0.7174,0.6742)，final_error 0.0990 m，amcl_error 0.0813 m，wall 20.577 s；总转向角约 0.674 rad（38.6°）。

### 5.4 失败样例：目标附近过冲

用同一 rule 选择跑 target=(3.185,1.235)、finish-tolerance=0.60、max-steps=4：

- 第 1 段后机器人 (3.1397,0.6143)，到目标距离 0.623 m，刚好超过 0.60 阈值；
- 下一次选择跳到 (4.1012,1.5746)，再跳到 (4.6338,2.7214)；
- 最终 (4.5504,2.6203)，误差 1.945 m，steps_executed=4，success=false。

这是“候选间距大于剩余距离、又缺少过冲保护”的真实失败；第 3/4 步需要在目标附近切换局部停靠，而不是继续选 1.4–2.0 m 的前向候选。证据保留在 agent_loop_mid/。

## 6. 本地 VLM 后端实测

检查脚本：sim/experiments/agentvln_hunter/tools/probe_vlm_backend.bash

结果（2026-11-08）：

- WSL 只看到两个 Microsoft Corporation Device 008e 3D controller，没有直通 AMD Radeon RX 9070 XT；
- rocminfo、rocm-smi、vulkaninfo、nvidia-smi 均不存在；
- Python 没有 torch、transformers、accelerate、bitsandbytes、llama_cpp、ollama、qwen_vl_utils；
- ~/.cache/huggingface 为空；没有 ollama 或 llama.cpp 可执行文件。

因此本步**没有可运行的本地 VLM**，也没有下载 6 GB 级 Qwen2.5-VL-3B 做 CPU 尝试（当前 WSL 只有约 7 GB 内存，CPU 推理不可行）。按用户方案，先用颜色/标志检测跑通闭环，并明确标为工程基线；模型来源和 WSL 后端限制已记录，不用假设冒充 VLM 结果。

## 7. 文件索引

- 候选生成：sim/experiments/agentvln_hunter/tools/candidate_builder.py
- 单帧编号图：sim/experiments/agentvln_hunter/tools/candidate_view.py
- 多段执行器：sim/experiments/agentvln_hunter/tools/agent_loop.py
- VLM 后端探测：sim/experiments/agentvln_hunter/tools/probe_vlm_backend.bash
- 候选单帧证据：outputs/agentvln_hunter_20261108_step2/candidate_view/
- 规则选择：outputs/agentvln_hunter_20261108_step2/agent_loop/
- 颜色基线：outputs/agentvln_hunter_20261108_step2/agent_loop_color/
- 直道+转弯：outputs/agentvln_hunter_20261108_step2/agent_loop_turn/
- 过冲失败：outputs/agentvln_hunter_20261108_step2/agent_loop_mid/

## 8. 已知限制与下一步

- 候选只在机器人前方 1.4–2.0 m 的扇形内；看不到更远或侧后方，跨大转角需要多段，且缺少主动观察位姿（第 3 步补）。
- 候选显示在 0.5 m 高信标上，地面点本身不在画面内；这是接口可视化，不是目标检测。
- 规则选择使用 oracle 地图目标；颜色选择只检测色块，不理解“经过红牌、在两个蓝箱中较远那个前方停下”这类语义。
- 没有局部停靠/目标深度；目标附近会过冲，见 5.4。
- 本地 VLM 不可用；WSL 没有 GPU 直通和推理运行时。
- 停稳位移有时到 0.0441 m，接近 0.05 m 上限；第 3 步要降低末段速度或延长停稳确认。

下一步（第 3 步）：

1. 在场景副本加“红牌 + 两个蓝箱”或等价目标，使指令有歧义和远近关系；
2. 目标可见后查询指定图像区域深度，用同帧有效像素中值估计距离，回传单位和有效率；
3. 用 p_camera=z*K^-1*[u,v,1]^T 反投影，再用同 stamp TF 变到 map；
4. 生成满足指令距离和车体净空的停靠位姿，试规划后执行；
5. 加短程观察位姿和纠偏；做关闭纠偏/关闭深度查询的对照。
