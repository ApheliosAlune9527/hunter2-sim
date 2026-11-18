# Go2 EDU 上手指南

整理日期：2026-11-09。适用对象：实验室刚采购的 Unitree Go2 EDU（含/不含 Docking Station、外置雷达、机械臂等选配都覆盖）。

> 证据等级标记：
> **✅ 官方** = Unitree 官网、官方 GitHub、官方手册/文档；
> **🟡 第三方** = 代理商/集成商文档或社区实践，需实机复核；
> **❗ 待实机** = 本机尚未连接机器狗，必须等设备到场后按第 10 节清单逐项确认。
>
> 本轮没有连接或操控实机。本文所有"已验证"仅指文档链路与本机离线工具链，不指实机动作。

---

## 0. 先看结论（10 条）

1. **Go2 EDU 的研究价值，一半在狗本体，一半在 Docking Station（扩展坞）。** 扩展坞里可能有一台 Ubuntu 的 Orin Nano 8GB 或 Orin NX 16GB，地址 `192.168.123.18`，用户名 `unitree`、密码 `123`。先确认有没有它，再决定代码放哪跑。✅🟡
2. **开发主路径是"有线 + DDS"，不是手机 App。** App 只用来绑定、升级固件、看状态、做内置建图；真正的数据和控制走 `192.168.123.0/24` 网段的 CycloneDDS。✅
3. **推荐环境是 Ubuntu 22.04 + ROS 2 Humble + CycloneDDS 0.10.2**，`ROS_DOMAIN_ID=0`。Ubuntu 20.04 + Foxy 也可，但新机器没必要。✅
4. **`/cmd_vel` 不是原生接口。** Go2 的高层运动接口是 `/api/sport/request`（SDK 里的 `SportClient`）；Nav2 想控狗，必须自己写一个 `/cmd_vel` → `SportClient.Move` 的桥。✅
5. **`Move()` 是 no-reply 的。** 发出去不会回执，也不会自动停；必须自己计时、限速、超时 `StopMove()`。✅
6. **急停是遥控器的 `L2 长按 + B`（Damping 阻尼模式）**，不是拔电池。实验时遥控器必须在另一个人手里。🟡
7. **EDU 的传感器是"配置项"不是"标配清单"**：Orin 计算模块、Intel D435i 深度相机、MID-360/XT16 外置雷达、D1 机械臂都可能是选配。不要按官网顶配想当然。🟡
8. **一台 Go2 足够做导航、VLN、学习型避障、状态估计、人机交互；不够做多机实机结论、高精度操作、长时间户外。**
9. **本机（Windows + AMD RX 9070 XT）不适合跑 Isaac Lab 训练**（需要 NVIDIA CUDA）。训练放实验室服务器/云，本机做开发、可视化、远端推理客户端。
10. **第一周不要碰低层控制（`/lowcmd`）。** 先用高层接口把"读数据 → 控速 → 急停 → 建图 → 单点导航"跑通；低层控制留到需要自己训练步态策略时。✅

---

## 1. 配置审计：你手里到底是哪台 Go2

Go2 有 AIR / PRO / X / EDU 四档，EDU 内部又分标准版、EDU Plus、EDU-U3/U4 等组合。**官网参数不能代替交付清单**，先填下面这张表。

| 项目 | 怎么查 | 记录 | 影响 |
|---|---|---|---|
| 机型与序列号 | 机身标签、App 设备信息 |  | 决定接口/保修 |
| 固件版本 | App → EMPLACE → 关于/更新 |  | 老固件会限制 App 与接口 |
| App 版本 | 手机应用商店 |  |  |
| 4D LiDAR | 看头顶：L1 还是 L2 |  | L1 15/20 m、L2 30 m；SLAM 配置不同 |
| 前视相机 | App 画面 |  |  |
| 深度相机 | 看机头是否有 D435i 等 |  | VLN/避障的关键 |
| 足端力传感器 | 手册/配置单；`/lowstate` 的 `foot_force` |  | 步态与接触研究 |
| 电池 | 8000 mAh 还是 15000 mAh；几块 |  | 续航 1–2 h vs 2–4 h |
| 充电器 | 33.6V 3.5A 还是 9A |  | 快充约 1 h15 |
| 遥控器 | 是否随附、6 位 ID |  | 急停与接管 |
| Docking Station | 机身背面是否有扩展坞；`ssh unitree@192.168.123.18` | 有/无 | 决定机载算力 |
| 计算模块 | `ssh` 后 `free -h`、`nvpmodel -q`、`cat /etc/nv_tegra_release` | Orin Nano 8GB / NX 16GB / 无 | 能否机载跑模型 |
| 外置雷达 | 是否有 MID-360 / XT16，`ping 192.168.123.20` |  | Unitree SLAM 模块 |
| 机械臂 | 是否有 D1/D1-550 |  | loco-manipulation |
| 网络 | 有线口、Wi-Fi 名称、实验室路由器 |  | 连接方式 |
| 实验室 GPU | `nvidia-smi` |  | 训练/远端推理 |

