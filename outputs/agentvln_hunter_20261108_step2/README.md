# 第 2 步证据索引（2026-11-08）

对应 sim/experiments/agentvln_hunter/README_step2.md。本步是工程基线，不是 VLM 结果。

## 主证据

- candidate_view/report.json：单帧候选生成/投影/编号；15 采样 → 7 有效 → 6 可见，selected id=3。
- candidate_view/annotated.png：编号与选中候选（黄色）叠图。
- agent_loop_color/run.json：颜色标记驱动选择，1 段成功，final_error 0.3147 m；marker 面积 2.287%。
- agent_loop_turn/run.json：两段直道+左转，2 段全部 status=4，final_error 0.0990 m，转向约 0.674 rad。
- agent_loop_turn/step_00/annotated.png、step_01/annotated.png：两段候选编号图。
- agent_loop/run.json：规则选择（oracle 地图目标）1 段成功，final_error 0.3240 m。

## 失败样例

- agent_loop_mid/run.json：目标附近过冲；4 段后误差 1.945 m。第 1 段后距目标 0.623 m 已超过 0.60 阈值，仍继续选 1.4–2.0 m 的前向候选。
- 该失败说明缺少目标附近的局部停靠/减速逻辑，不是 Nav2 动作失败（各段 status 均为 4）。

## VLM 后端

- vlm_probe.log：WSL 只有 Microsoft 3D controller，无 ROCm/Vulkan/NVIDIA；无 torch/transformers/ollama/llama.cpp，HF 缓存为空。
- 本步没有运行任何 VLM；颜色检测只作为 engineering baseline。
