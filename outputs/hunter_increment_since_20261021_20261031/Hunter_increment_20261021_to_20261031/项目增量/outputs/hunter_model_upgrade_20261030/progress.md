# 模型升级进度

## 2026-10-30

- 用户确认范围：实车外观、独立车轮转向和传感器；不在本阶段做实测悬挂、轮胎、电机标定。
- 完成原模型和厂家分件的只读来源/几何分析；核对两个分支和固定提交，未执行任何下载的启动程序。
- 建立独立升级计划。接下来通过子代理处理模型资源和几何检查，主代理负责当前环境、Fortress与传感器兼容验证。所有代理都禁止执行运动、实车程序或修改共用工作区。
- 几何描述包已生成，来源SHA和离线重建一致，10项静态测试通过；独立规格审查进行中。
- 已实查个人WSL、Humble、Fortress及NVIDIA图形能力。新建固定传感器兼容夹具，所有模型static，无车轮/控制插件/速度发布；Ogre2失败后定位为当前渲染能力限制，Ogre通过五类传感器连续消息验证，测试进程均仅关闭自身。
- 完整模型场景、ROS传感器接口和主入口尚待集成；未运行运动测试或任何实车驱动。整体未完成。
- 任务1两阶段独立审查均PASS；实际ament构建及固定关节折叠转换为7物理links/6活动joints的SDF检查通过，记录references/ament/check.json。
- 显式传感器帧ID已在固定夹具验证，扫描/点云、RGB/深度、IMU分别给出hesai_lidar、camera_optical_frame、imu_link正确前缀；记录references/sensor_probe/ca48a86a9c3c/check.json。
- 新完整场景正在生成。另完成单向传感器/状态ROS接口及2D scan高度坐标转换；5项接口mutation检查由缺模块红灯转绿，禁止速度或反向桥接。完整模型的运行验证尚未执行。
- 完整场景实际静态传感器链已PASS：references/full_sensors/84f73c45b8fb/check.json；采样包含原生及ROS点云/RGB/深度/CameraInfo/IMU/2Dscan及固定TF。所有物体static且控制插件移除，未发布速度，创建的进程全部关闭。
- 正式动态结构场景只做暂停GUI验证，两次均paused=true、sim_time=0且无速度发布；近景新版为references/full_preview/e431bbcda444，已查看并向用户展示截图。当前模型采用厂家分体CAD+本车上装，不声称照片涂装和外壳一比一复刻。
- 场景25项离线测试与ROS接口5项检查通过，正在独立规格审查；新主入口仍待接入，不提前宣称交付完成。
- 任务2规格及质量均PASS。任务3原始20项离线测试PASS，新/旧logged PowerShell检查真实PASS；正常入口实际GUI与3个观察节点/9桥/静态TF存在，native与ROS均无命令publisher，sim_time=0；根只结束自己启动的entry，session两组均closed，证据references/entry_runtime/5d2bae6f8fb3和user_logs/20261030T071813Z_376e3ce0ddc2。
- 任务3规格审查发现日志写入失败会跳过清理的异常分支，已由实现者用纯mock复现红灯，正在修复、重封存；不把正常路径通过当作此异常分支已经通过。随后继续原规格复审、最终质量审查及新版正常入口运行验证。
- 日志失败分支已先红后绿修复；根复跑24项入口检查PASS，规格复审PASS，最终质量与整体衔接审查PASS。最终入口清单SHA=dd4eec6f9e9d3299ab7c40fba3c46e9b77d58d7e2a412d5da40ff11418052840。
- 新版实际PowerShell -Check exit0，正常入口暂停GUI与ROS观察图、无速度publisher、时间0均PASS，证据references/entry_runtime/ecba75156563。根验证脚本主动SIGINT自己创建的入口后，user_logs/20261030T072354Z_210c628c6f53/session.json显示两个created groups均closed、无遗留；exit130来自根诊断收尾，不是用户按键。
- 已完成本轮选定范围，主入口与旧logged别名均指向完整模型。旧简化world/直接Bash/运动工具保留历史；不执行本轮运动测试，物理标定/照片涂装细节/雷达GNSS专用输出等限制写明。