**三个必做核对命令**（有线连上后）：

```bash
ping 192.168.123.161          # 运动控制 MCU
ping 192.168.123.18           # Docking Station（如果有）
ssh unitree@192.168.123.18    # 密码 123（如果有）
```

在扩展坞里再跑：

```bash
free -h
nvpmodel -q 2>/dev/null || true
ls /unitree/module 2>/dev/null
ros2 topic list 2>/dev/null | head
```

> 如果 `192.168.123.18` ping 不通、机身也没有扩展坞，说明是"纯本体"配置：所有计算放外部 Ubuntu 笔记本，通过本体网口直连。

---

## 2. 规格与能力边界

### 2.1 官方参数（EDU 列）✅

| 项目 | 数值 |
|---|---|
| 站立尺寸 | 70 × 31 × 40 cm |
| 趴下尺寸 | 76 × 31 × 20 cm |
| 重量（含电池） | 约 15 kg |
| 速度 | 0–3.7 m/s（实验室极限约 5 m/s） |
| 最大爬坡 | 40° |
| 最大越障 | 约 16 cm |
| 负载 | 约 8 kg（最大约 12 kg） |
| 关节峰值扭矩 | 约 45 N·m |
| 电池 | 15000 mAh / 432 Wh，续航约 2–4 h |
| 充电 | 33.6V 9A 快充，约 1 h15 |
| 4D LiDAR | L2：360°×96°，0.05–30 m，64000 点/s，精度 2 cm，带 IMU |
| 前视相机 | 高清广角 |
| 深度相机 | EDU 常见配置为 Intel D435i（1280×720@30，848×480@90） |
| 足端力传感器 | EDU 配置 |
| 机载算力 | 8 核 CPU；可选 Orin Nano 8GB（约 40 TOPS）或 Orin NX 16GB（约 100 TOPS） |
| 通信 | Wi-Fi 6 双频、蓝牙 5.2、4G（带 GPS） |
| 二次开发 | EDU 开放 |

### 2.2 研究含义：能做什么、不能做什么

**适合：**

- 室内外平地、草地、楼梯、缓坡上的导航与运动研究；
- 视觉/激光 SLAM、状态估计、语义地图、探索；
- VLN / 目标导航 / 开放词汇导航（相机 + 远端或机载 VLM）；
- 学习型局部避障、CBF 安全滤波、MPC；
- 强化学习步态/地形适应（训练在仿真，部署在狗）；
- 人机交互、社会导航、陪伴/导盲类应用；
- 背负 3–5 kg 的传感器/计算设备。

**不适合或要谨慎：**

- 精细操作（没有臂；加 D1 也只有 6 DoF + 夹爪，负载有限）；
- 高精度重复定位（腿式 + IMU 漂移，厘米级以下很难）；
- 长时间户外（2–4 h 续航，电池更换/充电要规划）；
- 雨雪/涉水（手册未给防护等级，不要假设）；
- 高速动态运动（5 m/s 是实验室极限，室内请限 0.5 m/s 以内）；
- 多机实机结论（一台狗只能证明单机；多机需第二台或纯仿真）。

### 2.3 算力现实

- 纯本体 + 外部笔记本：所有感知/模型跑在笔记本或服务器，机器狗只执行速度指令。**推荐作为第一周方案。**
- 有 Orin NX 16GB：可机载跑检测/分割/小 VLM（几 B 参数、量化后），大模型仍要远端。
- 有 Orin Nano 8GB：机载跑轻量检测、点云处理、导航栈；不要指望跑 7B 模型。
- 本机 AMD RX 9070 XT **没有 CUDA**：Isaac Lab / Isaac Sim 训练不可用；PyTorch ROCm 在 Windows 支持有限，建议训练上服务器。

