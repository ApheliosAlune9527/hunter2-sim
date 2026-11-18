# AgentVLN × HUNTER 2.0 本地 VLM 部署与仿真验证

2026-11-09 完成。所有行驶数据来自 Gazebo 中的虚拟 HUNTER。

## 本地模型

部署 Qwen2.5-VL-3B-Instruct F16 GGUF 及 F16 视觉投影器，两个文件的 SHA256 均与发布方一致。论文用 Qwen2.5-VL-3B 作为基座，再微调得到 AgentVLN-3B。作者仓库仍将微调检查点列为待发布，本轮使用已公开的基座权重。[论文 §4.2](https://arxiv.org/html/2603.17670v1#S4.SS2) · [作者仓库](https://github.com/Allenxinn/AgentVLN#todo) · [GGUF 发布页](https://huggingface.co/ggml-org/Qwen2.5-VL-3B-Instruct-GGUF/tree/main)

Windows 上的 llama.cpp b12143 经 Vulkan 使用 RX 9070 XT，显存实测约 7.9 GiB。服务监听 `127.0.0.1:18081`，模型别名 `qwen-vl`，图像 token 下限 1024。WSL 通过 Windows `curl.exe` 调用回环接口。服务已加载时，单次初始图像请求实测约 1.07 秒。三轮在线停靠的模型请求累计墙钟分别为 0.91、1.39、1.38 秒，包含两次查深度请求和一次选择请求。[运行回执与哈希](D:/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy/runtime.json)

## 模型读图与选箱

同一句蓝箱存在性问题，仿真相机图回答 `YES`，空白对照回答 `NO`。在从起点行驶到观察位姿后实际拍摄的同一帧上，用“较远”和“较近”分别提问。像素编号只标候选身份，深度来自同帧 RGB-D 深度图。[读图对照](D:/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy/image_input_control.json) · [四组逐轮结果](D:/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy/paired_2x2_natural_f16/report.json)

| 图像输入 | 按阶段查询两箱深度 | 深度工具关闭 |
|---|---:|---:|
| 原图 | 0/2 | 2/2 |
| 画面加候选编号 | 2/2 | 2/2 |

以上每格只有同一帧的两条指令。结果支持检查编号与指令接线，深度查询的收益仍待扩大样本验证。旧的 bigfar/swap 回放加编号和分阶段协议后为 3/4，旧 bigfar 的远箱有一次误选。允许模型自由决定动作的回放为 0/4，四次都没有选箱。本轮在线流程用分阶段协议指定测量阶段，模型实际发出工具调用并给出最终编号。自主决定何时查询、换位观察及完整 AgentVLN-3B 方法尚未验证。[旧回放](D:/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy/labelled_vlm_f16.json) · [自由调度回放](D:/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy/labelled_unrestricted_f16.json)

## 新布局与行驶

| 对象 | 中心位置或位姿 | 尺寸 |
|---|---|---|
| 近蓝箱 | `(5.294, 1.553, 0.400)` m | `0.26 × 0.20 × 0.80` m |
| 远蓝箱 | `(5.259, 2.375, 0.625)` m | `0.56 × 0.66 × 1.25` m |
| 标称观察位姿 | `(2.000, 0.500, 0.522)`，单位 m、m、rad | |
| 远箱标称停靠及评分中心 | `(3.538612, 1.385041, 0.522)`，单位 m、m、rad | 半径 0.30 m，航向误差上限 0.50 rad |

标称直线段长 1.775 m，方向 0.522 rad，轮廓到近箱最近净空 0.707 m。标称观察位姿实拍两箱完整入画，远箱的横向区间为 238–404 px，近箱为 454–514 px，间隔 50 px。远箱成像面积是近箱的 4.06 倍。从起点开到观察位姿后，实拍仍有 53 px 间隔和 3.86 倍面积比。[布局 JSON](D:/rob-memory/outputs/agentvln_hunter_20261108_step5_unblock/target_layout_straight.json) · [解析几何](D:/rob-memory/outputs/agentvln_hunter_20261108_step5_unblock/geometry_check.json) · [行驶到位后的图像](D:/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy/natural_frame/annotated.png)

| 测试 | 结果 | 停车区中心误差 |
|---|---|---:|
| 已知坐标，从标称观察位姿直进 | 成功并停稳 | 0.114 m |
| 从标准起点进入观察位姿，再由 VLM 选箱与停靠，第 1 轮 | 成功并停稳 | 0.149 m |
| 同条件第 2 轮 | 成功并停稳 | 0.126 m |
| 同条件第 3 轮 | 观察点附近重规划失败，30.02 仿真秒后取消完成并停稳 | 未进入停靠段 |
| 从标称观察位姿开始，VLM 选箱与停靠 | 成功并停稳 | 0.108 m |

完整起点任务为 2/3。三轮进入 VLM 阶段的测试均选中远箱并停稳，其中一轮直接从固定观察位姿开始。在线目标由模型选中的区域经新帧深度和 TF 反投影计算，标称停车区用于独立评分。三轮成功轨迹的车体轮廓到近箱最小采样净空为 0.747 m。箱体作为视觉与激光观测目标，净空按真值轨迹和矩形轮廓计算。接触事件计为 `not_measured`。近箱只完成选箱回放。[逐轮数据与汇总](D:/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy/validation_summary.json) · [重规划日志摘录](D:/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy/observation_replan_excerpt.log)

## 复跑入口

Windows 模型服务已启动。重启电脑后，可用 PowerShell 启动模型并检查服务。

```powershell
& 'D:/AgentVLN-runtime/qwen25vl-3b/start_qwen_vl.ps1'
curl.exe --noproxy '*' -fsS http://127.0.0.1:18081/health
```

用已存帧复跑上面的四组对照，无需启动 Gazebo。

```powershell
$trial = Get-Date -Format 'yyyyMMdd_HHmmss'
$results = '/mnt/d/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy'
wsl.exe -d Ubuntu-22.04 -u aphelios -- python3 -B "$results/compare_replay.py" --frame "$results/natural_frame" --out "$results/paired_repro_$trial"
```

行驶复跑在 WSL Ubuntu 22.04 中启动以下专用场景。入口会核验域 73、本机回环和分区，并读取冻结版 Nav2 参数。先确认该日志目录下没有活动会话。

```bash
repo=/mnt/d/rob-memory
fix="$repo/sim/experiments/lab_nav_fix_20261106"
scene="$repo/outputs/agentvln_hunter_20261108_step5_unblock"
results="$repo/outputs/agentvln_hunter_20261108_vlm_deploy"
export LOG_DIR=/tmp/agentvln_vlm_deploy_20261108_straight
WORLD="$scene/lab_agentvln_bigfar_straight.sdf" \
  BRIDGE="$repo/sim/experiments/agentvln_hunter/config/agentvln_bridge.yaml" \
  PARAMS="$fix/nav2_params_fix.yaml" LOCALIZER=amcl GUI=0 bash "$fix/run_fix_stack.bash"
```

确认启动成功后，在同一 WSL 终端加载环境并复跑。每轮先放置虚拟车并设置 AMCL 起点，之后由车自主行驶。观察段成功后才进入选箱和停靠。

```bash
source "$fix/lab_nav_fix_env.bash"
source /opt/ros/humble/setup.bash
source /home/aphelios/hz_sim_ws/install/setup.bash
trial=$(date +%Y%m%d_%H%M%S)
python3 -B "$repo/sim/experiments/agentvln_hunter/tools/reset_and_seed.py" -0.21 -0.77 0 0.0025 --ros-args -p use_sim_time:=true && \
  python3 -B "$results/run_straight_dock.py" --mode observe --out "$results/repro_${trial}_observe" && \
  python3 -B "$results/run_straight_dock.py" --mode vlm --out "$results/repro_${trial}_dock"
```

运行结束后，执行 `bash "$fix/stop_fix_stack.bash"` 关闭这一会话。本轮回执显示登记的 4 组仿真进程已全部退出，Windows 模型服务继续在线。[仿真停止回执](D:/rob-memory/outputs/agentvln_hunter_20261108_vlm_deploy/stop_receipt.log)
