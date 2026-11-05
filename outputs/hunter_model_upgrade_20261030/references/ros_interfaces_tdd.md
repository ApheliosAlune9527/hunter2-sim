# ROS观察接口红绿记录

2026-10-30 根代理为单向桥接拒绝路径先建立 `test_full_ros_interfaces.py`。
首次运行 `python -B -m unittest discover -s sim/tools -p test_full_ros_interfaces.py -v`：
`setUpClass ERROR`，原因是尚未实现的 `check_full_ros_interfaces.py` 不存在，退出码1。

随后实现固定9个GZ_TO_ROS接口、输入契约、scan参数和launch文件，同一命令运行5项检查均OK，退出码0。
检查覆盖正常接口完整性、添加速度桥、双向桥、缺项、普通TF话题和错误消息类型，以及ground参考高度带到rear-axle frame的转换。

实际ROS消息和TF不以这些离线检查代替：见 `full_sensors/84f73c45b8fb/check.json`。
该独立固定模型夹具收到点云、RGB/深度、内参、IMU、转换后的二维扫描和连续时钟，检查传感器帧及安装变换通过。
运行中无速度发布，机器人控制插件移除，所有模型static。