---

## 3. 第一次开机（Day 0）

### 3.1 开箱与上电

1. 在平整、防滑、2 m 内无人的地面开箱；先读随机《用户手册》和保修卡。
2. 电池从侧面插入电池槽，注意方向（电源键朝上），听到"咔哒"声即到位；不要硬压。🟡
3. 首次使用先充电到满；用原装 33.6V 9A 快充，约 1 h15。不要用非原装充电器。
4. 开机：短按电池上的电源键，等待提示音/指示灯；机器人默认趴姿。
5. 关机：优先用 App 的关机入口；或长按电源键至提示音后松手。**不要直接拔电池。**
6. 第一次站立前，确认四周 2 m 无人、地面无台阶/线缆。

> 具体按键时长不同批次可能不同，以随机手册和 App 提示为准。❗

### 3.2 急停与接管（必须先练）

| 操作 | 按键（遥控器） | 说明 |
|---|---|---|
| **急停/阻尼** | `L2` 长按 + `B` 单击 | 立即进入 Damping，切断运动；这是实验中的第一反应 |
| 站立/趴下 | `L2` 长按 + `A` 单击 | 锁定当前姿态或趴下；连按两次回站立 |
| 恢复站立 | `L2` 长按 + `X` 单击 | 摔倒后起身 |
| 默认步态 | `START` | 解锁/恢复默认步态 |
| 普通步态 | `L1` 长按 + `START` |  |
| 经典步态 | `RIGHT` 长按 + `START` |  |
| 自由行走 | `LEFT` 长按 + `START` |  |
| 避障开 | `X` 单击 | 默认开 |
| 避障关 | `Y` 长按 3 s |  |
| 奔跑 | `L2` 长按 + `START` | 室内不要用 |
| 耐力模式 | `L1` 长按 + `SELECT` |  |

> 表来自代理商手册（🟡），不同固件可能不同。**上手第一件事：在空地上把"急停 → 阻尼 → 恢复站立"各练 3 次。**

### 3.3 App 绑定与固件

1. 手机装 **Unitree Go**，注册/登录。
2. 打开狗电源和手机蓝牙，App 首页添加机器人，选择设备绑定。
3. 选择连接方式：
   - **AP 模式**：狗开热点（`GO2-XXXXXX`，8 位密码），手机连该热点；常见热点地址 `192.168.12.1`（以实机为准）。❗
   - **Wi-Fi 模式**：狗连实验室路由器，手机与狗同一局域网。
4. 绑定后先做固件升级（EMPLACE → 关于/更新）。老固件会限制 App 和接口。✅
5. 在 App 里逐个试：站立、趴下、急停、灯光、音量、避障开关、内置建图。

### 3.4 第一次程序控制（空场地）

顺序必须是：

```
趴姿 → StandUp → BalanceStand → Move(0.1, 0, 0) 0.5 s → StopMove → StandDown
```

不要第一次就 `Move(0.5, 0, 0.5)`。用本文 `tools/go2_move.py`：

```bash
python3 go2_move.py --iface eth0 --stand --vx 0.1 --duration 1 --yes
```

---

## 4. 网络与连接（Day 1）

### 4.1 三种拓扑，先选一种

| 方案 | 适用 | 优点 | 缺点 |
|---|---|---|---|
| A. 手机 App | 绑定、固件、内置建图 | 最快 | 不能跑代码 |
| B. 笔记本有线接狗 | 开发主路径 | 稳定、低延迟 | 需要 Ubuntu/网卡配置 |
| C. 扩展坞（Orin）机载 | 部署实验 | 少一根网线、可脱离笔记本 | 算力有限、环境要配 |

**推荐：B 开发 + C 部署；A 只做配置。**

### 4.2 IP 表（重要）

| 设备 | IP | 账号/密码 | 来源 |
|---|---|---|---|
| 运动控制 MCU | `192.168.123.161` | — | ✅ |
| Docking Station / 扩展坞 | `192.168.123.18` | `unitree` / `123` | ✅🟡 |
| 外置 LiDAR（MID-360/XT16） | `192.168.123.20` | — | 🟡 |
| 你的 Ubuntu 笔记本（有线） | `192.168.123.99/24` | — | ✅ |
| 备选笔记本地址 | `192.168.123.51/24` | — | 🟡 |
| 套装路由器（若有） | `192.168.123.100` | `mybotshop` | 🟡 |
| App AP 热点 | 常见 `192.168.12.1` | App 设置 | ❗ |

