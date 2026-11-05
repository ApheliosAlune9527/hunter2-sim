# 个人模型参考包

这两份 CMakeLists.txt 和 package.xml 是个人创建的数据安装封装，用于在 WSL 的个人 hz_sim_ws 中注册模型资源。包名保留 hunter_description 和 realsense2_description，以兼容原始 Xacro 中的包路径；版本和维护者字段沿用导出资料，用于来源追溯，不表示这个封装由上游维护者发布。

模型数据来源为 `F:\rob-memory\robot_assets\hunter_from_car_20261013_qjkgbbq5` 的对应 `urdf`、`meshes` 目录，原样复制至 `/home/aphelios/hz_sim_ws/src` 后逐文件校验 SHA256。Windows 原始参考资料保持只读；复制记录见 `F:\rob-memory\outputs\hunter_sim_execution_20261012\references\wsl_model_reference_import_20261013.json`。

车端导出的 RealSense 目录是安装共享目录，含 package.xml 和生成的安装脚本，但没有源码 CMakeLists.txt。此处另写仅安装 urdf/meshes 的封装，不复制这些安装脚本，也不引入相机驱动和消息代码。Hunter 参考包同样只含模型数据，不复制启动文件、底盘源码、导航包或旧地图。

初次准备仅写入不存在的个人包目录，已存在的同名包需要另行核对，不能覆盖。构建仅安装资源并注册包索引；Xacro 展开仅生成 XML 文件，二者均不启动 ROS 节点或机器人程序。

当前导出的车体模型主要为固定连接的外形和传感器安装坐标参考。此导入不等于已完成运动仿真：车轮/转向关节、惯性、简化碰撞体、控制器与虚拟传感器仍待建立和验证。具体实车型号与物理参数仍须实测核对。
