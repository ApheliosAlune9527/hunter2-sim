# 实验室导航基线实验目录（lab_nav_20261105）

接手方案任务 1 与任务 2 的落地目录。所有工件都在本目录内，不覆盖既有输出，
不修改已验收的 `sim/scenes/hz_hunter_full.sdf`。

**先看哪一份**：要数字看 `RESULTS.md`（由 `sim/experiments/lab_nav/make_report.py`
从各 `*_verification.json` 生成，没有手抄的数字）；要原因与踩坑看这份 README；
要单条结论的证据链看对应的 `taskN_verification.json`。

这份 README 本身可以用 `sim/experiments/lab_nav/check_docs.py` 自检：它会解析文中
所有反引号路径，确认文件真的存在，并把 RESULTS.md 与 README 里的成功率数字和
`task4_verification.json` / `task5_verification.json` 对账。最近一次运行：75 个路径
全部解析成功，truth 9/9 与 amcl 7/9 与记录一致。它抓到过一个真错：文中把审计脚本
写成 track_collision_audit.py，实际文件名是 `audit_tracks_collision.py`。

## 任务 1：独立实验室导航场景

| 文件 | 说明 |
|---|---|
| `lab_nav_map.pgm` | 2026-11-01 未修补原图副本，241×465 格，0.05 m/格 |
| `lab_nav_map.yaml` | 修正后的地图描述文件（见下） |
| `lab_nav_world.sdf` | 由二维图挤出的场景，world `hz_lab_2d`，初始位姿 (−0.21, −0.77, 0.165) yaw 0 |
| `walls.stl` | 墙体网格（1,326,684 B） |
| `manifest.json` | 源文件与副本的 SHA256、尺寸、坐标系 |
| `load_check.json` | 无头加载校验回执 |

**已修正的缺陷**：来源 YAML `outputs/lab_map_compare_20261105/lab_odom_06_new.yaml`
第 1 行写的是 `image: lab_odom_06.pgm`，而该目录里并没有这个文件（实际文件叫
`lab_odom_06_new.pgm`），直接拿去做 `map_server` 会加载失败。本目录的
`lab_nav_map.yaml` 把 `image` 指向同目录的 `lab_nav_map.pgm`，其余参数
（`mode: trinary`、`resolution: 0.05`、`origin: [-5.09, -4.89, 0]`、
`occupied_thresh: 0.65`、`free_thresh: 0.25`）与原文件一致。原文件保持不动。

加载校验结果：地图 12.05 × 23.25 m；occupied 5,928 / free 41,446 / unknown 64,691；
初始位姿所在格为**空闲**；按车体包络（x∈[−0.164, +0.814]、y∈±0.373）算出的
最小净空为 **0.76 m**（未知区也按不可通行计）。

## 任务 2：虚拟驱动与最小传感器闭环

`lab_nav_world_drive.sdf` 是在 `lab_nav_world.sdf` 基础上叠加的版本，改动全部
记录在 `drive_world_summary.json` 的 `changes` 里：

- 加入 `Sensors` 系统插件（`render_engine=ogre`）；
- 删掉 32 线雷达、RGB-D 相机、IMU，只留一个**单线 2D 扫描**；
- 在车模上加入 `AckermannSteering`（`/hz_sim/lab/cmd_vel` → `/hz_sim/lab/odom`、`/tf`）
  与 `JointStatePublisher`（`/hz_sim/lab/joint_states`）；
- `max_step_size` 由 0.001 改为 **0.004 s**（250 Hz，理由见性能一节）；
- 墙体碰撞由 1.3 MB 三角网格换成 **1,589 个盒子**（可视仍用 `walls.stl`）。

### 接口约定

| 方向 | 话题 | 类型 |
|---|---|---|
| GZ → ROS | `/clock` | `rosgraph_msgs/Clock` |
| GZ → ROS | `/hz_sim/lab/scan` | `sensor_msgs/LaserScan` |
| GZ → ROS | `/hz_sim/lab/odom` | `nav_msgs/Odometry` |
| GZ → ROS | `/hz_sim/lab/tf` | `tf2_msgs/TFMessage` |
| GZ → ROS | `/hz_sim/lab/joint_states` | `sensor_msgs/JointState` |
| **ROS → GZ** | `/hz_sim/lab/cmd_vel` | `geometry_msgs/Twist` |

`/hz_sim/lab/cmd_vel` 是**唯一**的速度入口；本场景不含任何实车控制程序。