**不要用 `.18`、`.161`、`.20` 作为你笔记本的地址。**

### 4.3 Ubuntu 有线配置

临时：

```bash
ip -br addr                       # 找到接狗的有线网卡，如 enp3s0
sudo ip addr add 192.168.123.99/24 dev enp3s0
sudo ip link set enp3s0 up
ping 192.168.123.161
ping 192.168.123.18
```

持久化（netplan）：

```bash
sudo tee /etc/netplan/60-go2.yaml > /dev/null <<'EOF'
network:
  version: 2
  ethernets:
    enp3s0:
      addresses: [192.168.123.99/24]
      dhcp4: false
EOF
sudo chmod 600 /etc/netplan/60-go2.yaml
sudo netplan apply
```

> 只保留"接狗"这块网卡，其它网卡（Wi-Fi、VPN、Clash TUN）先禁用。多网卡是 DDS 收不到话题的第一大原因。

### 4.4 Windows 有线配置（如果暂时没有 Ubuntu 机器）

```powershell
Get-NetAdapter
New-NetIPAddress -InterfaceAlias "以太网" -IPAddress 192.168.123.99 -PrefixLength 24
ping 192.168.123.161
```

但**不要在 WSL2 默认 NAT 模式下调 DDS**：WSL2 的虚拟网卡收不到宿主物理网卡的组播，`ros2 topic list` 会是空的。两个办法：

1. Windows 11 22H2+ 打开 WSL2 镜像网络：`%USERPROFILE%\.wslconfig`
   ```ini
   [wsl2]
   networkingMode=mirrored
   ```
   然后 `wsl --shutdown` 重启。**本机是 Windows 11 25H2，支持该模式，可尝试。**
2. 更稳：用原生 Ubuntu 笔记本，或直接在扩展坞里跑。

### 4.5 验证 DDS

```bash
# 方案一：官方 ROS2 包
source ~/unitree_ros2/setup.sh
ros2 topic list
ros2 topic echo /sportmodestate --once

# 方案二：SDK2 Python 现成例子
python3 example/go2/high_level/go2_sport_client.py eth0
python3 example/go2/front_camera/camera_opencv.py eth0
python3 example/go2/high_level/go2_utlidar_switch.py eth0
```

看到 `/sportmodestate` 有数据 = 链路通。没有数据按第 11 节排查。

---

## 5. 只读数据验收（Day 1–2）

### 5.1 装 SDK2 Python

```bash
sudo apt update
sudo apt install -y python3-pip git
git clone https://github.com/unitreerobotics/unitree_sdk2_python.git
cd unitree_sdk2_python
pip3 install -e .
```

> **必须用 Python 3.10**（Ubuntu 22.04 系统自带）。`cyclonedds==0.10.2` 只发布到 cp310 的 wheel；Python 3.12 没有 wheel，会走源码编译，缺 C 库时直接失败。🟡（本机实测）

若报 `Could not locate cyclonedds`：

```bash
git clone https://github.com/eclipse-cyclonedds/cyclonedds -b releases/0.10.x
cd cyclonedds && mkdir -p build install && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=../install
cmake --build . --target install
export CYCLONEDDS_HOME=~/cyclonedds/install
cd ~/unitree_sdk2_python && pip3 install -e .
```

### 5.2 DDS 频道表（SDK2）✅

| 频道 | 类型 | 方向 | 内容 |
|---|---|---|---|
| `rt/lowstate` | `LowState_` | 订阅 | 电机、IMU、BMS、足端力、遥控器原始值（`wireless_remote[40]`） |
| `rt/sportmodestate` | `SportModeState_` | 订阅 | 位置、速度、步态、身体高度、足端力 |
| `rt/utlidar/cloud` | `PointCloud2_` | 订阅 | 4D LiDAR 点云 |
| `rt/utlidar/switch` | `String_` | 发布 | `"ON"` / `"OFF"` 开关雷达 |
| `rt/lowcmd` | `LowCmd_` | 发布 | 低层关节控制（危险） |
| `rt/api/sport/request` | `Request_` | 发布 | 高层运动请求 |

