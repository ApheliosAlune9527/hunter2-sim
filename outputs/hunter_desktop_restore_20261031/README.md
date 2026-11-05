# HUNTER 2.0 台式机恢复记录

更新时间：2026-10-31。当前项目位于 `D:\rob-memory`，WSL 内对应 `/mnt/d/rob-memory`。

## 已完成

- 10 月 21 日完整包项目基线与 10 月 31 日增量已经合并；增量为 450 个新增文件、14 个更新文件，无冲突。近期交接上下文保存在本目录的 `用户交接上下文.txt`。
- 当前完整模型的 PowerShell/Bash 入口、观察 launch、场景网格 URI 和检查器已适配 D 盘。重新生成当前场景与封存清单，严格检查仍有效；场景语义除网格资源路径外未改变。
- 修正了场景生成器在 Windows 和 Linux 上的换行差异，保证两端生成相同字节。模型包的原始 19 个文件没有改动。
- 已安装微软官方、签名和 SHA256 均通过核验的 WSL 3.0.3；WSL2 内核为 6.18.54.1，WSLg 为 1.0.79。
- 已将原虚拟磁盘注册为 `Ubuntu-22.04`，并以 `aphelios` 用户成功进入 Ubuntu 22.04.5。磁盘注册前已核验与完整包快照的哈希一致；启动后磁盘正常产生运行状态变化，不再将其视为只读快照。
- 已核对 ROS Humble、Gazebo 6.18、CycloneDDS、ros_gz_bridge、robot_state_publisher、pointcloud_to_laserscan 与 colcon。
- 从 D 盘已校验的模型源码，在 `/home/aphelios/hz_sim_ws/src/hz_hunter_full_description` 创建了独立的原生 Linux 源码副本，并用 colcon 重新构建安装。没有复制笔记本的 build/install 链接。
- 当前环境文件及恢复用户的 `.bashrc` 已将旧 NVIDIA 选择改为 `Radeon RX 9070 XT`。WSL 的 `glxinfo -B` 实测返回 `D3D12 (AMD Radeon RX 9070 XT)`、`Accelerated: yes`；这仅确认 OpenGL 设备加速，不等于 Gazebo GUI 或传感器运行验收。适配器选择依据 [Mesa 官方说明](https://docs.mesa3d.org/drivers/d3d12.html)。

## 检查结果

- Windows：74 项离线测试中 73 项通过，1 项因未配置独立 Windows Bash 测试工具而按条件跳过。
- Ubuntu：74 项离线测试中 72 项通过，2 项仅适用于 Windows，按平台条件跳过。
- 原生 `ign sdf -k` 返回 `Valid.`。
- 从 Windows 主入口执行 `-Check` 成功，14 个封存文件、源包及安装资源、ROS 依赖和 Fortress/Ogre 库检查通过。
- 观察桥接契约仍为 9 条 Gazebo→ROS 单向接口；ROS 域 73、本机通信设置和默认暂停配置保持有效。
- 历史输出、地图、知识库和传感器来源中的 12,127 个文件，与“原包＋增量”的期望哈希一致。

## 当前边界

本次没有运行 Gazebo、ROS 观察节点、底盘、导航或运动测试。台式机上的 GUI、传感器实际出帧、动态驾驶和动态建图仍待后续验收。笔记本此前的静态结果属于原环境历史证据，不能代替台式机运行结论。

实车运动仍须用户明确授权，小车共用工作区只读。仿真 IMU 维持 50 Hz；源建图 YAML 的 100 Hz 注释仍未按实测对齐。地图候选没有自动接入当前测试场景。

WSL 当前提示 Windows 的 localhost 代理未映射到 NAT 环境。本轮离线构建和检查已完成；若后续需要 Linux 联网下载依赖，再按实际网络情况处理。

## 证据与备份

- `d_drive_adaptation.json`：目标路径、修改前后 SHA256、保留的模型源码与场景语义检查。
- `before_d_drive_adaptation/`：修改前的入口、环境、检查器、生成器、场景与清单原件。
- `wsl-install.log`、`wsl-verification.json`：WSL 安装成功及版本检查。
- `ubuntu-disk-before-registration.json`、`ubuntu-registration.json`：原磁盘校验与注册结果。
- `linux-environment.json`：恢复后的软件、用户和工作区盘点。
- `native-model-preparation.json`、`native-build.stdout.log`、`colcon_logs/`：原生源码校验与构建记录。
- `entry-readonly-final.json`、`sdf-check.stdout.log`：最终入口与 SDF 检查。
- `windows-offline-tests-final.*.log`、`linux-offline-tests-final.*.log`：最终两端测试结果。
- `graphics-query.stdout.log`、`linux-graphics-profile.json`、`linux-dotfiles/`：图形查询与原 shell 配置备份。
- `historical-preservation-verification.json`：历史资料保留复核。

今后在台式机执行入口的只读检查：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'D:\rob-memory\sim\tools\start_hunter_full_scene.ps1' -Check
```

原始迁移 ZIP、原增量包以及历史验证日志保留原样。当前 Codex 聊天数据库没有被迁移包覆盖。
