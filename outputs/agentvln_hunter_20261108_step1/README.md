# 第 1 步证据索引（2026-11-08）

本目录对应 sim/experiments/agentvln_hunter/README.md 的第 1 步。按重要性：

## 验收通过

- nav2_verify_camera.json：相机栈上 Nav2 16/16 参数读回。
- camera_verify3/report.json：RGB-D 同步、内参、TF、三色标记投影/深度/反投影，overall=true。
- camera_verify3/annotated.png：三色标记与 u/v/z 标注的可视证据。
- nav_camera/report.json：同会话 NavigateToPose 成功（status=4），70 帧中 66 帧在行驶中采集。
- nav_camera/start.png、mid.png、last.png：起步、行驶中、终点三帧。
- baseline_near_tight.json、baseline_short_tight.json、baseline_mid_long_tight.json：已知坐标四个目标到点成功。
- baseline_cancel.json：预算触发的取消、终态和停稳。

## 失败对照/保留样例

- nav_camera_loose_seed_fail/：松 AMCL 先验导致 0.53 m 后规划失败（status=6）。
- camera_verify/、camera_verify2/：相机 TF 高度/时序修复前的失败尝试；只有 camera_verify3/ 是有效版本。

## 诊断文件

- global_costmap.png/json/npz、global_costmap2.*：早期 costmap 排查截图/数据。