> 遥控器没有单独的 SDK 频道：摇杆和按键在 `rt/lowstate` 的 `wireless_remote[40]` 里（解析方法见 `unitree_sdk2py/utils/joystick.py`）。ROS2 侧才会额外发布 `/wirelesscontroller`。✅

ROS2 侧同名话题去掉 `rt/` 前缀，另有低频版本 `lf/lowstate`、`lf/sportmodestate`。✅

### 5.3 用本文工具跑通

```bash
cd tools
python3 go2_status.py --iface eth0            # 只读状态
python3 go2_record.py --iface eth0 --out run1.csv --seconds 30
```

`go2_status.py` 会打印：电池 SOC/电压/电流、IMU 姿态与温度、电机最高温度、足端力、运动模式/步态/位置/速度、遥控器摇杆。

**本机已验证**：在 WSL Ubuntu 22.04 里用 `fake_go2.py` 发布假的 `rt/lowstate` 与 `rt/sportmodestate`，`go2_status.py` 与 `go2_record.py` 均能正常接收并落盘。这证明频道名、IDL 字段、脚本逻辑正确；**仍未在真机上验证**。

### 5.4 相机与雷达

- **前视相机**：SDK2 的 `VideoClient.GetImageSample()` 返回 JPEG 字节流，示例见 `example/go2/front_camera/camera_opencv.py`。✅
- **深度相机**：SDK2 默认不提供；若是 D435i，通常在扩展坞上以 USB 设备出现，用 `rs-enumerate-devices` / `realsense2_camera` 接。❗
- **4D LiDAR**：`rt/utlidar/cloud`，frame 常为 `utlidar_lidar`；点云在雷达坐标系下，RViz 里看起来"上下颠倒/斜的"是正常的，要加 TF 或按外参变换。🟡
- 雷达默认可能关闭，用 `go2_utlidar_switch.py eth0` 开。✅

### 5.5 数据验收标准

- [ ] `/lowstate` 频率稳定（真机通常数百 Hz），`tick` 递增；
- [ ] `/sportmodestate` 有位置/速度/步态；
- [ ] 图像能取到，分辨率/帧率/时间戳记录；
- [ ] 点云能取到，frame_id、频率、范围记录；
- [ ] 录一段 30 s 的 CSV/bag，断开狗后能离线回放；
- [ ] 能识别"数据超时/图像滞后/雷达无点"。

---

## 6. 控制（Day 2）

### 6.1 高层 SportClient（推荐）✅

| 方法 | 作用 | 备注 |
|---|---|---|
| `StandUp()` | 站起 |  |
| `StandDown()` | 趴下 |  |
| `BalanceStand()` | 平衡站立 |  |
| `Damp()` | 阻尼/急停 | 软停 |
| `StopMove()` | 停止移动 | **每次 Move 后必须调** |
| `RecoveryStand()` | 摔倒恢复 |  |
| `Move(vx, vy, vyaw)` | 速度控制 | **no-reply**，需自己计时 |
| `Sit()` / `RiseSit()` | 坐下/起立 |  |
| `SpeedLevel(level)` | 速度档位 |  |
| `Euler(roll,pitch,yaw)` | 姿态控制 | 小心 |
| `SwitchAvoidMode()` | 切换避障模式 |  |
| `FreeAvoid(bool)` / `FreeWalk()` | 自由避障/自由走 |  |
| `HandStand` / `FreeJump` / `FrontFlip` 等 | 特技 | 不要在研究实验里用 |

### 6.2 安全封装（必须自己写）

```python
# 伪代码
vx = clamp(vx, -0.5, 0.5)
vy = clamp(vy, -0.3, 0.3)
vyaw = clamp(vyaw, -0.8, 0.8)
t0 = time.time()
while time.time() - t0 < duration:
    client.Move(vx, vy, vyaw)
    time.sleep(0.1)
    if watchdog_expired() or remote_override():
        break
client.StopMove()
```

本文 `tools/go2_move.py` 已实现：限幅、总时长上限 10 s、Ctrl-C/异常自动 `StopMove`、`--dry-run` 空跑、交互确认。

### 6.3 低层控制（先不要碰）

低层通过 `rt/lowcmd` 以约 500 Hz 发 12 个关节的 `q/dq/tau/kp/kd`，需要：

1. 用 `MotionSwitcherClient` 关掉原厂 sport 模式；
2. 自己算 CRC；
3. 自己保证关节限位、力矩限幅、摔倒保护。

