# 模型升级发现

- 用户拒绝继续以简化方块作为当前主仿真模型，并选择真实外观、独立车轮转向和传感器范围。
- 原 `hunter_2_0.STL` 为9452三角面、4728唯一顶点，一个顶点连通组件；单位毫米，包围盒980×745×370mm。不能用连通分量直接提取四个轮子。
- 厂家 `agilexrobotics/ugv_gazebo_sim` 的humble分支固定提交9d7888affce35321c657c1c8528307f3115b9d41提供底盘和轮子等9份STL，原始骨架8关节。模型原启动接口使用Gazebo Classic插件libgazebo_ros_ackermann_drive.so，不能直接用于Fortress。
- 厂家完整原始URDF零姿态几何整体约0.979809×0.745566×0.376644m；原点与个人后轴轮心原点不同，需要烘焙网格变换而非直接换URI。上游左右轮轴方向、0转角限位、零质量等不能盲用。
- 上游front_steer_left/right网格包含轮子几何，其中左侧还含其他连杆范围；不能同时将它们与完整前轮网格重复加载。先使用清晰的底盘和四轮几何，对转向连接件单独去重核对。
- 上游全部CAD质量相加约52.22747kg，不能作为实车带上装总质量。厂家当前底盘标称65–72kg，本阶段允许可追溯的工程假设，尚不标定轮胎/电机/悬挂实测响应。
- 原导出RViz描述的规范化哈希、8个网格及雷达TF已于outputs/hunter_model_update_20261030核对。上装与传感器继续复用该来源，机械臂不在本次选定范围。
- 初始WSL Ubuntu-22.04为Stopped；随后仅为个人仿真环境检查和固定传感器夹具启动。当前源目录不是Git仓库。
- 当前实际主机仍为Dell G15 5511，RTX3050 Laptop 4GB、约15.7GiB内存；不能把迁移记录中的未来台式机当作当前硬件。WSL为Ubuntu22.04.5，Humble，Fortress6.18.0/sensors6.9.0/rendering6.6.4，GLX使用D3D12 NVIDIA加速、OpenGL4.2；详情见references/environment.json。
- 全部物体static的独立传感器夹具中，ogre2触发GL3PlusTextureGpu::copyTo未实现异常并退出（references/sensor_probe/4215d88142d9）；同样夹具使用ogre成功收到扫描、360×4点云、RGB、深度、IMU连续数据（references/sensor_probe/b3a0885eb48d）。完整模型传感器与GUI采用ogre，未修改全局驱动或Mesa。
- 几何实现产出19links、6活动关节、完整来源清单；10项离线测试转绿，正在独立规格审查。仅代表离线模型结构，不能当作Gazebo或驾驶验收。
- 几何规格和质量独立审查随后均PASS；ament安装和固定关节折叠的SDF实际校验PASS。完整场景7物理links/6活动joints，保留12个独立网格视觉。
- 完整CAD静态夹具（所有模型static，机器人Ackermann与JointState插件均移除）实际采样通过：references/full_sensors/84f73c45b8fb。原生传感器及单向ROS数据链、固定TF、点云转2D扫描均有连续非空数据；720×32点云含10683有限点，640×480深度图含162615有效距离，2D扫描87个有限距离，IMU静止重力9.81。已查看RGB和深度PNG。此结果不包含轮子动态、里程计或驾驶性能。
- 外观对照图references/geometry/body_shell_comparison.png显示：旧本车单体STL自身为简化封闭车壳和近球形轮胎；厂家分体CAD有更完整机械/轮胎细节。当前采用厂家分体CAD并复用本车上装，不把它声称为照片一比一外观；侧覆盖件/轮盖/涂装仍有表达差异，未修改稳定模型。
- 入口集成核对发现ament `--symlink-install`正常把share/urdf、mesh和source_manifest链接到/home/aphelios/hz_sim_ws/src/hz_hunter_full_description下同相对路径。根代理实际readlink确认三类资源。原入口校验器“解析后必须仍在share内”的假设会误拒绝合法安装；正在只对固定个人source root的同相对路径增加兼容回归，入口封存清单的越界拒绝保持严格，所有资源仍须逐文件SHA匹配。另CMakeLists仅为构建文件，不要求安装到share，其源哈希仍必查。
