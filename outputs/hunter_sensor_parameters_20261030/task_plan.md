# 复用现有建图外参实现计划

执行方式：在当前会话按顺序实施；使用测试驱动开发和完成前验证。用户已授权复用小车已有配置用于个人仿真；本目录不是 Git 仓库，变更前保存文件副本与 SHA256，不创建 Git 仓库。实车只读，所有测试在个人 WSL 中使用独立通信分区和静止模型。

目标：将已逐文件核对的 FAST-LIVO2 外参与 CH104 数据帧语义接入完整 CAD 仿真，保证 URDF、SDF、ROS TF、传感器实际数据相互一致。

设计：继续以既有名义 `hesai_lidar` 安装帧为锚点。源参数满足 `p_I = R_IL p_L + t_IL`、`p_C = R_CL p_L + t_CL`；URDF 中 IMU 和相机光学帧相对雷达的位姿使用这些变换的逆。光学数据帧采用现有建图配置。静态实测发现新光心被旧名义相机外壳自身遮挡后，将外壳及其安装框平移约 15 mm，使其保持原来的光心相对关系；外壳网格本身不变，此调整并非实车测量。`imu_link` 改为 CH104 建图数据帧。保留 19 个链接、6 个活动关节、12 个外观网格及既有命名空间。

技术：Python 标准库、URDF/SDF、个人 WSL Ubuntu 22.04、ROS Humble、Gazebo Fortress/Ogre1。相机继续使用已验证的居中方形像素近似；深度共用该近似。零偏、噪声、时间延迟和物理标定精度不由这些配置推断。

## 1. 来源与回滚边界

- [x] 比对 `vio.cpp`、`LIVMapper.cpp`、`ch104_imu_pub_legacy.py` 的车端和 Windows SHA256。
- [x] 核对 CH104 默认 frame_id、XYZ 顺序及 g→m/s²、deg/s→rad/s 单位换算。
- [x] 备份将修改的 `sim/tools/` 文件、生成的包文本资源、URDF、转换输入和场景/封存文件。
- [x] 创建 `sim/tools/hunter_sensor_profile.py`，固定四份配置/源码文件的路径与哈希，仅将它们作为读取的证据，不导入或运行导出的设备脚本。

## 2. 坐标与生成器

- [x] 先为新关系写失败测试：由 URDF 反算 `T_I_L`、`T_C_L`，应分别得到原 YAML 数值；IMU 为 `(0.539,-0.110,0.463)` m、相机光心为 `(0.644,0.015,0.475)` m。
- [x] `hunter_sensor_profile.py` 提供 `relative_poses()`、`validate_sources(root)`、`profile_report(root)`；使用 `t_inv=-R.T*t`。来源变化必须拒绝。
- [x] 修改 `build_hunter_full_description.py`：IMU 与相机光学帧固定到雷达；记录相机外壳的名义位置调整；来源和限制写入 geometry_report、source_manifest、包 README。
- [x] 修改 `check_hunter_full_scene.py`：校验新来源、独立反算参数关系；相机引擎 +X 与光学 +Z 的旋转由矩阵换算。
- [x] 修改 `build_hunter_full_scene.py` 的参数来源说明以及入口固定文件列表；无速度/反向桥接变化。

## 3. 安装、场景与离线验证

- [x] 构建生成器并运行几何/关系测试，再在个人 WSL 同步数据包并 `colcon build --packages-select hz_hunter_full_description`。
- [x] 仅在转换副本中删除 preserveFixedJoint 标签，运行 `ign sdf -p` 生成转换数据，再生成正式场景。
- [x] 更新入口封存，运行模型、场景、观察接口、入口测试与真实入口 `-Check`；验证完整场景 SDF 有效。

## 4. 静态运行验证与交付

- [x] 在独立 Gazebo 分区、ROS 域 74、仅本机通信中运行所有模型均为 static 的完整夹具，删除机器人控制插件，不发送速度或世界控制。
- [x] 验证非空雷达、RGB、深度、IMU、CameraInfo 与 scan；ROS TF 的平移和旋转应与参数换算一致，CameraInfo 应与实际投影一致。
- [x] 用一个有水平分量的测试重力向量验证 IMU 旋转后的数据轴；该向量只存在于独立静态夹具。
- [x] 核对只结束本轮创建的子进程，保存验证报告、来源记录、剩余近似与用户下一次启动方式。

验收重点：外参复用的含义是与收到的建图配置一致，不声称其物理测量精度已经得到验证；详细网格外观和车轮关节保持可用，启动仍默认暂停，实车未被控制。