官方示例 `example/go2/low_level/go2_stand_example.py` 可以看，但**第一次上机不要跑**。低层控制错误可能烧电机或摔狗。✅

---

## 7. 建图与导航（Week 1–2）

### 7.1 三条路线

| 路线 | 组成 | 适合 | 限制 |
|---|---|---|---|
| A. App 内置建图 | Unitree Go + L1/L2 | 最快验收 | 黑盒、难导出、难改 |
| B. ROS2 + LIO + Nav2 | Point-LIO/FAST-LIO2 + Nav2 | 研究主路径 | 要自己搭桥、调参 |
| C. Unitree SLAM 模块 | 扩展坞 + MID-360/XT16 + `unitree_slam` | 官方方案 | 需要选配硬件 |

### 7.2 路线 A：App 内置 3D 建图

官方说明：用 L2 雷达 + App 可构建点云地图，并指定路径让 Go2 自主移动。🟡✅

操作要点：

1. 空旷、光照稳定、少动态行人；
2. 从固定起点开始，慢速（≤0.3 m/s）走完整个区域；
3. 同一区域走两遍，提升点云密度；
4. 建完后在 App 里设目标点/路径，先空载试跑；
5. 记录起点、地图范围、失败点。

> 这条路线只用于"证明狗能自主走"，不能作为论文的实验平台。

### 7.3 路线 B：ROS2 + Point-LIO + Nav2

推荐组件：