### 启动方式

```bash
# 服务器（无头）
ign gazebo -s -r -v 3 /mnt/d/rob-memory/outputs/lab_nav_20261105/lab_nav_world_drive.sdf
# 桥接
ros2 run ros_gz_bridge parameter_bridge --ros-args \
  -p config_file:=/mnt/d/rob-memory/sim/config/lab_nav_bridge.yaml -p use_sim_time:=true
```

**必须先 `source /mnt/d/rob-memory/wsl/hz_sim_env.bash`**：这个文件会设置
`IGN_PARTITION=hz_sim_aphelios_73`、`ROS_DOMAIN_ID=73`、`ROS_LOCALHOST_ONLY=1` 和
`rmw_cyclonedds_cpp`。如果先设 `IGN_PARTITION` 再 source，会被它覆盖，服务器和
客户端会落进不同分区，`ign topic -l` 看起来"没有话题"（本次已踩过）。
同理，桥接进程若用默认 FastRTPS，而客户端用 CycloneDDS，两者互相看不见。

也可以直接跑 `sim/experiments/lab_nav/run_lab_nav.bash`（内部已按正确顺序 source）。

### 实测结果（`task2_verification.json`）

| 项目 | 结果 |
|---|---|
| `set_pose` 精度 | 请求 (2.535, 12.885, 2.7053) → 真值完全一致 |
| 直行 2.21 m @0.05 m/s | 里程计 2.2052 m vs 真值 2.2098 m，**相对误差 0.21%** |
| 倒车 1.17 m @−0.05 m/s | 里程计与真值**完全一致**（误差 0.0%） |
| 满舵转向关节角 | 内侧 **0.4439 rad**、外侧 **0.3185 rad**（理论 0.444 / 0.318） |
| 最小转弯半径 | 理论 1.669 m；实测弧长/转角 **1.627 m（−2.5%）** |

关节限位与转向能力：插件 `steering_limit=0.4`，关节硬限位 ±0.58，满舵时内侧轮
0.444 rad，与 `L/sin(δ)` 推导的 1.669 m 一致（`L/(2δ)` 那种小角度近似会算成
0.812 m，是错的，本目录的推导已按前者修正）。

### 性能实测

成本几乎与**迭代次数**成正比，与步长无关：

| 配置（500 次迭代） | 墙钟耗时 |
|---|---|
| 步长 1 ms + 网格墙 | 11.56 s |
| 步长 1 ms，无传感器 | 6.12 s |
| 步长 1 ms，无传感器无墙 | 2.61 s |
| 步长 4 ms + 网格墙 | 12.39 s |
| 步长 4 ms + 盒子墙 | 9.67 s |
| 步长 8 ms + 网格墙 | 12.53 s |

所以把步长从 1 ms 提到 4 ms，吞吐直接约 4 倍；再把墙体碰撞换成盒子，再快 25%。
当前配置实测实时系数约 **0.19**，即 60 仿真秒的一轮约需 5 分钟墙钟。

### 已知缺口

- 碰撞**没有**可用的接触话题：Contact 系统加载了，但本 build 从不广告
  `/world/hz_lab_2d/contacts`，teleport 进墙也没有消息。现在用两条替代证据：
  轨迹审计（占用栅格距离场查已存轨迹）与 RL 环境里的轮速代理。详见
  `task4_verification.json` 的 `collision_source_correction`。
- 墙高 2.4 m、家具一视同仁按 2.4 m 挤出，这是工程假设。
- 未知区无几何，地面是一整块平面，靠墙挡住车。

## 复现脚本

全部在 `sim/experiments/lab_nav/`：

