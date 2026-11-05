# 实车导出的机器人参考资料

2026-10-13 已接收并核验两个车端导出的压缩包。资料来自 `car-NUC15JNKU7X4` 的导航工作区源码与相机描述安装目录；知识库仅作历史参考。

本次离线解包目录：[hunter_from_car_20261013_qjkgbbq5](hunter_from_car_20261013_qjkgbbq5/)。共 184 个文件，原压缩包保留在执行记录的 `references/archives` 中。

| 目录 | 当前用途 |
| --- | --- |
| [hunter_description](hunter_from_car_20261013_qjkgbbq5/hunter_description/) | 车体与传感器外形、安装坐标参考；还需为仿真补齐车轮、转向关节和物理参数。 |
| [hunter_base](hunter_from_car_20261013_qjkgbbq5/hunter_base/) | 只读查阅控制接口、里程计和尺寸参考值。初始化连接 CAN 后会进入控制模式并释放刹车，不能直接作为安全仿真程序运行。 |
| [hunter_nav_odom](hunter_from_car_20261013_qjkgbbq5/hunter_nav_odom/) | 导航参数和行为树参考；其中共享旧地图仅作历史资料，后续地图采用个人新建图导出。 |
| [realsense2_description](hunter_from_car_20261013_qjkgbbq5/realsense2_description/) | 补齐模型引用的相机描述与外形文件；不等于已配置仿真相机或真实相机驱动。 |

当前个人地图基线候选为 `lab_20261011_155236_369289`，原始地图归档已与车端及历史导出记录核对一致。二维候选地图见 [lab_map.yaml](../maps/lab_20261011/lab_20261011_155236_369289/merged/ros2_nav2/lab_map.yaml) 和 [lab_map.png](../maps/lab_20261011/lab_20261011_155236_369289/merged/ros2_nav2/lab_map.png)；转换过程、实际布局、定位和导航效果仍待验证。

核验记录：[压缩包校验](../outputs/hunter_sim_execution_20261012/references/asset_transfer_manifest_20261012.json)、[离线解包](../outputs/hunter_sim_execution_20261012/references/asset_extraction_receipt_20261013.json)、[主模型直接文件引用](../outputs/hunter_sim_execution_20261012/references/model_reference_check_20261013.json)、[个人地图归档一致性](../outputs/hunter_sim_execution_20261012/references/map_archive_verification_20261013.json)。

用户明确限制：共用小车工作区只读；没有用户明确下令小车移动，禁止提供或执行可能导致实车移动的命令。涉及移动，必须先明确提醒并等待授权。这里的源码和启动文件仅作为参考，后续个人仿真工程需要独立入口并与实车控制通道隔离。