- **LIO**：Unitree 官方为 L2 提供 [point_lio_unilidar](https://github.com/unitreerobotics/point_lio_unilidar)（Point-LIO + L2 内置 IMU，无需其它定位传感器）。✅
- **里程计**：LIO 输出 `odom` → `base_link`；四足的 `base_link` 会随身体起伏，建议加 `base_footprint` 或对 z/pitch/roll 做低通。
- **Nav2**：`nav2_bringup` + 自定义 `/cmd_vel` 桥。
- **桥**：订阅 `/cmd_vel`，转成 `SportClient.Move(vx, vy, vyaw)`，并做限幅/超时/急停。本文 `tools/go2_cmdvel_bridge.py` 已实现，`--dry-run` 可无狗联调。
- **代价地图**：四足 footprint 不要照抄 Hunter；按实际机身包络 + 0.05 m 余量；`inflation_radius` 从 0.35–0.45 m 起调。
- **定位**：AMCL 可用，但腿式漂移大；建议 LIO + 地图配准，或直接 LIO 里程计 + 局部代价地图。

最小闭环：

```text
建图（LIO）→ 保存 pcd → 定位（LIO/AMCL）→ Nav2 单点 → /cmd_vel 桥 → SportClient.Move → 到点 StopMove
```

### 7.4 路线 C：Unitree SLAM 模块（如果有扩展坞 + 外置雷达）

官方/代理商流程（🟡，以实际模块为准）：

```bash
ssh unitree@192.168.123.18
cd /unitree/module/unitree_slam/bin
sudo ./unitree_slam          # 终端 1
sudo ./mid360_driver         # 终端 2（或 xt16_driver）
sudo ./keyDemo eth0          # 终端 3
```

按 `Q` 开始建图，慢速走两遍，`W` 停止；回到起点，`A` 重定位，`S` 设节点，`D` 开始循环导航。注意：节点间距 ≥1.5 m、目标距离 ≤10 m、障碍物高度 ≥20 cm、关闭原厂避障。🟡

### 7.5 与 Hunter 项目的差异（重要）

| 维度 | Hunter | Go2 |
|---|---|---|
| 运动学 | 阿克曼/差速 | 腿式，身体高度/姿态可变 |
| 里程计 | 轮速 + IMU | 足端/IMU/LIO，漂移特性不同 |
| footprint | 车体包络 | 四足站立包络 + 摆动余量 |
| 台阶 | 不能 | 能（≤16 cm） |
| 控制接口 | `/cmd_vel` 原生 | `/api/sport/request`，需桥 |
| 参数 | 已有 nav2_params | **不能直接复用**，必须重调 |

---

## 8. 仿真与训练（Week 2+）

### 8.1 unitree_mujoco（接口验证）

- 支持 Go2，C++/Python 两个版本；
- **只支持低层**（`LowCmd`/`LowState`/`SportModeState`），不模拟原厂 sport 服务；
- 仿真 domain 默认 1、网卡 `lo`；真机 domain 0；
- 用途：验证低层控制器、状态机、DDS 链路，不是导航仿真。

```bash
# 仿真
./unitree_mujoco -r go2 -s scene_terrain.xml
# 控制程序（无网卡参数时自动连仿真 domain 1）
python3 example/python/stand_go2.py
```

### 8.2 unitree_rl_lab（Isaac Lab，需 NVIDIA）

- 支持 Go2/H1/G1；
- 依赖 Isaac Sim 5.1 + Isaac Lab 2.3 + CUDA；
- **本机 AMD 9070 XT 不可用**；用实验室 RTX 4090/A100 服务器或云。

### 8.3 常用开源资产

- `mujoco_menagerie` 的 Go2 MJCF：快速做运动学/可视化；
- `unitree_ros`：Go2 URDF/网格；
- `point_lio_unilidar`：L2 建图；
- `Nav2`：导航栈。

### 8.4 Sim2Real 检查清单

- [ ] 关节顺序、符号、零位与真机一致；
- [ ] 电机限幅、力矩限幅、温度保护；
- [ ] 观测延迟、控制频率与真机一致；
- [ ] 地形/摩擦/质量随机化覆盖真机；
- [ ] 先在仿真里跑 10 次，再上狗；上狗先吊起来/趴姿测试。

---

## 9. 安全与运维

### 9.1 电池

- 电量低于 20% 不要做剧烈动作；低电量会趴下（手册提示约 10 min 预警）。🟡
- 长期存放保持 40–60%，每 1–2 个月补电；
- 鼓包、异味、异常发热立即停用；
- 充电时有人在场，不覆盖散热孔。

### 9.2 关节与散热

- 连续高扭矩（爬坡、跳跃、负载）后摸关节温度；烫手就休息；
- 不要在超过 35 °C 的环境长时间满负载；
- 摔倒后先 `Damp`，再检查腿部/线缆，再 `RecoveryStand`。

### 9.3 实验 SOP

1. 场地：平整、防滑、边界清楚、2 m 内无人；
2. 人员：一人操作、一人持遥控器急停、一人记录；
3. 开机顺序：狗 → 遥控器 → 网络 → 程序；
4. 关机顺序：程序 `StopMove` → `StandDown` → 关程序 → 关狗；
5. 每次实验记录：固件版本、电池、地图、参数、失败现象；
6. 不在狗身上放尖锐/易掉落物；负载用扎带+防滑垫。

### 9.4 保修与固件

- EDU 保修 12 个月（官网）；自行拆机/改线可能失去保修；
- 固件升级前记录当前版本；升级后重新验证接口；
- 不要混用不同来源的 `unitree_sdk2`/`unitree_ros2` 版本。

---

## 10. 验收清单

### Day 0：能安全地让它动、让它停

- [ ] 电池正确安装、充满；
- [ ] App 绑定成功、固件最新；
- [ ] 遥控器配对，`L2+B` 急停练 3 次；
- [ ] 站立/趴下/恢复站立各 3 次；
- [ ] 记录固件、App、序列号。

### Day 1：能读数据

- [ ] 有线 `ping 192.168.123.161`；
- [ ] `ros2 topic list` 有 `/sportmodestate` `/lowstate` `/utlidar/cloud`；
- [ ] `go2_status.py` 打印电池/IMU/电机温度/足端力；
- [ ] 录 30 s CSV，行数 > 1000；
- [ ] 前视相机出图；
- [ ] 雷达点云在 RViz 可见。

### Day 2：能控速、能停

- [ ] `StandUp` → `Move(0.1,0,0)` 1 s → `StopMove`；
- [ ] 超时保护：程序被杀后狗在 1 s 内停；
- [ ] 遥控器接管优先；
- [ ] 记录 3 次成功、3 次失败。

### Week 1：能建图、能单点导航

- [ ] 建一张 20 m × 20 m 室内图；
- [ ] 重复定位 5 次，记录误差；
- [ ] Nav2 单点导航 10 次，记录成功率/碰撞/接管；
- [ ] 失败分类：定位/感知/规划/执行/到点。

### Week 2：能跑一个基线

- [ ] 选一个公开基线（如 Point-LIO + Nav2，或 StreamVLN 推理）；
- [ ] 固定任务、固定起点、固定评测；
- [ ] 有对照（人工遥控/纯 Nav2）；
- [ ] 有成本记录（推理延迟、调用次数、功耗）。

---

## 11. 故障排查

| 现象 | 可能原因 | 处理 |
|---|---|---|
| `ping 192.168.123.161` 不通 | 网卡没配 IP、网线、狗没开机 | `ip -br addr`；换网线；确认狗已启动 |
| `ros2 topic list` 为空 | `ROS_DOMAIN_ID` 不是 0；没用 CycloneDDS；多网卡；防火墙 | `export ROS_DOMAIN_ID=0`；`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`；`CYCLONEDDS_URI` 指定网卡；关防火墙 |
| SDK 返回 3102 | 网络不通/服务未起 | 先 ping，再确认 `sport` 服务在跑 |
| `Move` 没反应 | 未站立/未切 locomotion；遥控器接管；急停中 | 先 `StandUp`+`BalanceStand`；看 `/sportmodestate` 的 `mode` |
| 狗走一下停一下 | `Move` 超时/未重发 | 10 Hz 重发；或改用轨迹接口 |
| 相机黑屏 | 光线太暗、被占用、驱动问题 | 换环境；重启程序；查 `VideoClient` 返回码 |
| 雷达无点云 | 雷达被关 | `go2_utlidar_switch.py eth0` 开；查 `/utlidar/cloud` |
| RViz 点云上下颠倒 | 雷达坐标系方向 | 加 TF/外参，不要改数据 |
| 狗突然趴下 | 低电量/过热/保护 | 查 `soc`、电机温度；冷却/充电 |
| 程序崩了狗还在走 | 没有 finally `StopMove` | 所有控制代码必须 try/finally + 看门狗 |
| App 连不上 | 热点/路由器/蓝牙 | 重启 App；用 AP 模式；检查 2.4G/5G |

---

## 12. 参考与工具

### 官方

- Go2 产品页：https://www.unitree.com/go2
- 4D LiDAR L2：https://www.unitree.com/L2
- 文档中心：https://support.unitree.com/main/en
- SDK2（C++）：https://github.com/unitreerobotics/unitree_sdk2
- SDK2（Python）：https://github.com/unitreerobotics/unitree_sdk2_python
- ROS2 支持：https://github.com/unitreerobotics/unitree_ros2
- unitree_mujoco：https://github.com/unitreerobotics/unitree_mujoco
- unitree_rl_lab：https://github.com/unitreerobotics/unitree_rl_lab
- Point-LIO（L2）：https://github.com/unitreerobotics/point_lio_unilidar

### 第三方/实践

- TechShare Go2 SDK/ROS 设置（日文，2026-09 更新）：https://techshare.co.jp/faq/unitree/unitree-go2_pc_lan.html
- TechShare Go2 NAT 联网：https://techshare.co.jp/faq/unitree/go2_r1_nat_internet.html
- Weston Robot Go2 SLAM 指南（2026-09 更新）：https://docs.westonrobot.com/guides/unitree/go2_slam/
- MYBOTSHOP Go2 手册（85 页，含遥控器按键表）：https://www.docs.mybotshop.de/downloads/GO2_User_Manual.pdf

### 本文附带工具

| 文件 | 用途 | 状态 |
|---|---|---|
| `tools/go2_status.py` | 只读状态 | 已用假 Go2 验证 |
| `tools/go2_record.py` | 录 CSV | 已用假 Go2 验证 |
| `tools/go2_move.py` | 安全速度控制 | 编译/空跑通过；待实机 |
| `tools/go2_cmdvel_bridge.py` | `/cmd_vel` → `SportClient` | ROS2 联调通过；待实机 |
| `tools/fake_go2.py` | 本地假狗 | 已验证 |
| `tools/README.md` | 安装与用法 | — |

---

## 附：第一周每天做什么

| 天 | 目标 | 产出 |
|---|---|---|
| D1 | 开箱、App、急停、站立 | 配置表、急停记录 |
| D2 | 有线网络、DDS、读状态 | `ros2 topic list` 截图、30 s CSV |
| D3 | 相机、雷达、录制 | 图像/点云样例、bag |
| D4 | SportClient 控速、超时保护 | 3 次成功视频/日志 |
| D5 | 建图（App 或 LIO） | 一张 pcd/地图 |
| D6 | Nav2 单点导航 | 10 次结果表 |
| D7 | 复盘、定下周实验 | 失败分类、参数表 |