| 脚本 | 作用 |
|---|---|
| `build_nav_package.py` | 任务 1：复制地图、改写 YAML 与 mesh URI、算 SHA256 |
| `verify_nav_world.py` | 任务 1：`ign sdf -k` + 无头加载 + `[Err]` 计数 |
| `build_lab_world.py` | 任务 2：生成可驾驶世界（插件、传感器、步长、盒子墙） |
| `run_lab_nav.bash` | 启动服务器与桥接 |
| `pick_calibration_pose.py` | 选出净空最大、直行距离最长的标定位姿 |
| `test_drive_baseline.py` | 直行/倒车/转向的里程计对真值测试 |
| `probe_steering.py` | 读取满舵时的实际前后轮转角 |
| `test_turn_radius.py` | 开环圆弧 + 真值采样拟合转弯半径 |
| `make_probe.py` / `make_box_walls.py` | 性能对照用的探针世界 |
| `make_nav2_params.py` | 从师兄 `nav2_params.yaml` 派生本场景参数，只打四刀并写 `nav2_params_diff.json` |
| `placeable_region.py` | 按师兄 footprint 算可放置区域，并按走廊条件筛目标 |
| `run_lab_stack.bash` / `stop_lab_stack.bash` | 起/停整个栈（`LOCALIZER=truth\|amcl`、`NAV2=0\|1`） |
| `truth_localisation.py` / `odom_tf.py` / `init_pose.py` | 真值 TF、AMCL 模式的 odom TF、初始位姿重发 |
| `run_nav2.launch.py` / `run_amcl.launch.py` | 导航栈与定位的 launch |
| `run_nav_eval.py` | 3 目标 × N 轮评测（真值判据、复位、看门狗、CSV/JSON） |
| `plot_nav_eval.py` | 目标图与真值轨迹图 |
| `audit_tracks_collision.py` | 用距离场复核已存轨迹的边缘净空 |
| `amcl_eval.py` | AMCL 静止与 2 m 直线误差 |
| `measure_profile.bash` / `probe_rates.py` | 三组感知档案（精简 / 完整 / 完整带界面） |
| `consistency_check.py` / `cloud_stats.py` | 运动时序一致性与点云字段核查 |
| `rl/` | RL 环境、接口自检、训练、评测（见 Task 7） |

### 从零复现的命令顺序

```bash
source /mnt/d/rob-memory/sim/experiments/lab_nav/lab_nav_env.bash   # 必须先，它设域 73 与分区
python3 -B sim/experiments/lab_nav/build_scene_from_2d.py          # 2D 图 -> 墙盒/STL/SDF
python3 -B sim/experiments/lab_nav/build_nav_package.py            # 地图 + YAML + 清单
python3 -B sim/experiments/lab_nav/verify_nav_world.py             # SDF 合法性与无头加载
python3 -B sim/experiments/lab_nav/build_lab_world.py              # 可驾驶世界（插件+传感器）
python3 -B sim/experiments/lab_nav/placeable_region.py             # 可放置域与目标集
python3 -B sim/experiments/lab_nav/make_nav2_params.py             # 师兄参数 + 四刀补丁

LOCALIZER=truth NAV2=1 bash sim/experiments/lab_nav/run_lab_stack.bash
python3 -B sim/experiments/lab_nav/run_nav_eval.py --tag demo      # 9 轮
bash sim/experiments/lab_nav/stop_lab_stack.bash

LOCALIZER=amcl  NAV2=1 bash sim/experiments/lab_nav/run_lab_stack.bash
python3 -B sim/experiments/lab_nav/run_nav_eval.py --tag amcl --reinit-amcl
bash sim/experiments/lab_nav/stop_lab_stack.bash
```

隐藏前提：`run_lab_stack.bash` 只用 `setsid nohup` 脱离启动才不会被 WSL 会话带走；
`ros2 launch` 把节点 fork 到独立会话，所以 `stop_lab_stack.bash` 除了 pid 文件还要按
节点名模式扫残留。

## Task 3 — truth localisation and the first Nav2 loop (2026-11-05)

Chain: `map -> odom` and `odom -> base_link` are both published by
`truth_localisation.py`, `base_link -> laser` is static.  The gz `tf` topic is
**not** bridged: two publishers for the same edge produced a stream of
`TF_OLD_DATA` warnings.  SmacPlannerHybrid (Dubins, minimum turning radius
1.669 m, unknown = lethal) plus RegulatedPurePursuitController (0.20 m/s,
collision detection on, no reversing, no rotate-to-heading).

Accepted run: goal (2.2, -0.77, 0), status 4 succeeded, 2.202 m travelled in
12.85 simulated seconds, final error 0.208 m (tolerance 0.25), heading error
0.001 rad.  A lateral goal 1.2 m away at (1.0, 0.0) does **not** converge: the
vehicle circled for 330 simulated seconds and 36 m of path.  That is the
expected consequence of a 1.669 m minimum turning radius with reversing
disabled, and it is why task 4 has to check reachability before it counts a
failure as a failure.

Two earlier blockers were real bugs, not tuning:

* the scene was **mirrored** about the map x-axis (wall meshes and boxes used
  `y = origin.y + row * res` instead of `origin.y + (rows - row) * res`), so the
  vehicle spawned inside a phantom wall; fixed in
  `sim/experiments/lab_scene/build_scene_from_2d.py` and
  `sim/experiments/lab_nav/build_lab_world.py`, verified by 0 wall boxes
  touching the spawn footprint and a clean drop test;
* a single-plane `gpu_lidar` reaches ROS through `ros_gz_bridge` as 0.1 m on
  every beam (its vertical step is `nan`), so the scan now uses three vertical
  samples spanning +/-0.017 rad at a height of 0.62 m.

Evidence: `task3_verification.json` and `nav_goal_track.json`.

## Task 4 - repeatable navigation evaluation

The goal set is not hand-picked.  `placeable_region.py` erodes the free space
with the costmap footprint (the senior's `[[0.52,0.395],[0.52,-0.395],
[-0.50,-0.395],[-0.50,0.395]]`, not the CAD envelope, so that "placeable" and
"plannable" mean the same thing) for all 72 headings, then requires the straight
corridor from the spawn to be clear in the driving direction.  Result: 46.93 m2
at any heading, 25.97 m2 at every heading, largest strict component 20.68 m2,
and the spawn itself is placeable at all headings.

Each goal is given the heading of the straight approach (bearing from spawn),
because a forward-only Dubins vehicle that is asked to arrive at yaw 0 from a
26 deg bearing cannot always turn the last few degrees in the available space.
Nine runs, three rounds per goal, 60 simulated seconds each, wall-clock
watchdog 400 s, truth pose from the gz odometry plugin, collisions from the gz
contact system with wheel/floor ground contact filtered out.

| goal | target (x, y) | dist | successes | mean err | mean sim s |
|---|---|---|---|---|---|
| short_straight | 1.885, 0.435 | 2.42 m | 3/3 | 0.186 m | 11.6 |
| mid_offset | 3.185, 1.235 | 3.94 m | 2/3 | 0.122 m | 31.5 |
| long_run | 4.285, 2.535 | 5.58 m | 3/3 | 0.163 m | 29.9 |

Overall 8/9 with truth localisation, tolerance 0.25 m.  This is the batch run
before the `allow_unknown` patch and before success was checked against the
truth; it is kept as history, and the corrected batch is 9/9 - see
"Correction: a success has to be confirmed by the truth" below.  Nothing here
is a measured collision count.  `far_turn` (8 m band, 45-110
deg) has no placeable cell with a free straight corridor and is reported
infeasible rather than replaced by a goal that happens to work.

The single failure is informative: `mid_offset` round 1 finished with 0.104 m
position error and 0.094 rad heading error - both inside tolerance - after
covering exactly the straight-line distance, yet the NavigateToPose action never
returned and the run timed out at 61 simulated seconds with the vehicle
standing still.  It is recorded as a stop-short failure, not a success, and
left open for task 5.

A control experiment kept the same goals but forced every target heading to
0 rad (`nav_eval_runs_yaw0_headings.json`): 6/9, with `short_straight` failing
3/3 while the two farther goals passed.  The near goal is approached at 26 deg,
so the vehicle arrives within position tolerance carrying ~0.5 rad of heading
error; with reversing and rotate-to-heading disabled it then circles away
looking for a legal turn.  Distance alone does not predict difficulty.

Evidence: `task4_verification.json`, `nav_eval_runs.json`, `nav_eval_summary.csv`,
`nav_eval_tracks.json`, `nav_eval_tracks.png`, `nav_eval_goals.png`.

## Task 5 - AMCL localisation

AMCL now owns `map -> odom`; the truth module is not started in this mode, so
there is exactly one publisher of that edge.  The scan, the odometry and every
navigation parameter are the ones from task 4 - only the localiser changed.
The `amcl:` block is the senior's, unmodified (differential motion model,
likelihood field, 2000 particles, `transform_tolerance: 1.0`).

Three pieces had to be added for it to run at all:

* `odom_tf.py` publishes `odom -> base_link` stamped with the odometry
  message's own time (never `now()`, which reproduces the task 3 extrapolation
  errors) plus the same static `base_link -> laser` transform truth mode uses.
* `LOCALIZER=amcl` in `run_nav2.launch.py` puts amcl into the *same*
  lifecycle manager as the rest of the stack.  A second manager cannot work:
  amcl's configure step needs `/map` to already exist, so map_server must be
  activated first by the same manager.
* `init_pose.py` publishes `/initialpose` until `map -> base_link` resolves.
  AMCL only starts publishing `map -> odom` after it gets an initial pose, and
  the global costmap only activates after that TF exists - waiting for
  "Managed nodes are active" first deadlocks.

| Test | Result | Criterion |
|---|---|---|
| Static, 59 samples | mean = max = 0.0437 m, drift 0.0 m | < 0.05 m |
| Straight 2.011 m at 0.12 m/s | end error 0.0926 m, heading 0.012 rad | < 0.15 m |

Both pass (`amcl_eval.json`).  The static figure is a constant offset, not
jitter: the pose barely moves sample to sample.

Repeating the task 4 goals under AMCL gives 6/9 against 8/9 with truth
localisation in the matching batch:

| Goal | AMCL | truth | mean error (AMCL) |
|---|---|---|---|
| short_straight | 3/3 | 3/3 | 0.104 m |
| mid_offset | 3/3 | 2/3 | 0.114 m |
| long_run | 0/3 | 3/3 | 0.871 m |

Both batches above predate the `allow_unknown` patch and the truth-checked
success criterion.  Re-run with both in place the same two batches give 7/9 for
AMCL (short_straight 2/3, mid_offset 3/3, long_run 2/3, two budget expiries and
no false success) against 9/9 for truth; the long goal recovers once unknown
space stops being planned through.  See "Correction: a success has to be
confirmed by the truth" for the numbers and the artefacts.

The two shorter goals are as reliable as with truth.  `long_run` (5.58 m) fails
three times: twice it stops within 0.15 m - inside tolerance - without the
action ever returning, and once it aborts 1.92 m short.  The pattern is drift
accumulating over the longer path and showing up as obstacles that do not line
up in the local costmap.  This is reported as a real limitation, not tuned
away.

Resetting between rounds needs the filter to settle: teleport, re-seed with
five `/initialpose` messages, then four seconds of still scans.  With a shorter
settle the first plan of a round was issued from an estimate 1.06 m off, and
that round never recovered (`amcl_nav_probe.py` shows the trace).

Evidence: `task5_verification.json`, `amcl_eval.json`, `nav_eval_runs_amcl.json`,
`nav_eval_summary_amcl.csv`, `nav_eval_tracks_amcl.png`, `nav_eval_goals_amcl.png`.

## Task 6 - perception profiles

Three fixed configurations were measured with `measure_profile.bash`, which
starts one world plus its bridge, measures for a fixed wall-clock window and
then kills exactly the processes it started.  `probe_rates.py` subscribes by
explicit topic name (graph discovery stays empty on this machine even when the
topics are up) and reports per-topic rate plus the simulated clock.

| Configuration | Real-time factor | Scan or lidar | Camera | IMU |
|---|---|---|---|---|
| lean navigation, server only | 1.00 | 9.70/10 Hz | - | - |
| full sensors, server only | 1.00 | 5.44/10 Hz | 2.72/5 Hz | 54.2/100 Hz |
| full sensors, GUI attached | 1.00 | 9.53/10 Hz | 4.87/5 Hz | 98.5/100 Hz |

Three things came out of this that change how the rest of the work should be
run:

1. **Nothing here is limited by physics or by the step size.**  All three hold
   the clock at exactly 1.00x real time.  The lean profile delivers 9.7 of 10
   scan frames per second with a p95 interval of 100.5 ms - it is a real-time
   profile.
2. **Headless is the slower path for sensors on this machine.**  The same world
   with the GUI attached delivers every sensor at nominal rate, while
   server-only delivers about 54% of nominal with the clock still at 1.00x.
   The frames are dropped, not slowed.  So "run headless to save time" is wrong
   here for perception work; it is only right for the lean navigation profile,
   where the only sensor is the 2D scan.
3. **The earlier 0.14x real-time figure is not reproduced** by any of these
   three configurations.  It was recorded with a different load (GUI plus the
   full observation program) and stays specific to that run until those
   conditions are rebuilt - it should not be quoted as a property of the
   platform.

Evidence: `task6_verification.json`, `profile_lean_scan.json`,
`profile_full_sensors.json`, `profile_full_sensors_gui.json`.
Reproduce with `PROFILE=full bash sim/experiments/lab_nav/measure_profile.bash
sim/scenes/hz_hunter_full.sdf sim/config/hunter_full_bridge.yaml <label> 20`
(add `GUI=1` for the third row).

### Timing consistency while moving

Drove 0.15 m/s for 12 s and compared every message stamp with the simulated
clock at arrival (`consistency_check.py`).  Scan, odometry, ground truth and the
`base_link` TF all arrive within one clock tick: mean age 0.0 ms, scan worst
case 4.0 ms.  The clock only ticks at 250 Hz, so this establishes "no topic is
more than 4 ms stale", not "the ages are exactly zero".

The frame plumbing was checked directly: `/scan` carries `frame_id: laser`, and
`base_link -> laser` resolves to (0.539, 0, 0.620) with 1.571 rad of yaw, which
is exactly the sensor pose written into the world.  Obstacles therefore land
where they are seen.

The 50 ms scan-versus-TF lag seen during task 3 does not appear here.  It came
from bridging the Gazebo TF while the localiser also published it; with a
single TF authority per edge it is gone.

Evidence: `task6_consistency.json`, `consistency_check.py`.

### Point cloud as a FAST-LIVO2 input

Sampled one frame of `/hz_sim/full/lidar/points` while the full profile ran:

| property | value |
|---|---|
| geometry | 720 x 32 organised, 23,040 points, 10,690 with a return |
| point_step | 32 bytes |
| fields | `x`, `y`, `z`, `intensity`, `ring` |
| frame | `hz_sim/full/hesai_lidar` |

The gap that matters for FAST-LIVO2 is per-point time.  The cloud carries no
`time`/`offset_time` field, and no azimuth field either, so a per-point
timestamp can only be invented by assuming the column index maps linearly onto
the sweep.  That would be a fabricated time base, so it is not done.

What this cloud does support: geometry, obstacle detection, a 2D projection for
the scan-based stack.  What it does not support yet: motion undistortion for a
LIVO-style pipeline.  `intensity` is present but simulated, not calibrated
against the physical Hesai.  The frame name contains slashes, which TF accepts
but several offline tools assume away.

### Lean profile versus full profile

Both hold 1.00x realtime, so neither is limited by the physics step.  What
differs is what the robot can see and how well the headless bridge keeps up.

| | lean navigation | full sensors |
|---|---|---|
| sensors | one planar scan, 720x3 at 10 Hz | 3D lidar 720x32, rgbd 640x480, imu, odom |
| step | 0.004 s | world default |
| headless delivery | scan 9.70/10 Hz | lidar 5.44/10, camera 2.72/5, imu 54.2/100 |
| with a window open | not used | lidar 9.53/10, camera 4.87/5, imu 98.5/100 |

The lean world is what traditional navigation and RL run in; the full world is
kept for perception work.  A number from one is never tabulated next to a number
from the other without saying which profile produced it.

### Engineering assumptions carried by the scene

Written down so a later reader does not mistake them for measurements:

- **Walls are extruded from a 2D occupancy grid.** A cell marked occupied became a
  box 2.4 m tall. The real obstacles are desks, chairs, cabinets and pillars; the
  grid does not know their heights, so a 2.4 m wall may be taller than reality.
- **Unknown space has no geometry.** Cells the mapping run never saw are neither
  free nor blocked in the world; in planning they are treated as impassable, so
  the planner cannot exploit a gap in the map.
- **The floor is one flat plane** over the whole world, so there are no steps,
  ramps or kerbs.
- **The scan is a simulated ray cast** from a single plane at 0.62 m, not a real
  lidar return: no dropouts from black surfaces, no multipath, no intensity.
- **The map is the 2026-11-01 run as captured**, including desks added since
  September. It is deliberately not the repaired version.

### Correction: the collision figure was not measured

Every run before this point reports `0 collisions`, taken from `/contacts`.  That
topic exists on the ROS side because the bridge creates it, but the Gazebo
Contact system -- which is loaded, verified with a verbose run -- never
advertises `/world/hz_lab_2d/contacts` in this build.  The bridge therefore sat
on an empty topic and the zero was a number produced by nothing.

What the saved data can still answer is whether the footprint ever entered an
occupied cell.  Over every recorded truth pose in all 18 runs
(`audit_tracks_collision.py`):

| runs | worst footprint-edge clearance | runs with overlap |
|---|---|---|
| truth localisation, 9 runs | 0.200 m | none |
| AMCL, 9 runs | 0.071 m | none |

That is not the same claim as "no contact".  It cannot see a contact between two
samples, and a vehicle can press against a wall without its footprint crossing
the grid line.

The replacement is a blocked detector: wheels turning (odometry advancing) while
the simulated pose does not move.  It was validated by driving into a wall on
purpose -- `rl_termination_test.json` reports the collision after 1.1 m of a
1.6 m approach.  The evaluator and the RL environment now report
`contact_proxy` together with `contact_source` so the distinction travels with
the number.

### Correction: a success has to be confirmed by the truth

The first batch run under the senior's parameters produced one round that
returned `STATUS_SUCCEEDED` with the vehicle 1.421 m from the goal.  It was not a
bookkeeping slip: `probe_goal_tf.py` reproduced the mechanism.  The controller's
own estimate (TF `map -> base_link`) and the simulated pose agreed to a
millimetre for the first seconds of the run, then parted company -- the estimate
ran on for about a metre while the vehicle stood still.  Odometry was advancing
because the wheels were turning; the body was not moving.  The estimate therefore
reached the goal, the controller reported success, and the vehicle never got
there.

The number that made this visible is the one the evaluator already recorded:
distance from the goal in the simulated pose.  So the criterion changed:

```
success = (status == STATUS_SUCCEEDED) and (final_error <= 0.25 m)
```

`reported_success` now keeps the controller's claim next to the truth-checked
verdict, a disagreement is stored as `false_success` with reason
`truth_disagrees`, and the odometry-versus-truth travel is recorded per round
with `stuck` set when the difference exceeds 0.5 m.  A settle loop also waits for
the simulated pose to stop moving before the first goal of a fresh stack is sent,
because the runaway only ever happened on that first goal.

Re-running the same three goals under the same parameters, with
`allow_unknown: false` (`nav_eval_runs_nounknown2.json`):

| goal | rounds | success | mean final error | mean simulated time |
|---|---|---|---|---|
| short_straight | 3 | 3/3 | 0.183 m | 11.5 s |
| mid_offset | 3 | 3/3 | 0.158 m | 22.0 s |
| long_run | 3 | 3/3 | 0.171 m | 24.8 s |

Nine of nine, no false success, no stuck round.  The earlier `0 collisions` claim
is unrelated and remains as corrected above -- it is still an unmeasured
quantity, not a measured zero.

## Task 7 - RL environment and a first policy (2026-11-06)

The point of this task is the interface, not a number.  The environment lives in
`sim/experiments/lab_nav/rl/` and drives the same world, the same 2D scan and the
same velocity entry the navigation baseline uses, so a policy and Nav2 can be
compared on equal footing later.

| element | choice | why |
|---|---|---|
| observation | 76 floats: 72 beams (720 pooled 10:1 by minimum, /3 m, clipped), goal range /6 m, goal bearing /pi, previous v and w | one scan per control step keeps the frame rate honest; the two action echoes let the policy see its own latency |
| action | `v = (a0+1)/2 * 0.26 m/s` (forward only), `w = a1 * 0.20 rad/s` | the baseline runs `allow_reversing: false`, so a reversing policy would not be comparable; the Ackermann limit is left to the vehicle model |
| control period | 0.1 simulated seconds | 10 Hz is the rate the scan and the odometry can actually sustain |
| reward | `2.0 * progress - 0.01 - 0.05 |dv|`, +5 on goal, -5 on contact | progress in metres is what the navigation metrics also report; the small step cost stops loitering, the action penalty is a crude smoothness term |
| termination | 0.25 m to goal, contact, or the episode budget | the tolerance is the same 0.25 m the Nav2 evaluation accepts |
| reset | teleport, read the pose back, re-seed from truth + the first odometry sample | Gazebo's odometry does not reset on teleport, so integrating it across episodes would give each episode a different heading bias |

Goals come from the same `placeable_region` masks as task 4, but the RL pool is
split: 40 training goals and 12 held-out goals, with every held-out goal more than
0.75 m from any training goal.  The three fixed evaluation goals are the ones the
navigation baseline ran (`short_straight`, `mid_offset`, `long_run`), so the
comparison does not depend on a new sample.  `far_turn` is absent because no
corridor satisfied the footprint check, exactly as in task 4.

### What the environment had to work around

Gazebo's contact system loads in this build but never advertises
`/world/hz_lab_2d/contacts`; a teleport straight into a wall produces no message.
Bridging a topic nothing publishes only makes an empty stream look like a clean
run, which is how the earlier `0 collisions` figure became wrong.  The environment
therefore uses a proxy: contact is declared when the wheel odometry is integrating
while the true pose does not move for four consecutive control steps and the
commanded speed is above 0.08 m/s.  Every episode reports `contact_proxy` and
`contact_source`, and a solution that spins its wheels in place cannot hide.

### Interface validation

`smoke_env.py` checks observation shape and range, the control period, that reset
lands within 3.9 mm of the requested pose, and that an idle episode ends on its
budget at 60 simulated seconds.  `test_terminations.py` reaches a goal in 4.21 s
and stops on contact after 1.1 m when sent down a 1.6 m path into a wall.

### Four runs, and what each one changed

Every run is PPO with a [64,64] MLP on CPU; the differences are the budget, the
goal pool and one reward term.  Nothing below is a tuned result -- these are the
four runs that were actually executed, in order, with what each one ruled out.

| run | steps | goal pool | reward | curve: arrivals | fixed goals | train goals | held-out |
|---|---|---|---|---|---|---|---|
| `seed0_8k` | 8,192 | all 40 | progress | — | 0/3 | — | 0/6 |
| `seed0_60000` | 60,000 | all 40 | progress | 12.2 % | 0/9 | — | 0/6 |
| `seed1_20000_near8` | 20,000 | nearest 8 | progress | 18.7 % | 0/9 | 0/8 | 0/6 |
| `seed2_20000_near8_distance` | 20,000 | nearest 8 | + distance charge | 34.5 % | 0/9 | **4/8** | 0/6 |

Two of those columns need care.  `seed0_60000` is the only run whose curve has no
recorded `reason` field, so its arrival rate is the old return-threshold estimate
(return >= 4) rather than the episode's own ending; the later runs record `reason`
and are counted from it.  Returns are **not** comparable between the last run and
the others: charging 0.03 per metre of remaining distance every step drags the
mean return down (a successful episode returns about +2.8 instead of +5.9), so a
lower return in that row does not mean a worse policy -- the arrival counts do.

### Why the first three policies stopped a metre short

The 20k run on the nearest eight goals reached 0.864 m mean final distance and
still never arrived.  A trace of one episode (`diag_policy.py`) shows the shape:

```
t=9.7 s   distance 0.679 m   v=0.000   w=-0.000
...
t=60.1 s  distance 0.678 m   v=0.002   w=0.001
```

The vehicle drives up to the goal, then commands zero for the remaining fifty
simulated seconds.  This is not a controller bug: with contact at -5.0 and time
at -0.01 per step, stopping is worth about -0.6 per episode while one bad approach
costs -5.0, so "creep close and stop" is a better expected return than "risk the
last metre".  The policy optimised the reward it was given.

The `progress_distance` variant charges 0.03 per metre of remaining distance every
step, which makes idling cost about the same as failing.  With that single change
the same budget and goal pool takes the train goals from 0/8 to 4/8 and the mean
final distance from 0.864 m to 0.613 m.  The fixed goals and the held-out goals
stay at zero: the policy can now finish a goal it has practised, and still cannot
generalise, which is a different problem from the one the reward fixed.

### What this does and does not claim

The interface is verified: resets read back within 3.9 mm, the observation is
76 finite floats, the control period is 0.1 simulated seconds, termination fires
for both goal and contact, and no episode leaked state into the next.  The policy
is not a navigation result.  On the same three goals and the same world Nav2 with
truth localisation succeeds 9/9 with a 0.25 m tolerance; the best policy here is
0/9 with a mean miss of 1.97 m.  A comparison table with those numbers in one
place is what a reader should ask for, and it is in `RESULTS.md` -- with the
caveat that the policy sees no map while the baseline plans on one.

### Fairness conditions recorded now, before any comparison

The policy sees no map, the baseline does.  The policy's pose starts from truth at
reset and then drifts on odometry.  Before a policy may be compared with Nav2 the
following have to match: map or no map, localisation mode, sensor profile, speed
limits, goal set and time budget.  Those are written into
`task7_verification.json` so a later reader can check them rather than trust the
prose.

## Task 8 - what to do next

The platform is finished enough to be used, and the honest list of what it cannot
do is in `TASK8_NEXT_STEPS.md`, together with what each candidate direction would
require and the read-only checklist for real-vehicle work.  That file is a decision
memo: it does not start anything, and the choice needs the supervisor's direction.
