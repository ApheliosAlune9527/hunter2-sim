# Go2 EDU 第一天验收清单（一页纸）

日期：______  操作人：______  见证人（持遥控器）：______
机器序列号：____________  固件：____________  App：____________

> 场地要求：平整防滑、2 m 内无人、无台阶/线缆；遥控器在见证人手里，`L2 长按 + B` 是急停。

## A. 开箱与安全（30 min）

- [ ] 电池正确插入（听到"咔哒"），电量 > 50%
- [ ] 原装 33.6V 9A 充电器确认
- [ ] 遥控器配对（6 位 ID）
- [ ] 急停练习 3 次：`L2 长按 + B` → 狗进入阻尼 → `L2 长按 + A` 恢复
- [ ] 站立 / 趴下 / 恢复站立 各 3 次
- [ ] 记录：电池型号 ______ mAh；充电器 ______ A；遥控器 ID ______

## B. 配置审计（20 min）

- [ ] 头顶雷达：L1 / L2（圈一个）
- [ ] 前视相机：有 / 无
- [ ] 深度相机：型号 ____________（D435i / 无 / 其它）
- [ ] 足端力传感器：有 / 无（App 或配置单）
- [ ] Docking Station：有 / 无；`ping 192.168.123.18`
- [ ] 扩展坞算力：`ssh unitree@192.168.123.18`（密码 123）→ `free -h`、`nvpmodel -q`
- [ ] 外置雷达：MID-360 / XT16 / 无；`ping 192.168.123.20`
- [ ] 机械臂：D1 / 无
- [ ] 实验室 GPU：____________（`nvidia-smi`）

## C. 网络（20 min）

笔记本 Ubuntu：

```bash
ip -br addr
sudo ip addr add 192.168.123.99/24 dev <网卡名>
sudo ip link set <网卡名> up
ping 192.168.123.161        # 必通
ping 192.168.123.18         # 有扩展坞才通
```

- [ ] `192.168.123.161` 通
- [ ] 只保留接狗网卡，关 Wi-Fi/VPN/Clash TUN
- [ ] `ROS_DOMAIN_ID=0`
- [ ] `ros2 topic list` 能看到 `/sportmodestate` `/lowstate` `/utlidar/cloud`
- [ ] `ros2 topic echo /sportmodestate --once` 有数据

## D. 只读数据（30 min）

```bash
cd tools
python3 go2_status.py --iface <网卡名>
python3 go2_record.py --iface <网卡名> --out ../logs/day1.csv --seconds 30
```

- [ ] 电池 SOC / 电压 / 电流有数
- [ ] IMU 姿态有数、电机温度有数、足端力有数
- [ ] 运动模式/步态/位置有数
- [ ] CSV 行数 > 500
- [ ] 前视相机出图（`camera_opencv.py`）
- [ ] 雷达点云可见（RViz，frame `utlidar_lidar`）

记录：`/lowstate` 频率 ______ Hz；图像分辨率 ______；点云频率 ______ Hz

## E. 控速（20 min，空场地）

```bash
python3 go2_move.py --iface <网卡名> --stand --vx 0.1 --duration 1 --yes
```

- [ ] 前进 0.1 m/s × 1 s，狗平稳走
- [ ] 程序 Ctrl-C 后狗 1 s 内停（`StopMove`）
- [ ] 遥控器随时能接管
- [ ] `--vx 0.5` 限幅生效（日志有 warn）
- [ ] 记录 3 次成功 / 3 次异常：____________________

## F. 建图（30 min，二选一）

- [ ] App 内置 3D 建图：走完 20 m × 20 m，地图保存
- [ ] 或 ROS2 + Point-LIO：`ros2 launch ...`，保存 pcd
- [ ] 回到起点重定位，误差 ______ m
- [ ] 记录：地图范围 ______；失败点 ______

## G. 收尾

- [ ] `StopMove` → `StandDown` → 关程序 → 关狗
- [ ] 电池电量 ______%，充电
- [ ] 数据备份到 `outputs/go2_edu_research_20261109/logs/`
- [ ] 填写失败/异常：____________________________

## 常见卡点（先查这三条）

1. `ping` 不通 → 网卡 IP/网线/狗没开机。
2. `ros2 topic list` 空 → `ROS_DOMAIN_ID=0`、CycloneDDS、多网卡、防火墙。
3. `Move` 没反应 → 没 `StandUp`/没进 locomotion、遥控器接管、急停中。

## 今日必须带回的三样东西

1. 配置表（B 节）
2. 30 s `day1.csv` + 一张相机图 + 一张点云截图
3. 3 条"狗不听话"的现场记录（现象 + 当时模式 + 处理）
