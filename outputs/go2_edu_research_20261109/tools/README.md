# Go2 工具包

四个脚本，覆盖"只读状态 → 录数据 → 安全控速 → 无狗测试"，外加一个 Nav2 桥。

## 0. 安装（Ubuntu 22.04）

一键脚本（会 `sudo apt`，但**不改网络、不动机器人**）：

```bash
bash setup_go2_ubuntu.sh              # 只装 SDK2
bash setup_go2_ubuntu.sh --with-ros2  # 同时编译 unitree_ros2
```

手动步骤：

```bash
sudo apt update
sudo apt install -y python3-pip git
git clone https://github.com/unitreerobotics/unitree_sdk2_python.git
cd unitree_sdk2_python
pip3 install -e .
```

若报 `Could not locate cyclonedds`，先编译 CycloneDDS 0.10.x：

```bash
git clone https://github.com/eclipse-cyclonedds/cyclonedds -b releases/0.10.x
cd cyclonedds && mkdir -p build install && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=../install
cmake --build . --target install
export CYCLONEDDS_HOME=~/cyclonedds/install
cd ~/unitree_sdk2_python && pip3 install -e .
```

> Windows 上 `cyclonedds==0.10.2` 只有到 cp310 的 wheel；用 Python 3.12 会源码编译失败。**在 WSL/Ubuntu 的 Python 3.10 里装最省事。**
> 本机 WSL 的实测路径：`get-pip.py --user` + `pip install --user cyclonedds==0.10.2` + `pip install --user -e unitree_sdk2_python`。

## 1. 只读状态

```bash
python3 go2_status.py --iface eth0
python3 go2_status.py --iface eth0 --seconds 10 --json
```

打印：电池 SOC/电压/电流、IMU 姿态/温度、电机最高温度、足端力、运动模式/步态/位置/速度、遥控器摇杆。
**只订阅，不发送任何控制指令。**

## 2. 录数据

```bash
python3 go2_record.py --iface eth0 --out run1.csv --seconds 30
python3 go2_record.py --iface eth0 --out run1.csv --max-hz 50   # 限频
```

CSV 列：时间、tick、电压/电流/SOC、IMU 温度、rpy、12 个关节的 q/dq/tau/temp、4 个足端力。

## 3. 安全控速

```bash
# 空跑，看会发什么
python3 go2_move.py --dry-run --vx 0.2 --duration 2

# 实机：先站起，0.2 m/s 前进 2 s
python3 go2_move.py --iface eth0 --stand --vx 0.2 --duration 2

# 转圈
python3 go2_move.py --iface eth0 --vyaw 0.3 --duration 2 --yes
```

安全设计：

- 限幅 `vx ±0.5 / vy ±0.3 / vyaw ±0.8`；
- 总时长上限 10 s；
- Ctrl-C/异常/结束都 `StopMove`；
- 默认交互确认，`--yes` 跳过；
- 不碰低层控制，遥控器始终优先。

> `Move()` 是 no-reply，脚本会以 10 Hz 重发；这是"持续速度"而不是"走 2 秒就自动停"。

## 4. Nav2 桥（/cmd_vel → SportClient）

```bash
# 无狗联调：只打印
python3 go2_cmdvel_bridge.py --dry-run

# 实机
python3 go2_cmdvel_bridge.py --iface eth0
```

- 订阅 `/cmd_vel`（`geometry_msgs/Twist`），10 Hz 转成 `SportClient.Move`；
- 限幅 `vx ±0.5 / vy ±0.3 / vyaw ±0.8`；
- 0.5 s 没有新指令就 `StopMove`；
- Ctrl-C 退出时 `StopMove`。

Nav2 侧把 `controller_server` 的 `cmd_vel` 重映射到这个节点即可，例如：

```bash
ros2 run nav2_bringup navigation_launch.py ...
ros2 run <your_pkg> go2_cmdvel_bridge.py --iface eth0 --ros-args -r /cmd_vel:=/cmd_vel_nav
```

## 5. 无狗测试（假 Go2）

用一个进程在 DDS 上发布假的 `rt/lowstate` 和 `rt/sportmodestate`，另一个进程订阅：

```bash
# 终端 1
python3 fake_go2.py --iface eth0 --domain 1 --seconds 30

# 终端 2
python3 go2_status.py --iface eth0 --domain 1 --seconds 10
python3 go2_record.py --iface eth0 --domain 1 --out fake.csv --seconds 5
```

**注意**：真机 domain 是 0，假狗用 1，避免误连真机。仿真（unitree_mujoco）默认也是 domain 1。

## 6. 已验证 / 未验证

| 脚本 | 状态 |
|---|---|
| `go2_status.py` | ✅ 在本机 WSL + `fake_go2.py` 真实 DDS 收发通过 |
| `go2_record.py` | ✅ 同上，CSV 30 行/3 s 正常 |
| `fake_go2.py` | ✅ 通过 |
| `go2_move.py` | ✅ 编译 + `--dry-run`；❌ 未接实机 |
| `go2_cmdvel_bridge.py` | ✅ 在 WSL ROS2 Humble 中用 `ros2 topic pub` 发布 `/cmd_vel`，收指令、限幅、0.5 s 超时停车均通过；❌ 未接实机 |
| `setup_go2_ubuntu.sh` | ⚠️ 未在本机执行（WSL 无 sudo）；按官方文档写成，首次在实验室机器上跑时请逐段确认 |

真机第一次跑 `go2_move.py` 前，务必：

1. 场地 2 m 内无人、无台阶；
2. 有人手持遥控器，`L2 长按 + B` 急停；
3. 先 `--vx 0.1 --duration 1`；
4. 看 `go2_status.py` 的 `mode` 是否为 3（locomotion）。

## 7. 排障

| 现象 | 处理 |
|---|---|
| `3 秒内没有收到 rt/lowstate` | 网卡名错、网线、domain 错（真机 0 / 仿真 1）、防火墙 |
| `SportClient` 调用返回 3102 | 网络不通或 `sport` 服务没起 |
| `Move` 没反应 | 没 `StandUp`、没进 locomotion、遥控器接管、急停中 |
| `cyclonedds` 装不上 | 用 Python 3.10；设 `CYCLONEDDS_HOME` |
| WSL 下收不到 | WSL2 默认 NAT 收不到物理网卡组播；开 mirrored 或换原生 Ubuntu |

