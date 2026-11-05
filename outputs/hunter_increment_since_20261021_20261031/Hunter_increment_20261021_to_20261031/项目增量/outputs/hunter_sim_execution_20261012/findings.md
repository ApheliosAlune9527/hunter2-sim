# 执行核对记录

## 2026-10-12：实车主机环境
证据来源：用户在小车终端执行 hostnamectl 和读取 ROS_DISTRO 后回传的输出；未由本机直接连接或查询小车。

| 项目 | 已确认值 |
|---|---|
| 登录用户 | car |
| 主机名 | car-NUC15JNKU7X4 |
| 硬件型号 | ASUSTeK COMPUTER INC. / NUC15JNKU7X4 |
| 操作系统 | Ubuntu 22.04.5 LTS |
| 内核 | Linux 6.8.0-138-generic |
| 架构 | x86-64 |
| 当前终端 ROS_DISTRO | humble |
| 提示符中的当前目录 | /home/car/桌面 |

ROS_DISTRO 只说明当前终端加载的发行版；尚未检查已安装的软件、运行中的节点或导航功能。此处硬件为小车主机，与先前查询的 Windows 笔记本分别记录。

## 尚未确认
- 当前是否有他人在使用小车。
- Hunter 铭牌型号、描述模型、几何参数及底盘控制接口。
- 各工作区实际位置、传感器配置、已有导航配置和运行质量。
- 不将已有启动清单、文件存在或环境变量视为导航效果验证。

## 2026-10-12：已有目录与文件
证据来源：用户回传 /home/car 和 /home/car/桌面 的 ls -la 输出，附件为已粘贴的文本.txt。

- 已确认目录存在：/home/car/hunter2.0_ws、/home/car/hunter_nav_odom_ws、/home/car/robot_bringup_ws、/home/car/nav2_ws、/home/car/hz_ws。
- 用户再次明确：/home/car/hz_ws 是此前为自己建立的个人 FAST-LIVO2 建图工作区。此工作区作为个人建图资产来源；其他工作区仅用于只读核对底盘、模型与导航资料。电脑端仿真工程在个人独立目录建立。
- 相关传感器和建图候选目录也存在：ch104_ws、d435i_ws、hesai_xt32_ws、fastlivo2_ws、fastlivo2_maps，以及若干 XT32 工作区。
- 已确认文件存在：/home/car/start_hunter_fixed.sh、/home/car/start_hunter_nav_stack.sh；尚未读取内容，也未运行这些脚本。
- 桌面有历次 frames 文件和部分其他资料；它们不能证明当前坐标关系或导航已验证。
- hunter2.0_ws 仅是目录名称，不能据此认定实车铭牌型号；上述工作区的源码、使用关系和运行质量仍待检查。

## 2026-10-12：源码包与底盘启动脚本
证据来源：用户回传三个 src 目录列表以及 start_hunter_fixed.sh 的文本。

- /home/car/hunter2.0_ws/src 包含 hunter_description、hunter_ros2、ugv_sdk。
- /home/car/hunter_nav_odom_ws/src 包含 hunter_base、hunter_description、hunter_nav_odom、robot_bringup。
- /home/car/robot_bringup_ws/src 包含另一份 robot_bringup。
- 存在重复命名的模型与启动包，须核对文件内容及使用关系，不直接假定各副本相同或当前已加载。
- start_hunter_fixed.sh 涉及重启 hunter-can.service、检查 can0 回传，并启动 robot_bringup 的 hunter.launch.py。此脚本不能作为只读查询执行；当前只读取文字。
- 脚本文本按顺序引用 /opt/ros/humble、hunter2.0_ws/install、hunter_nav_odom_ws/install，并配置 rmw_cyclonedds_cpp 和 ROS_DOMAIN_ID=88。这些是该脚本的配置，未证明当前终端或运行系统使用它们。
- 脚本提示语中的 Hunter 2.0 不是铭牌型号证据；URDF/Xacro 内容、底盘参数、控制消息和导航能力仍待核实。

## 2026-10-12：底盘启动配置与查询工具
- 当前小车终端找不到 rg 命令；未安装任何工具。后续文件查询改用系统自带 find，文本查询可用 grep，已知文件仍用 sed 只读查看。
- 已读 /home/car/hunter_nav_odom_ws/src/robot_bringup/launch/hunter.launch.py 的源码文本。
- 该文件包含 hunter_base 包中的 launch/hunter_base.launch.py，配置 port_name=can0、robot_model=hunter2、odom_frame=odom、base_frame=base_link、odom_topic_name=odom。
- publish_odom_tf 启动参数默认 true，传给底盘启动文件；尚未验证运行中的坐标发布关系或是否有重复发布。
- 此处为静态源码配置，不是实车铭牌、当前运行状态或控制接口的完整确认。控制话题、消息类型、单位、底盘约束与模型内容仍待读取。

## 2026-10-12：模型文件位置与底盘节点配置
- find 查询已成功，导航工作区的 hunter_description/urdf 中找到 assembly.urdf.xacro、hunter.urdf.xacro、common_properties.xacro，另有 package.xml 与 launch/display.launch.py；模型文件内容尚未读取。
- robot_bringup/launch 中找到 hunter、xt32、ch104、d435i、ars548 的启动文件；文件存在不能证明这些设备当前运行或为一期必需传感器。
- 已读 /home/car/hunter_nav_odom_ws/src/hunter_base/launch/hunter_base.launch.py：创建 hunter_base 包的 hunter_base_node 节点。
- 该文件默认 use_sim_time=false、simulated_robot=false、robot_model=hunter2、port_name=can0、control_rate=50、publish_odom_tf=true，默认里程计话题 odom、坐标 odom/base_link。
- 参数名称和默认值属于静态配置。simulated_robot 的实际分支逻辑、control_rate 的使用方式、控制话题与消息语义尚未查代码；不能据该参数推定完整的物理或传感器仿真已存在。

## 2026-10-12：主模型与控制代码索引
证据来源：用户附件中的 hunter.urdf.xacro 文本及 grep 的源码行索引。

- hunter.urdf.xacro 引用 common_properties.xacro 与 assembly.urdf.xacro；主文件展示 base_link 到 hunter_link 的固定连接，以及 hunter_2_0.STL 的外观与碰撞网格，网格缩放为 0.001。
- 主模型还有 PiPER_plate.STL 与 PIPER.STL 外形，通过固定关节连接；这只是模型引用，未确认实车是否装有机械臂，也不是机械臂关节仿真的证据。
- 主文件中未见车轮转动、转向关节及惯性定义，assembly 与 common_properties 的内容仍待读取；不能据主文件断言整个引用模型的完整结构。
- hunter_messenger.hpp 第 94～95 行的索引显示创建 geometry_msgs::msg::Twist 订阅，话题为 /cmd_vel。这是该源码的接口定义，未验证当前运行节点或其他包副本。
- 同文件第 233 行出现 SetMotionCommand(msg->linear.x, phi_i)，第 346～363 行存在 linear.x/angular.z 的处理；完整回调与转换函数尚未读，暂不锁定角速度到转向角的语义、限幅或单位。
- 已定位 simulated_robot 和 sim_control_rate 的相关实现，但仅有匹配行；模拟模式是否提供动力学、传感器或仅里程计仍待完整函数核对。

## 2026-10-12：装配模型与完整控制回调
- 已读 assembly.urdf.xacro：装配支架、ARS548、GNSS、XT32 通过固定关节连接，D435i 使用 realsense2_description 的 _d435i.urdf.xacro 宏。描述中列出的部件不能直接当作实车当前装配证据。
- XT32 在 assembly_link 下的文件位置为 0 0 0.32，绕 Z 轴旋转 M_PI/2；D435i 的文件位置为 0.10805 0 0.2635。这些是模型中的相对变换，不是已校准的实车外参。
- 已读主模型及装配模型中的 Hunter 部件均采用固定连接，未见独立的车轮转动与转向关节；common_properties 和外部相机模型仍待检查。现有资产可作为外形与安装位置参考，运动和传感器仿真尚未建立。
- 已读 hunter_messenger.hpp：/cmd_vel 的 Twist 回调在 simulated_robot=false 时调用底盘 SDK；linear.x 作为线速度传入，angular.z 与 linear.x 用于计算转弯半径，再换算内侧车轮转角 phi_i。
- 转向计算包含 angular.z=0 时返回零转角、较小半径时返回 max_steer_angle、以及倒车时的符号处理。尺寸 l/w、限值与小半径倒车分支仍需结合参数及调用代码核对，不作运动测试或导航质量结论。
- 在 simulated_robot=true 分支中，回调仅把消息存入 current_twist_；此头文件未见读取该输入推进仿真的过程。PublishStateToROS 仍从 hunter_->GetRobotState() 取数据；初始化与其他源文件尚待核查，不能把此开关视为完整仿真。
- 里程计使用 BicycleKinematics 数值积分；实际轴距、轮距及该积分模型的参数一致性仍待读取 hunter_params.hpp、bicycle_model.hpp 与 hunter_base_ros.cpp。

## 2026-10-12：初始化、尺寸与模拟入口结论
证据来源：用户回传 hunter_base_ros.cpp、hunter_params.hpp、bicycle_model.hpp、common_properties.xacro 的完整片段。

- Initialize 创建 AGX_V2 协议的 HunterRobot。Run 对 hunter2 使用 HunterV2Params；这是代码配置及实现，实车铭牌仍未核实。
- HunterV2Params 代码值：轴距 0.650 m、轮距 0.605 m、轮半径 0.165 m；max_steer_angle=0.58 rad、max_steer_angle_central=0.461 rad、max_linear_speed=1.5 m/s。均为源码参数，未实测；回调未直接使用速度上限，亦不能据常量声明保证完整限幅。
- BicycleKinematics 的声明将 L 固定为 HunterV2Params::wheelbase，并注释自行车运动学方程；operator() 的源文件实现尚未读取。
- common_properties.xacro 仅定义颜色。已读的三份 Hunter Xacro 没有独立的车轮转动/转向关节、车体惯性或 Gazebo 运动/传感器仿真配置；现有描述主要可复用外形、碰撞网格与安装坐标，不能直接当作完整运动仿真底座。
- 关键：Run 设置模拟标志之后，无条件进入 CAN 端口连接流程；连接成功即调用 EnableCommandedMode 和 ReleaseBrake，未因 simulated_robot=true 而绕开。不得在本轮启动此程序或据模拟标志推断已与实车隔离。
- 主循环固定 rclcpp::Rate(50)，每次调用 PublishStateToROS 并处理回调；已读流程未以暂存的 current_twist_ 推进交互仿真。现有模拟开关不是完整离线仿真入口，电脑端应另建独立入口与控制通道。
- 转向计算的小半径倒车符号、连续限幅、零时间间隔积分等边界留作未来个人工程的静态审查项；未做车端修复或运行验证。

## 2026-10-12：导航文件与分段启动入口
- hunter_nav_odom 包中已找到多组 lab_odom 地图的 YAML/PGM：01、04、05、06，以及 01_2026_9_13。尚未确认脚本指定哪一版，不按文件名推定当前使用或地图质量。
- config 中有 nav2_params.yaml、nav2_params_stock.yaml、mapper_params_online_sync.yaml、self_return_filter.yaml，以及 navigate_no_spin.xml 和 navigate_through_poses_no_spin.xml。参数和行为树内容尚未读取；no_spin 文件名不能证明实际导航已经禁用原地旋转或符合转向约束。
- launch 中找到 base_sensors.launch.py；导航依赖和实际参数选择尚待读取。
- 已读 start_hunter_nav_stack.sh：重启 CAN 后分段引用 robot_startup 下的 01_hunter.inc、02_xt32.inc、03_model_tf.inc、04_scan.inc、05_nav2.inc、06_rviz.inc、07_x4air.inc、08_camera_lidar_tf.inc。
- 这份一键脚本包含硬件通信重启和多项程序启动，仅作为文字参考，未运行。具体底盘包来源、点云转二维激光配置、地图和 Nav2 参数路径仍需读取各分段文件。
- 脚本中列出的 X4 Air 与先前用户个人 FAST-LIVO2 的 D435i 资料分别记录；当前硬件装配和各算法实际传感器来源仍未核实。

## 2026-10-12：Nav2 指定地图与候选基线参数
- 已读 robot_startup/01_hunter.inc 与 05_nav2.inc：两者先调用 use_robot，再加载 Humble 与 hunter_nav_odom_ws/install，设 Cyclone DDS 和 ROS_DOMAIN_ID=88。use_robot 的具体定义尚待读取，包副本和最终环境来源仍未完全确认。
- 05_nav2.inc 指定 maps/lab_odom_01.yaml 和 config/nav2_params.yaml，传 use_sim_time=false、autostart=true。该分段文件仅显示文字，未执行。
- 已读该 nav2_params.yaml：全局规划插件 SmacPlannerHybrid，搜索模式 REEDS_SHEPP、minimum_turning_radius=1.6；路径跟踪插件 RegulatedPurePursuitController，desired_linear_vel=0.25、use_rotate_to_heading=false、allow_reversing=true。均为文件设置，未验证实际导航效果。
- AMCL 配置使用 DifferentialMotionModel，输入 scan，坐标 map/odom/base_link；运动噪声模型适配性须结合实测定位表现，不据名称判定配置错误。
- 局部和全局代价地图都使用 /scan，分辨率 0.05 m；footprint 顶点为 [0.52, ±0.395] 与 [-0.50, ±0.395]，描述范围约长 1.02 m、宽 0.79 m，尚未与实车测量对齐。
- 参数指向两份 no_spin 行为树；behavior_plugins 列表不含 spin，控制器关闭 rotate_to_heading。行为树 XML 尚未读取，不据文件名断言所有路径都没有旋转动作。
- YAML 的多项 use_sim_time=true 与启动传参 false 同时存在，最终值是否被启动文件重写尚待核对，不能直接认定为时钟故障。
- FollowPath 下保留 DWB 注释、critics 等字段；实际 RPP 版本是否使用这些字段须按插件声明核对。未修改原配置，未将静态字段混杂视为已发生的运行故障。
- 地图 YAML 元数据、点云转 scan、模型与 TF 的来源尚待读取。

## 2026-10-12：环境别名与导航雷达链路
- type use_robot 显示它是别名，文本依次加载 Humble、hunter2.0_ws、d435i_ws、hesai_xt32_ws、ars548_ws、robot_bringup_ws 的安装环境，并设置 ROS_DOMAIN_ID=88 和 Cyclone DDS。此次仅显示别名，不调用它；不能把别名文本当作当前环境已按该顺序加载的证据。
- 02_xt32.inc 在该别名之后引用 xt32_direct_ros2_ws/install，指定 xt32_direct_driver 的 xt32_direct_node。导航雷达启动入口与个人 FAST-LIVO2 资料分别记录，当前实际运行状态未查。
- 03_model_tf.inc 引用 hunter_nav_odom_ws/install，并指定 hunter_description 的 display.launch.py。该启动文件内容尚待读取，以确认模型入口和坐标发布配置。
- 04_scan.inc 指定 pointcloud_to_laserscan_node：cloud_in=/lidar_points_direct，scan=/scan，target_frame=base_link，transform_tolerance=0.1。
- 该点云转换文件设置 min_height=0.10、max_height=0.85、angle_min=-3.14159、angle_max=3.14159、angle_increment=0.00872665（约 0.5°）、scan_time=0.10、range_min=0.50、range_max=20.0、use_inf=true。均为配置值，scan_time 不等于已测实际发布频率。
- 已找到 Nav2 的二维激光输入配置链路；原始点云实际 frame_id、TF 对齐、测量频率、遮挡和自车回波仍待核查，未订阅或回放数据。

## 2026-10-12：模型入口、地图元数据与行为树内容
- display.launch.py 使用 hunter.urdf.xacro 生成 robot_description，启动 robot_state_publisher（名为 hunter_robot_state_publisher）与 RViz。已读入口没有 Gazebo、车轮控制器或虚拟传感器，不是完整仿真启动文件；未运行。
- lab_odom_01.yaml 指向同目录 lab_odom_01.pgm，模式 trinary，分辨率 0.05 m/格，地图原点 [-5.59, -9.29, 0]，occupied_thresh=0.65、free_thresh=0.25。图像尺寸、实际空间对应和地图质量尚未核对。
- 已读两份 no_spin XML：没有 Spin 行为节点；分别用 ComputePathToPose、ComputePathThroughPoses，经 FollowPath 执行，并在恢复分支清除代价地图、等待 5 s 或 BackUp。
- 两份行为树都有 BackUp，参数 backup_dist=0.30、backup_speed=0.05；此为会涉及倒车的恢复动作，不因文件名 no_spin 而变成无运动流程。未来导航/恢复测试须遵守用户明确的移动授权约束，本轮仅显示文件文字。
- 单目标树的 RateController 为 1 Hz，多目标树为 0.333 Hz；这些是文件值，不是已测重规划频率或运行表现。
- 底盘、描述模型、导航接口与主要文件引用已形成静态资产记录；安装包路径、时间参数覆盖、个人 hz_ws 配置、实际传感器坐标和铭牌仍待确认。

## 2026-10-12：Nav2 共享目录与个人工作区文件
- 当前终端 ros2 pkg prefix --share nav2_bringup 返回 /opt/ros/humble/share/nav2_bringup。该命令只查本地包索引，未启动节点；此路径是当前终端结果，不据此断言所有启动环境都没有其他同名包。
- 个人 /home/car/hz_ws/src 中找到 FAST-LIVO2、HesaiLidar_ROS_2.0、livox_ros_driver2 和 rpg_vikit 的包与相关文件。
- FAST-LIVO2 有 xt32_mapping.launch.py、xt32_mapping_nav.launch.py、config/xt32.yaml、config/xt32_nav.yaml，另有其他机型配置和 xt32（复件）.yaml。当前实际使用哪一变体仍需结合个人启动入口核对，不按文件名选复件或其他机型。
- HesaiLidar_ROS_2.0 下有 config/config.yaml、launch/start.py；rpg_vikit 包含 vikit_common 和 vikit_ros。
- src 中存在 FAST-LIVO2/src/install 的生成文件，后续资产整理优先源码、配置、模型和地图，不把生成文件的存在视为当前编译/运行验证。
- Windows 已有个人 hz_ws 备份可复用；后续如采用备份需核对相关版本/文件一致性，不把它当成整个机器人系统的备份。

## 2026-10-12：时间参数重写与个人建图输入
- 已读 /opt/ros/humble/share/nav2_bringup/launch 的 bringup、localization 文件及 navigation 文件前 220 行。三者通过 RewrittenYaml 把传入的 use_sim_time 写到启动使用的参数中，父入口把该值传给定位和导航子入口。按 05_nav2.inc 的 false 传参，这个静态启动路径会覆盖 YAML 中的 True；不需要仅依据文本差异修改原参数文件。当前运行节点的实际值未查询。
- 已读 navigation 的非组合启动分支，控制器 cmd_vel 重映射到 cmd_vel_nav，velocity_smoother 将 cmd_vel_nav 输出到 cmd_vel。组合分支只读到前半部分，实际运行模式与控制来源仍未验证。
- 个人 xt32_mapping.launch.py 属于 fast_livo 包，默认加载 xt32.yaml 与 camera_pinhole.yaml，创建 fastlivo_mapping（laserMapping）；另含 /left_camera/image 的压缩图像转发节点。此处只是源码引用，未运行。
- xt32.yaml 文件输入是 /camera/camera/color/image_raw、/lidar_points、/imu/data，图像和雷达开启。与已有 Nav2 的 /lidar_points_direct -> /scan 输入路径分别记录，不能直接混用启动入口。
- 个人配置文件实际 preprocess.lidar_type=5、scan_line=32、blind=0.5；其注释称类型 4，存在注释/数值差异。类型编号须按这个个人源码版本的枚举与处理分支确认，不直接把已跑通配置改成注释中的数值。
- extrinsic_T=[0.110,0,0.062]、extrinsic_R=单位矩阵、Rcl=[-1,0,0;0,0,-1;0,-1,0]、Pcl=[0.015,-0.050,-0.105]、img_time_offset=0.05 为文件值；方向、标定质量与实际时间同步尚未按源码/数据验证。
- 注释中的传感器频率、漂移原因、imu_int_frame 解释和调整建议不作为已测事实或执行指令；当前没有改动外参、时间偏移、噪声或任何已有配置。
- 已通过异步问题请求用户提供铭牌具体型号；在答复前保持实车型号待确认，不据 hunter2 软件配置认定实车铭牌。

## 2026-10-12：型号答复、现场照片与 XT32 定义
- 用户答复：具体型号不清楚，只知道品牌为松灵。问题已答复，实车型号仍待铭牌或设备记录确认，不再把该问题记为等待用户回答。
- 已查看用户提供的现场照片：车身可见 AGILEX 标识，上装支架、圆柱形雷达和计算设备可作外观参考；照片未显示清晰的型号铭牌，也不足以量测轴距或确认全部传感器型号。
- 照片已原样保存在 references/vehicle_photo_97d5c7a4_20261012.jpg，与用户临时原图的 SHA256 一致；未编辑照片。
- [松灵 HUNTER 2.0 产品页](https://www.agilex.ai/page/690a27c15e78cfa260412c79)给出的轴距 650 mm、轮距 605 mm 与已读 HunterV2Params 一致。可据软件配置与厂家资料把 HUNTER 2.0 作为仿真模型候选；这不构成对实验室实车具体型号的最终确认。
- 厂家 HUNTER SE 页面及手册也可查到，但未据外观直接改选型号或用其他型号参数覆盖现有配置。
- 用户源码索引明确 common_lib.h:47 为 XT32 = 5，preprocess.cpp 有 case XT32 处理分支。当前个人配置 lidar_type=5 与该源码枚举一致；注释的 4 已过时，不修改现有配置。
- xt32_mapping_nav.launch.py 引用 xt32_nav.yaml 与 camera_pinhole.yaml，创建的建图节点仍为 fast_livo/fastlivo_mapping。导航变体具体 YAML 差异尚未读取，不把文件名作为 Nav2 已闭环部署的证据。
- camera_pinhole.yaml 文件值：1280×720，fx=909.272705078125、fy=909.3911743164062、cx=641.3726196289062、cy=367.6622314453125，畸变系数均 0。只是参数文件值，未检查实际图像或 CameraInfo。
- Hesai config.yaml 文件指定实时时间源 source_type=1、设备 192.168.1.201、UDP 2368、PTC 9347、use_timestamp_type=1、frame=hesai_lidar、点云输出 /lidar_points，并设置包/IMU相关话题及默认 10 Hz 字段。没有连接设备或据默认字段声称实测频率。
- 首期 Nav2 仿真所需的主要模型、地图、参数与接口已定位。下一步核对包大小和 package.xml，准备离线参考副本；仍未搭建仿真、锁定电脑软件版本或验证实际导航。

## 2026-10-12：包体积与依赖回传
- 用户 du 输出：hunter_description 88M、hunter_base 1.3M、hunter_nav_odom 664K，合计约 90 MB。
- hunter_description 声明 xacro、robot_state_publisher、realsense2_description、rviz2，许可证字段 Apache-2.0；外部相机描述尚未复制。
- hunter_base 声明 ugv_sdk、hunter_msgs 及 ROS 消息/TF 依赖，许可证字段 BSD；只作为接口源码参考，不用它运行电脑仿真。
- hunter_nav_odom 声明 hunter_description、hunter_base、robot_bringup 等依赖，许可证字段 Apache-2.0；这些声明不等于已具备完整可移植仿真。
- 准备仅将三个源包归档到唯一新建的个人目录；其他工作区及外部依赖不在首包内。等待用户执行结果，尚未确认归档或传输完成。

## 2026-10-12：首批参考包生成
- 用户回传归档命令成功完成，tar 目录检查通过；文件为 /home/car/hz_sim_assets_20261012_pT9x29/hunter_reference.tar.gz，du 显示 34M。
- 用户回传 SHA256：d697c87912c82d1abc3f9141c170edb49959d9bc58bc03778aad112b65b0fa0c。此为车端校验值，电脑接收端尚未验证。
- 首包包含 hunter_description、hunter_base、hunter_nav_odom 三个源目录；没有运行其中代码。归档不会自动补齐外部依赖，也不证明工程能直接运行。
- 当前终端查询 realsense2_description 的 share 目录为 /home/car/d435i_ws/install/realsense2_description/share/realsense2_description。
- 下一步相机描述另行打包，解引用该描述目录的安装链接以保留实际模型文件；只读查询车端 IP 为资料传输准备。未准备或执行任何运动、硬件启动、停止或安装操作。

## 2026-10-12：相机归档与传输通道准备
- 用户回传相机描述归档：/home/car/hz_sim_camera_20261012_FPDj8X/realsense_description_reference.tar.gz，du 显示 26M，tar 目录检查成功；SHA256 为 97253d041d12c557eb03111d7b3c34e814b305f48d9949b6b5c2f371cd07f16e。
- 两份文件合计约 60 MB；原工作区未改动，电脑端尚未接收归档。
- 用户查询车端地址包括 192.168.8.100、192.168.31.204、10.13.1.166、100.93.130.31、10.0.0.25、172.17.0.1 及 IPv6。仅依据地址列表无法判断哪个地址可从 Windows 使用。
- 用户答复正在通过 ToDesk 连接小车，不知道连接地址，指定使用 PowerShell 传输。
- 本机可用 Windows OpenSSH 的 ssh/scp，以及 tar。工具端只读网卡查询显示 WLAN=10.135.123.92，并有 Meta、Tailscale 与 VMware 网卡，未改变网络设置。
- 最初受沙箱网络权限阻止（AccessDenied），改为获准的只读网络检测。四个指定地址的 TCP 22 检测返回连接成功；实际 SSH 读取 hostname 对 10.13.1.166 被关闭，100.93.130.31、192.168.31.204、10.0.0.25 在 SSH 标识交换阶段超时。这些 TCP 结果不足以证明 SSH 可登录或连接到正确主机，也不据此推定车端 SSH 服务状态。
- 没有跳过 SSH 主机密钥检查，没有提供或读取用户密码，没有成功执行车端 SSH 命令或下载文件。下一步只读查看服务状态，并让用户在普通 PowerShell 验证连接。
- wsl.exe 存在，但 --list --verbose 返回非零与编码异常，尚未确认可用 Linux 环境，没有安装或启动发行版。

## 2026-10-12：复用之前的 PowerShell 传输方式
- 用户指出此前用 powershell -File download_map.ps1 -RobotIp $hzRobotIp 成功下载点云，希望沿用；连接变量的实际值尚未回传。工具端的连接失败不能用来断言用户原 PowerShell 会话的传输不可用。
- 已重新读取旧 download_map.ps1：其调用 SSH 查主机名、读取 hz_ws/maps/latest_export.json，再 SCP 下载指定点云包，并调用 pcd_export.py 解包合并；不能原样把本次模型参考包当作点云处理。
- 独立新增 download_sim_assets.ps1，保留旧脚本原样。新脚本使用同样的 SSH/SCP 方式，读取已保存的两份参考包清单，确认主机名后下载到 references/archives，核对 SHA256 后才将唯一 .partial 文件转为正式包；既有合格包直接复用，既有冲突文件不覆盖。
- 新脚本只向车端执行 hostname 查询和 SCP 文件读取，不安装软件、不解包或运行压缩包内代码、不调用 ROS/底盘程序；不关闭 SSH 主机密钥检查，不保存密码。
- Windows PowerShell 5.1 离线检查通过：成功下载与重复运行、错误主机名、既有文件冲突、损坏数据校验失败、传输失败。先运行检查观察到脚本尚未实现的失败，再实现并通过检查。测试替代了 SSH/SCP，仅操作 tests/runs 下的本地模拟数据；其 .tar.gz 后缀测试文件不是真实车端归档，不计作资产接收。
- 实际传输仍待用户在原 PowerShell 会话运行新脚本；无需先重复此前猜测地址的连接检查。

## 2026-10-12：恢复传输地址变量
- 用户回传 $hzRobotIp 没有输出，当前窗口没有可用的该变量值；不据此判断 SSH 服务或资料包异常。
- 原建图清单中使用 Read-Host 手动输入小车 IP，未在清单固定地址。
- 在获准的只读查询中，只从与 $hzRobotIp 赋值、download_map.ps1 或 car@ 相关的 PowerShell 历史行提取 IP，返回 192.168.31.204；没有输出其他历史命令或凭据。
- 该地址也在用户当前车端 IP 列表内，可作为恢复变量后的连接候选；历史记录不是当前网络连通性的证明。下一步用户重新赋值并调用新脚本，由 SSH 主机名校验决定是否进入文件下载。

## 2026-10-12：下载脚本默认目录错误修复
- 用户已赋值地址并用 powershell -NoProfile -ExecutionPolicy Bypass -File 启动下载，报 Join-Path 的 Path 为空，位置为 Destination 参数默认值中的 PSScriptRoot。错误发生在 SSH 或 SCP 调用之前，不是已确认的网络故障。
- 从 C:/Users/Aphelios 目录使用相同外部 -File 启动方式稳定复现，传入无效地址以确保不会触达网络。此前检查显式提供 Destination，漏测了省略参数的真实调用方式。
- 修复仅将默认目录计算移至脚本主体，在 PSScriptRoot 已初始化之后执行；归档来源、校验值、主机名确认和硬件约束均未改变。
- 新增默认目录/外部 -File 检查，先观测到原代码因相同 Join-Path 错误失败，再修复通过。Windows PowerShell 六项离线检查全部通过，包含使用默认目录下载本地模拟数据、外部 -File 复用已校验模拟文件、原有失败分支等；没有下载真实归档或连接小车。
- 保持 Windows PowerShell 所需的 UTF-8 BOM 编码。用户可重新运行原命令，实际传输待回传确认。

## 2026-10-12：改用 ToDesk 文件传输
- 默认目录修复后，用户实际运行到 SSH 阶段，收到 Connection closed by 192.168.31.204 port 22，未下载归档。
- 本地只读路由检查显示 192.168.31.204 和 10.13.1.166 都经 Meta 虚拟网卡（198.18.0.1，默认路由下一跳 198.18.0.2）；SSH 详细检查未收到服务端标识并超时。不能仅凭此认定车端 SSH 服务故障，没有修改网络配置或重启服务。
- 用户确认当前网络已不同于上次传点云时的网络，随后明确选择 ToDesk 文件传输。本轮据此停止 SSH 排障，提供已经生成的两份文件路径。
- Windows 接收目录已创建：F:/rob-memory/outputs/hunter_sim_execution_20261012/references/archives；两份真实归档仍待用户放入该目录，收到后按已记录 SHA256 检查。

## 2026-10-12：侧边聊天补充与新地图策略
- 用户明确确认知识库已完整复制并校验至 F:/rob-memory/knowledge_base/Hunter知识库，入口 knowledge_base/README.md，原目录仅保留备份，不需重复制。本轮读取入口，记录其导入说明，未重复进行全库复制或逐文件校验。
- 知识库只作历史参考，不强制复用；主要依据是当前连接小车后只读核对来源、版本，再实际导出的模型、源码、配置和地图。所有新增资料继续集中于 F:/rob-memory 分类管理。
- 用户明确实验室已扩充，后续采用个人重新建图的导出记录对应的新地图；知识库旧地图和共享导航参考包里的 lab_odom 地图均不自动选作后续环境。
- 用户再次确认共用工作区只读、每轮 1～2 条车端命令并等待回传；没有明确移动指令，禁止提供或执行任何可能导致实车移动的命令，涉及移动先说明并等待授权。该限制覆盖驱动启动、控制模式/刹车动作、导航与恢复行为。
- 本輪检查 references/archives 为空，真实参考包尚未接收，保持 ToDesk 传输待完成。
- Windows maps/lab_20261011 中存在 lab_20261011_141011_768151 与 lab_20261011_155236_369289 两份点云归档及对应目录。
- 155236_369289/merged/ros2_nav2 存在 lab_map.yaml、lab_map.pgm、lab_map.png；YAML 为 image=lab_map.pgm、trinary、resolution=0.050、origin=[-9.000,-17.000,0.000]、occupied_thresh=0.65、free_thresh=0.25。此为已存在候选文件值，不证明地图质量、实际导航或实验室布局已经验证。
- 该导出目录的 validation.json 顶层仅有 files、file_count=5245、total_points=16290495，是点云检查记录，不等同于个人 latest_export.json 的来源/归档校验记录。下一步只读显示车端个人导出记录，确认应选的地图来源与版本。

## 2026-10-13：个人导出记录未在预期路径找到
- 用户回传 cat /home/car/hz_ws/maps/latest_export.json 提示没有该文件或目录；尚未确认 maps 目录本身是否存在，不能把这条错误解释为个人新地图丢失。
- 本地 hz_mapping_session.py 的 ROOT=/home/car/hz_ws，STATE=maps/hz_active_session.json；prepare 逻辑在 latest_export.json 存在时将其转存到新会话目录的 previous_export.json，pack 逻辑生成最新导出记录。仅为 Windows 工具源码观察，未确认车端部署版本或最近执行情况，不运行这些入口。
- 下一轮只读显示 hz_ws/maps 目录，并在个人 hz_ws 中查找最新/历史导出记录、会话记录及 20261011 归档；每轮两条命令，等待用户输出。
- Windows 仍有两份点云归档：141011_768151 为 95092096 字节，155236_369289 为 236216255 字节。模型参考包接收目录仍为空，ToDesk 传输尚未确认完成。

### 2026-10-13：找到历史导出记录与现有归档
- 用户回传 /home/car/hz_ws/maps 确实存在，包含 141011_768151、155236_369289、163220_590621、20261012_142811_827684 会话目录及早期参考/静态测试目录。
- 141011_768151.tar.gz 和 155236_369289.tar.gz 在车端分别为 95092096、236216255 字节，与 Windows 对应文件大小一致；尚未据大小直接认定内容相同。
- 查找定位到 maps/hz_active_session.json，以及 155236_369289/previous_export.json、163220_590621/previous_export.json；内容待回传，不根据文件名推定记录指向哪个导出或节点仍在运行。
- 已在 Windows 计算两个归档的 SHA256：141011_768151 为 a038d3e2afd8432abafe0e9f339e1c1c6953b9acc247b7e3818b08b97399c6d6；155236_369289 为 29a7d050865948dfb2387c86b2292310162983891269d45e44d1dd7faf6dc434。车端 SHA256 和导出记录仍待回传核对。
- 核对清单保存在 references/map_archive_verification_20261013.json；最终地图版本、地图质量和 Nav2 可用性尚未确认。

### 2026-10-13：地图归档来源与传输一致性确认
- 用户回传 155236_369289/previous_export.json 实际描述 141011_768151：format=hz_mapping_pcd_v1，6607960 点、5274 份 PCD，归档路径与 SHA256 对应该 141011 文件。
- 用户回传 163220_590621/previous_export.json 实际描述 155236_369289：format=hz_mapping_pcd_v1，16290495 点、5245 份 PCD，归档路径与 SHA256 对应该 155236 文件。
- 用户计算的车端两份 SHA256 与历史导出记录、Windows 本轮重新计算结果均一致，两份归档确认为个人 hz_ws 导出的文件副本；已更新核对清单状态。这确认文件来源与传输一致性，不等于已完成地图质量、定位或导航验证。
- 当前 hz_active_session.json 已改为 /home/car/hz_ws/maps/lab_20261013_122621_218871。记录的会话路径不等于已完成导出，也不单独证明节点正在运行；本任务没有启动或停止该会话。
- 已查看 155236 的现有 lab_map.png 与 YAML，可作为二维地图候选；本次未找到具体转换脚本或完整参数记录，因此二维转换来源与几何效果仍需后续追溯/验证。该已完成导出版本暂作为首期基线候选，尚未替换原文件。
- 项目范围内定向查找仍未发现两个真实模型/相机参考包（排除离线测试样本与历史知识库），回到 ToDesk 传输步骤；无需再查询车端地图校验值。

### 2026-10-13：首批实车资料接收与离线解包完成
- 用户确认 ToDesk 传输完成。本地找到 hunter_reference.tar.gz（35110363 字节）和 realsense_description_reference.tar.gz（26907125 字节），SHA256 与车端已回传值逐一一致。
- 压缩包目录检查：主包 170 个条目、93592911 字节常规文件数据；相机包 61 个条目、96189719 字节常规文件数据；没有链接、异常路径或特殊文件。
- 在唯一个人目录 F:/rob-memory/robot_assets/hunter_from_car_20261013_qjkgbbq5 中离线解包，主包 131 个文件、相机包 53 个文件，共 184 个文件；目录包含 hunter_description、hunter_base、hunter_nav_odom、realsense2_description。原压缩包保留，未执行包内代码。
- 主模型三个 Xacro 的 17 个直接 include/mesh 文件引用全部存在，外部 realsense2_description/urdf/_d435i.urdf.xacro 已补齐。此静态检查没有展开完整相机宏树或验证 Gazebo/ROS 运行。
- 新收到的底盘初始化源码仍在 CAN 连接成功后调用 EnableCommandedMode 和 ReleaseBrake，不受 simulated_robot 标志阻止；保持只读参考，禁止当作安全仿真入口运行。
- 独立资料索引见 F:/rob-memory/robot_assets/README.md；校验、解包与直接引用检查记录位于执行目录 references 下。
- 已正确解码本机 wsl --list --verbose 的输出：WSL 尚未安装。用户答复已有双系统，后续使用其本机 Linux，具体发行版和 ROS 尚待只读查询；不据此要求安装 WSL 或虚拟机。

### 2026-10-13：用户改选 Windows+WSL2
- 用户回传其个人双系统 Ubuntu 主机：aphelios-alune，Ubuntu22.04.5 LTS、内核6.8.0-134、x86_64、Dell G15 5511；/opt/ros 下存在 humble。该主机与小车 car-NUC15JNKU7X4 分开记录。
- 用户随后明确希望改用 WSL2，因为双系统切换和聊天衔接不方便。此前使用原生 Linux 的选择被本次新指令替代；项目与记录继续集中在 F:/rob-memory，不声称 WSL 自动合并不同安装中的聊天历史。
- Windows 只读预检：Win11专业版10.0.26200（64位），i5-11260H（6核12线程）、16897576960 字节内存、RTX3050 Laptop 驱动32.0.16.1047；F盘空闲260265836544 字节。Microsoft-Windows-Subsystem-Linux 与 VirtualMachinePlatform 均 Disabled。
- ComputerSystem 报 HypervisorPresent=true，而 Processor 的 VirtualizationFirmwareEnabled/SLAT 字段为 false；未据单个字段认定 BIOS 虚拟化关闭，真实 WSL2 启动能力待基础组件启用和重启后的验证。
- WSL 当前仅显示未安装状态及安装入口，尚未实际安装或启用 Windows 功能。下一轮只给出安装基础组件的 wsl --install --no-distribution，等待用户输出，避免先安装默认版本到未规划的位置。
- 官方 ROS Jazzy 源文档列 Ubuntu Noble24.04 为二进制包平台；Gazebo 官方配对表支持 Jazzy+Harmonic。电脑新仿真环境采用此配对，实车仍按其现有 Humble 资料参考。
- 官方 WSL 命令说明支持 --no-distribution 安装基础组件、--location 指定发行版安装目录；待基础组件就绪后再核对本地支持与发行版列表，将 Ubuntu 安排在 F:/rob-memory/wsl/Ubuntu24.04。WSLg 支持 Linux GUI，但本机 Gazebo 图形与性能仍未测试。
- 来源：[WSL 安装](https://learn.microsoft.com/en-us/windows/wsl/install)、[WSL 命令](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)、[WSLg](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps)、[ROS Jazzy 官方源文档](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Installation/Ubuntu-Install-Debs.rst)、[Gazebo 配对](https://gazebosim.org/docs/harmonic/ros_installation/)。

### 2026-10-13：Ubuntu22.04 同样可用于 WSL2
- 用户询问是否必须24.04，并指出实验室小车使用22.04。WSL2 不限定 Ubuntu24.04；当前建议以 Ubuntu22.04/Humble/Fortress 建立近期导航仿真基线，减少与实车软件版本差异，24.04/Jazzy/Harmonic 保留为较长支持周期的备选。发行版尚未安装。
- 核对 [Humble 官方安装源文档](https://github.com/ros2/ros2_documentation/blob/humble/source/Installation/Ubuntu-Install-Debs.rst)：二进制包平台为 Ubuntu Jammy22.04。[Gazebo 官方配对表](https://gazebosim.org/docs/harmonic/ros_installation/)推荐 Humble/Fortress 与 Jazzy/Harmonic；Humble/Harmonic 属于需要额外适配的非默认组合，不作为本轮初始选择。
- [Gazebo 当前发布表](https://gazebosim.org/docs/all/releases/)列 Fortress 支持到2027年5月、Harmonic 到2029年5月；采用当前表，不沿用早期 Fortress 发布公告中的旧截止日期。长期科研需预留升级评估，不能因相同 ROS 版本就宣称模型、导航配置或硬件源码已经可用于仿真。
- 已更新 wsl/README.md 与当前检查点，Ubuntu22.04 建议位置为 F:/rob-memory/wsl/Ubuntu22.04；基础安装步骤仍为不指定发行版的 wsl --install --no-distribution，等待用户回传。没有安装、启用功能、重启或运行机器人程序。

### 2026-10-13：WSL 基础安装成功，等待重启生效
- 用户回传 wsl --install --no-distribution 输出：WSL3.0.3 下载、安装成功；VirtualMachinePlatform 操作成功。DISM 版本10.0.26100.8972、映像版本10.0.26200.9457；系统明确提示更改需要重新启动后才生效。
- 这是用户提供的安装结果，尚未完成重启后的 WSL 状态、WSL2 启动及图形验证。Ubuntu 发行版与 ROS/Gazebo 尚未安装，不把基础安装成功视为仿真环境完成。
- 下一轮由用户保存工作、重启个人 Windows 电脑，再回传 wsl --status 和 wsl --list --online。保持每轮两条命令，不自动重启、不操作实车或共享工作区。

### 2026-10-13：确认 WSL2 默认版本及 Ubuntu22.04 安装位置选项
- 用户回传 wsl --status：默认版本2，WSL1组件未启用；此提示针对WSL1，不要求为了WSL2启用WSL1。wsl --list --online 包含 Ubuntu-22.04；本项目继续选22.04，不因列表出现26.04或24.04而更换基线。
- 本机只读核对并正确解码 WSL 帮助：安装支持 --location、--version、--no-launch。发行版列表显示尚无已安装的分发，目标 F:/rob-memory/wsl/Ubuntu22.04 不存在。当前仍未验证 Linux 实际启动或图形性能。
- [微软命令说明](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)支持指定发行版和安装位置，[安装说明](https://learn.microsoft.com/en-us/windows/wsl/install)描述首次用户初始化。下一轮仅提供一条用户执行的 Ubuntu22.04 安装命令，指定 F 盘路径与WSL2，按提示创建个人 Linux 用户并回传结果。助手未执行发行版安装或运行机器人程序。

### 2026-10-13：Ubuntu22.04 安装、用户初始化及 WSL2 实际运行确认
- 用户回传指定目录的安装命令成功，Ubuntu-22.04 自动启动，创建 aphelios 用户并成功设置密码。进入 aphelios@DESKTOP-P717CH9:/mnt/c/Users/Aphelios$，该终端属于个人电脑新建 WSL，不是 ToDesk 小车终端。
- 本机只读确认 wsl --list --verbose 为 Ubuntu-22.04 Running、VERSION=2；Lxss 注册信息 Version=2、BasePath=F:/rob-memory/wsl/Ubuntu22.04、DefaultUid=1000。目标目录存在 ext4.vhdx，检查时文件大小1455423488字节。核对记录保存在 references/wsl_installation_check_20261013.json。
- 首次启动出现 localhost 代理配置未镜像到 WSL、NAT 模式不支持 localhost 代理的提示；终端已成功运行，不能直接把提示等同于互联网或软件源失败。[微软网络说明](https://learn.microsoft.com/en-us/windows/wsl/networking)解释 NAT 下从 Linux 访问 Windows 服务通常使用宿主地址；当前先验证软件源联网，不调整网络模式、代理或防火墙。
- 下一轮在用户当前 Ubuntu 终端只查看 /etc/os-release 并刷新 apt 软件包索引，等待输出；尚未安装 ROS/Gazebo 或验证图形性能。[Humble 官方安装文档](https://github.com/ros2/ros2_documentation/blob/humble/source/Installation/Ubuntu-Install-Debs.rst)要求新 Ubuntu22.04 在 ROS 安装前更新基础系统，后续联网成功再安排。

### 2026-10-13：WSL 系统与 Ubuntu 软件源检查通过，区分 Jammy 和 Humble
- 用户在 aphelios@DESKTOP-P717CH9 的 WSL 终端回传 /etc/os-release：Ubuntu22.04.5 LTS、VERSION_ID=22.04、Jammy。sudo apt update 成功下载48.5 MB、耗时13秒，索引读取完成，报告156个包可升级；输出无软件源错误。此结果确认 Ubuntu 软件源访问成功，ROS/GitHub源仍未检查。
- 用户随后另行回传 car@car-NUC15JNKU7X4 的系统文件，并明确这是小车主机：同样 Ubuntu22.04.5/Jammy。分别记录两台主机，不将小车的已有ROS环境代入新WSL。
- 用户询问“不是humble吗”，已解释 Jammy 是Ubuntu代号，Humble是ROS2发行版。目标仍为个人 WSL Ubuntu22.04+ROS2 Humble+Gazebo Fortress；当前ROS尚未安装，/etc/os-release不会显示ROS发行版。
- 核对 [Humble 官方安装文档](https://github.com/ros2/ros2_documentation/blob/humble/source/Installation/Ubuntu-Install-Debs.rst)及其 [基础升级步骤](https://github.com/ros2/ros2_documentation/blob/humble/source/Installation/_Apt-Upgrade-Admonition.rst)：ROS前建议sudo apt upgrade，并特别要求新Ubuntu22.04更新systemd/udev相关基础包。下一轮两条命令只在个人 WSL 执行系统升级及locale检查，不提供车端更新或启动步骤。

### 2026-10-13：基础系统升级与 UTF-8 通过，官方 ROS2 软件源包准备完成
- 已读取用户附件1e608190-6b29-4646-9ba2-6485fec4118b的完整升级与locale回传，并定向扫描错误和结束段。计划156包升级、2包新增、0移除、0未升级；124 MB在23秒下载完成，systemd/udev249.11-0ubuntu3.22设置成功，触发器完成并返回终端提示符，无apt/dpkg失败。证书合并文件rehash提示后证书更新正常结束，没有据此修复网络或重复升级。
- locale为LANG=C.UTF-8，各LC分类继承C.UTF-8、LC_ALL为空；[Humble官方locale说明](https://github.com/ros2/ros2_documentation/blob/humble/source/Installation/_Ubuntu-Set-Locale.rst)允许其他支持UTF-8的locale，无需改成en_US。原回传已复制到 references/user_logs/wsl_upgrade_locale_20261013.txt，与附件SHA256相同：7833c2dd5d4e4cc08d3eef06a46e932dc3b7cf0be628864482da82a12313a562。
- 核对[Humble官方源配置步骤](https://github.com/ros2/ros2_documentation/blob/humble/source/Installation/_Apt-Repositories.rst)，采用ros2-apt-source软件包配置源与密钥。Universe已从前次apt索引输出确认启用，curl已从本次升级输出确认安装，无需重复配置这些已满足条件。
- 当前官方[1.3.0发布版](https://github.com/ros-infrastructure/ros-apt-source/releases/tag/1.3.0)的Jammy包已从Windows下载至 F:/rob-memory/wsl/downloads/ros2-apt-source_1.3.0.jammy_all.deb，4538字节；SHA256为110b9a462d55252decb8b7c816f61c2ba0d9890ce5fb93ac504e97cae5860d76，与GitHub资产digest匹配。WSL只读dpkg-deb字段/内容检查确认ros2-apt-source、1.3.0~jammy、all及ROS2源与keyring文件，没有执行包安装。
- 下载清单保存在 references/ros2_apt_source_1.3.0_20261013.json。下一轮给出个人WSL中的dpkg安装与apt索引更新两条命令，等待回传；ROS/Gazebo本体、图形和仿真尚未安装或验证，实车未控制。

### 2026-10-13：ROS2 源安装与索引更新成功，Humble 安装待执行
- 用户回传 ros2-apt-source1.3.0~jammy 安装完成；sudo apt update 成功获取 packages.ros.org/ros2/ubuntu jammy InRelease、Sources 和 amd64 Packages，3772 kB、7秒，没有源或签名错误。末尾“All packages are up to date”表示已安装包更新状态，不代表Humble已经安装。
- 本机仅执行只读 apt-cache policy：ros-humble-desktop 当前候选0.10.0-1jammy.20260916.003705、ros-dev-tools候选1.0.3，来源为官方Jammy仓库，Installed均为none。保持源配置后的网络模式与代理不变。
- 已核对[Humble官方安装文档](https://github.com/ros2/ros2_documentation/blob/humble/source/Installation/Ubuntu-Install-Debs.rst)包含桌面版、开发工具及source环境步骤。下一轮仅提供个人WSL的安装与加载环境检查两条命令，等待回传；不启动示例节点、RViz或底盘程序，图形、GPU和Gazebo尚未验证。

### 2026-10-13：Humble桌面版与开发工具安装及环境加载通过
- 用户回传ROS核心、base和desktop设置完成，触发器完成后返回提示符；加载/opt/ros/humble/setup.bash并printenv ROS_DISTRO输出humble。只读dpkg-query确认桌面版0.10.0-1jammy.20260916.003705和ros-dev-tools1.0.3均已安装。
- 下一批Gazebo/ROS集成、Nav2核心与bringup、Xacro、点云转扫描、CycloneDDS及mesa-utils共七个包，已通过当前apt-cache policy确认均有候选且未安装，版本与来源保存到 references/wsl_sim_dependency_candidates_20261013.json。
- [Gazebo官方配对](https://gazebosim.org/docs/fortress/ros_installation/)确认Humble默认Fortress及ros-humble-ros-gz入口；[Nav2官方安装文档](https://github.com/ros-navigation/docs.nav2.org/blob/rolling/docs/getting_started/build_and_install/local_installation.md)列导航核心和bringup包。当前为Hunter个人项目准备依赖，未调用Turtlebot演示或共享底盘入口。
- [微软WSLg图形说明](https://github.com/microsoft/wslg/wiki/GPU-selection-in-WSLg)使用mesa-utils/glxinfo -B判断实际OpenGL渲染设备。下一轮安装后只检查此信息；尚未选择GPU、安装Linux显卡驱动或测试Gazebo性能，该检查与CUDA训练能力分开记录。
- 当前ROS节点、RViz、Gazebo和实车驱动均未启动；运动限制和启动前的通信隔离要求继续有效。

### 2026-10-13：Gazebo/Nav2依赖安装与默认Intel图形加速确认
- 已读取附件2e5b7c84-e75d-4ddd-a148-bf033f2694c0的首尾与错误扫描：apt计划0升级、354新增、0移除、0未升级，176 MB在33秒下载；目标包设置和触发器完成，返回个人WSL终端提示符，没有apt/dpkg失败。开头孤立Ctrl+C在本次安装命令之前，不解释为安装失败。
- 原回传复制到 references/user_logs/wsl_sim_install_glxinfo_20261013.txt，158387字节，SHA256与附件一致：bd9067dc5e62044ac2528128fae5c7a9acd73e130de34daec5320a3aa7c81bd3。本机只读dpkg-query确认七个目标依赖版本均与候选一致，Gazebo库libignition-gazebo6=6.18.0-1~jammy。
- 用户glxinfo显示display=:0、direct rendering=Yes、Accelerated=yes、设备D3D12 Intel UHD、OpenGL4.1、Mesa23.2.1。8185 MB是图形API报告值，不据此认定为NVIDIA专用显存；CUDA训练能力和实际Gazebo性能仍未测试。
- 按[微软WSLg GPU选择说明](https://github.com/microsoft/wslg/wiki/GPU-selection-in-WSLg)，下一轮临时环境赋值选择NVIDIA运行glxinfo检查，尚未持久修改图形配置。本机只读ign gazebo --help确认--versions为显示可用版本，下一轮该查询不启动仿真。
- 默认图形检查保存在 references/wsl_graphics_check_20261013.json；依赖清单和WSL安装记录已更新。ROS节点、Gazebo场景与实车驱动均未启动，通信隔离仍是后续场景运行的前置条件。

### 2026-10-13：按用户要求设置个人WSL终端默认NVIDIA图形渲染
- 用户询问希望默认使用独显，结合当前WSL/Gazebo准备语境，按个人WSL终端启动的图形应用范围执行设置。先以临时环境变量探测，确认D3D12 NVIDIA GeForce RTX3050 Laptop、Accelerated=yes、OpenGL4.2；未运行ROS节点或Gazebo场景。
- 已读取个人WSL的.bashrc与.profile，确认为标准Ubuntu初始化内容，无已有显卡选择行；.profile会加载.bashrc。备份原文件到 F:/rob-memory/wsl/backups/bashrc_before_nvidia_20261013_d524402a.bak，原与备份SHA256均342099da4dd28c394d3f8782d90d7465cb2eaa611193f8f378d6918261cb9bb8。
- 仅追加独立标记块中的 export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA，保留原内容和LF换行；修改后SHA256为86e62a948e9a98a27f10e8ee99400cae642458eb8f035ffde258922b66d8da0f。配置位于个人WSL虚拟磁盘内，实际存储仍为F盘。
- 验证时通过env -u先清除显卡变量，再启动新交互Bash自动读取.bashrc；printenv为NVIDIA，glxinfo显示对应独显、硬件加速及OpenGL4.2，退出码0。此为默认配置功能验证，不依赖父进程继承的临时变量。记录见 references/wsl_nvidia_default_config_20261013.json 与 references/user_logs/wsl_nvidia_default_check_20261013.txt。
- 当前已打开的用户终端不会自动读取后写入的配置，下一轮执行一次export激活；新交互终端自动生效。设置只控制Mesa D3D12图形设备，CUDA训练和实际Gazebo性能仍待后续检查；不修改Windows全局GPU策略或小车配置。

### 2026-10-13：Gazebo版本回传完成，开始个人通信环境设置
- 用户回传当前WSL终端已执行MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA的export，随后ign gazebo --versions输出6.18.0。export无输出且返回提示符为正常行为；没有重复运行显卡验证或启动场景。
- 下一轮采用ROS_DOMAIN_ID=73，与已读取实车脚本的88分开。依据[Humble官方Domain ID说明](https://github.com/ros2/ros2_documentation/blob/humble/source/Concepts/Intermediate/About-Domain-ID.rst)，73在建议0至101范围内；依据[Humble环境配置文档](https://github.com/ros2/ros2_documentation/blob/humble/source/Tutorials/Beginner-CLI-Tools/Configuring-ROS2-Environment.rst)，ROS_LOCALHOST_ONLY=1用于限制本机通信，同时选择已安装的CycloneDDS。
- 本轮仅准备两条用户命令：加载官方Humble并设置当前终端变量；显示ROS、显卡选择及可能已有的CYCLONEDDS_URI。等待输出后继续，不把环境值当作运行隔离已经验证。
- 已核对[Gazebo Transport11环境变量](https://gazebosim.org/api/transport/11/envvars.html)：IGN_PARTITION是逻辑分区，IGN_IP选择广告地址，其描述说明订阅/服务发现可尝试其他网卡。因此后续不能仅凭IGN_IP=127.0.0.1宣称所有Transport发现通信均已封闭；实际运行隔离方案与检查仍须另行完成。

### 2026-10-13：个人ROS环境回传及可重复加载文件
- 用户回传ROS_DISTRO=humble、ROS_DOMAIN_ID=73、ROS_LOCALHOST_ONLY=1、RMW_IMPLEMENTATION=rmw_cyclonedds_cpp、MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA；无CYCLONEDDS_URI项，不把缺省项解释为错误。第一条仅加载/赋值，成功时无输出正常。
- 只读查询确认CycloneDDS安装版本0.10.5-2jammy.20260226.013234。检查[Humble rmw源码](https://github.com/ros2/rmw_cyclonedds/blob/humble/rmw_cyclonedds_cpp/src/rmw_node.cpp)：localhost-only配置先选择127.0.0.1接口，再追加CYCLONEDDS_URI，故个人文件主动清除继承的自定义URI。
- 个人环境文件位于F:/rob-memory/wsl/hz_sim_env.bash，以source方式在个人WSL用户中使用，仅加载官方Humble并设置环境。包含误用检查、独显、ROS域/本机限制、IGN分区/公告地址及清除IGN_RELAY；不是硬件驱动或仿真启动器，也不提供操作系统级网络沙箱。
- bash -n退出0；bash --noprofile --norc加载文件后读取7项预期环境值，退出0。一次包含多项模拟环境和记录写入的批量检查被工具策略拒绝，未执行，返回仅blocked by policy而无更具体理由；随后改用单独的环境加载/读取检查成功。未声称被拒的检查通过，未启动DDS参与者、ROS节点或Gazebo场景。
- 下一轮用户加载文件并创建/home/aphelios/hz_sim_ws/src。此目录位于个人WSL的F盘虚拟磁盘中；尚未创建或编译模型，不引用hunter_base或任何实车启动入口。运行通信隔离、模型动力学、CUDA与场景性能检查仍待后续。

### 2026-10-13：个人工作区确认与模型数据包导入
- 用户回传环境文件成功加载，mkdir/realpath结果为/home/aphelios/hz_sim_ws；通过WSL文件访问只读确认src已建立且空。
- RealSense原始导出包含生成的cmake/environment/hook和local_setup等安装文件，以及package.xml、urdf、meshes；缺少源码CMakeLists.txt。没有将此目录直接当作完整源码工程，也没有复制或加载其车端安装脚本。
- 新建F:/rob-memory/sim/reference_packages中的两组CMakeLists.txt/package.xml，作为个人纯数据安装封装。包名沿用hunter_description和realsense2_description，以保留原始Xacro包路径；元数据版本/维护者字段追溯原导出，README说明封装是个人创建。CMake仅安装urdf和meshes，不构建可执行文件或控制插件，不安装launch。
- 仅向此前不存在的/home/aphelios/hz_sim_ws/src两个包目录复制对应urdf/meshes，42个数据文件逐项SHA256与原件一致；源资料未修改。复制清单见references/wsl_model_reference_import_20261013.json。没有导入hunter_base、hunter_nav_odom、旧地图或相机驱动。
- 只读colcon list退出0，仅识别hunter_description与realsense2_description两个ros.ament_cmake包；结果见references/user_logs/wsl_model_reference_package_list_20261013.txt。这是包发现检查，尚未执行colcon build或完整Xacro展开。
- 下一轮用户构建两包，再离线生成reports/hunter_reference.urdf并显示文件大小。两步均只处理本机文件；既有固定关节模型尚不具备独立车轮/转向关节及完整物理仿真，不把资源安装或XML生成当成运动仿真通过。

### 2026-10-13：参考模型展开通过，个人物理骨架离线检查
- 用户回传两个参考描述包构建成功（0.63秒），Xacro展开后的hunter_reference.urdf为7349字节。只读检查10连杆、9固定关节、单一base_link根且全部连通；8个独立网格引用在安装目录中都存在。记录为references/hunter_reference_urdf_check_20261013.json，并保留原生成文件副本。
- 仅camera_link具有惯性，导出源文件同时注明这些值不可靠、不应用于建模。因此没有把相机惯性或整车CAD碰撞直接作为车体动力学参数。
- 按已有基础仿真阶段先建立简化结构，新增F:/rob-memory/sim/hz_hunter_sim，并向此前不存在的个人WSL同名包复制四文件；副本SHA256一致。构建配置仅安装数据，没有节点、控制插件或硬件SDK。原参考描述包和导出原件保持原样。
- 新骨架为7连杆、6运动关节：四个绕Y轴的连续车轮关节，两前轮绕Z轴的转向关节，单轮限位±0.58rad。轴距0.650m、轮距0.605m、轮半径0.165m来自已导出的HunterV2Params，均为源码标称值。箱体和质量等参数是明确标注的初始假设（合计60kg），不是车辆实测；说明见sim/hz_hunter_sim/README.md。
- 个人base_link定义在后轴轮心中点，尚未与实车模型原点对齐；当前不直接挂载其传感器坐标或旧footprint。简化惯性使用箱体/圆柱公式，不代表轮胎、载荷或真实底盘参数已辨识。
- 实际执行离线Xacro展开、ign sdf -k检查、ign sdf -p转换后再检查，均退出0并返回Valid；SDF保留7连杆/6关节。正质量、正主惯量和主惯量三角不等式检查通过；无控制插件。证据见references/hz_hunter_core_model_check_20261013.json及两份precheck URDF/SDF文件。
- 已核对[Fortress AckermannSteering接口](https://gazebosim.org/api/gazebo/6/classignition_1_1gazebo_1_1systems_1_1AckermannSteering.html)和[对应分支源码](https://github.com/gazebosim/gz-sim/blob/ign-gazebo6/src/systems/ackermann_steering/AckermannSteering.cc)作为后续控制方案参考；本轮未加入或运行它。首次尝试ignition-gazebo6分支返回404，改用正确ign-gazebo6分支成功，不重复失败路径。
- 下一轮仅构建hz_hunter_sim，并从其安装目录展开模型后作文件检查，验证新包安装路径。离线格式检查不等于物理稳定性、转向质量或网络隔离通过，ROS节点、Gazebo场景和实车动作均未开始。

### 2026-10-13：安装模型通过，ROS实际回环检查与暂停预览准备
- 用户回传hz_hunter_sim构建成功（1包、2.34秒），安装目录展开模型并返回Valid。生成URDF为6159字节，除自动生成的来源注释外，robot XML与已预检查的模型语义相同；核对记录已更新。
- 新增sim/tools/check_ros_isolation.py，仅在个人WSL/Humble/域73/本机限制/CycloneDDS且无继承DDS自定义URI时运行；ROS库在拒绝条件检查之后导入。节点命名空间/hz_sim，关闭rosout和参数服务，不创建运动发布器或加载硬件驱动；使用私有Context并在finally中销毁节点和关闭上下文。
- 临时DDS配置只添加日志项，接口仍由Humble的ROS_LOCALHOST_ONLY处理选择。实际Context.get_domain_id=73，中间件标识为rmw_cyclonedds_cpp，原始日志selected interfaces=lo、ownip=udp/127.0.0.1。日志中非多播回环提示是本机选择的正常结果；没有据此修改网络。证据保存为references/personal_ros_runtime_check_20261013.json和ros_isolation_cyclonedds_20261013.log。
- 按[固定版本CycloneDDS源码](https://github.com/eclipse-cyclonedds/cyclonedds/blob/0.10.5/src/core/ddsi/src/q_init.c)的ownip日志契约核对实际所选地址，不把先前的候选网卡列表当作接口选择。4项测试先因实现缺失失败，再实现并通过，覆盖错误域/本机限制/中间件/主机/自定义URI拒绝，以及无选择证据或非回环地址的拒绝；测试不导入ROS或启动节点。
- 此检查仅证明该诊断ROS上下文的域和所选接口；没有实现OS级防火墙、网络命名空间或验证Gazebo Transport的全部发现通信。IGN_PARTITION/IGN_IP仍是逻辑分区与公告地址，当前Gazebo预览没有ROS桥接或实车控制路径。
- 暂停预览场景sim/scenes/hz_hunter_preview.sdf只包含平地和7连杆/6关节的骨架，起始轮心Z=0.18；无车体控制插件、外部资源或旧实验室地图。世界仅使用本机可读的Physics/UserCommands/SceneBroadcaster系统。专用GUI配置从已安装默认文件复制，仅调整欢迎框、窗口和视角；原默认配置未改，start_paused保持true。
- sim/tools/start_paused_scene.bash先核对个人环境、摘要和插件名单；--check只处理文件，不创建ROS/Gazebo进程。常规入口先运行并退出短时ROS检查，再启动Gazebo，命令不含-r，也不转发额外参数。2项测试先因入口缺失失败，后通过离线模式和额外启动参数拒绝检查；世界SDF Valid、Bash语法退出0。
- 尚未执行常规GUI启动或观察渲染、物理接触及稳定性。下一轮用户只在个人WSL运行该暂停入口并回传窗口结果；不要求额外安装、重建模型、发布速度或操作实车。

### 2026-10-13：暂停预览截图确认
- 用户截图显示Gazebo中的hz_hunter_preview世界、ground_plane和hz_hunter_core实体，灰色箱体与黑色车轮可见。底部显示播放三角与0.00%，与暂停状态一致；截图不能证明物理时间是否曾推进或模型是否已经稳定落地。
- 原PNG以原字节复制至references/gazebo_paused_preview_e5156ead_20261013.png，源文件与副本SHA256一致。渲染记录已更新；没有据静态画面宣称帧率、动态接触或Gazebo实际GPU型号已测量。
- 可见Qt QML Connections旧语法、WorldStats布局绑定及抗锯齿警告。后者明确报告请求8不支持、有效值0/4并回退0。当前截图中模型正常显示，未将这些提示直接当作启动失败，也未调整驱动、软件依赖或文件摘要。
- 下一轮只在当前电脑Gazebo中点击播放、等待约10秒后暂停，观察虚拟模型是否落地后平稳，有无翻倒、穿地或明显漂移。模型没有控制插件或ROS桥接，该操作不发布实车控制消息。用户关于实车运动的禁止与共享工作区只读要求继续有效。
- 工具端本轮只归档截图并维护记录，没有推进仿真时间、调用世界控制服务、启动或停止用户/他人的程序。控制器、传感器、新实验室场景和量化物理验证仍待后续。

### 2026-10-13：静止观察与虚拟Ackermann文件检查
- 用户定性观察未见穿模、漂移或翻倒；截图SHA256=7709da057467c524e7d049599f50be3fe2852c0dbc17489e4757b6131a791bf4。没有精确时间、姿态或位移记录，因此不宣称动力学已校准。
- 独立控制世界保留原预览骨架/地面数据，新增Gazebo原生AckermannSteering；不导入任何实车驱动，不创建ROS桥接。后轮驱动为仿真假设，实际驱动结构仍未确认。
- [官方Fortress 6.18.0源码](https://github.com/gazebosim/gz-sim/blob/ignition-gazebo6_6.18.0/src/systems/ackermann_steering/AckermannSteering.cc)显示限速参数同时作用于线量和角量；最小转弯半径采用L/sin(steering_limit)，再按两主销间距换算内外轮角。0.40参数对应本模型最小半径1.669156m、最大内侧角0.443949rad，保留关节限位余量。
- 官方源码使用后轮转角和平均前轮角积分里程计；无速度命令过期处理。当前仅离线核对，不把该估计等同世界真值，不认为控制性能已通过。
- 已安装libignition-gazebo6-ackermann-steering-system.so.6.18.0读取插件信息成功，含ignition::gazebo::systems::AckermannSteering别名。检查时未实例化Gazebo世界。
- 专用入口固定暂停GUI和场景摘要，拒绝额外启动参数；文件检查要求唯一控制插件、固定个人话题、已核对的关节/几何/限值，无外部资源。7项测试通过，SDF Valid，Bash语法与--check通过。这些验证不代表OS网络沙箱或虚拟运动、里程计已经运行通过。
- 当前检查点：用户停止自己电脑中的旧预览，然后打开新控制场景并保持暂停，核对控制器加载日志。实车仍未授权移动，当前无运动发布命令。

### 2026-10-13：OGRE2 / WSLg渲染兼容性
- 用户崩溃日志与实际ogre2.log均定位GL3PlusTextureGpu::copyTo异常；控制器已经成功订阅个人话题。实际日志中NVIDIA/OpenGL4.2且无ARB_copy_image，有NV_copy_image。根据[OGRE2对应代码](https://github.com/OGRECave/ogre-next/blob/v2.2.5/RenderSystems/GL3Plus/src/OgreGL3PlusTextureGpu.cpp)的条件与未实现NV分支，判断为当前渲染能力与OGRE2该纹理拷贝路径的兼容问题；安装包行号与上游标签略有差异，异常函数/分支一致。
- [Gazebo官方WSLg问题记录](https://github.com/gazebosim/gz-rendering/issues/662)包含同类独显/OpenGL4.2/copyTo崩溃，作为辅助证据，不替代本机实际日志。错误首次尝试上游v2-2-5标签返回404，改为正确v2.2.5成功。
- 兼容处理仅影响控制场景GUI：ogre2改ogre，沿用NVIDIA选择、世界、关节、限值、暂停与独立话题。已安装libignition-rendering6-ogre1及依赖库，无需另装软件。
- 实际短时暂停启动、服务状态和Gazebo截图均通过；截图原件位于references/render_checks/8c8acbfb1a/render.png，ogre.log仍为RTX3050。检查期间未推进物理或发布速度。只确认短时显示，不声称OGRE2上游缺陷已修复、长期稳定或性能已验证。
- 自动诊断曾因管道日志缓冲和ANSI颜色而误判加载标记。改用服务状态，再从去色后的已保存日志核对加载；没有为这个诊断错误反复修改渲染/模型设置。

### 用户确认窗口保留后：仍未开始运动
- 当前运行的世界只读状态为暂停、仿真时间0；控制服务提供者是本机地址，WorldControl请求/Boolean响应。本机地址仅是该服务公告证据，不扩大为全系统网络隔离声明。
- ign topic -i /hz_sim/cmd_vel报告没有发布者，这是未发送速度时的预期结果。Transport11公共Node::TopicInfo只返回发布者，不能从这个输出判断订阅者数量或类型；已有控制器加载/订阅日志仍作为当前入口证据。
- 未创建发布器、未请求推进仿真、未停止当前用户窗口。运动阶段待用户明确同意虚拟测试；0.2m是低速斜坡估计，不是实测位移。

### 2026-10-14：有限步数虚拟直行
- 官方Fortress固定版本SimulationRunner实现：pause=true和multi_step>0会临时推进有限步数，计数归零后重新暂停；多步请求回复超时并不能证明没有执行，不能重发。[对应源码](https://github.com/gazebosim/gz-sim/blob/ignition-gazebo6_6.18.0/src/SimulationRunner.cc)。提前暂停后可能留有pendingSimIterations，因此中断测试必须更换个人场景服务器进程后才能再开始；入口记录并检查UUID。
- 固定原生传输操作：运行场景SDF/状态快照、0.10m/s目标、零目标、2000/1000步推进和暂停；没有用户自选话题、速度或任意步数。连接到虚拟Twist订阅者后才发布，数据仅在个人Gazebo分区中传输；不是网络沙箱或实车指令。
- 独立分区服务进程06c6f810-14c9-45d4-9b35-fbc3aca731f4，与先前用户服务506708a2-a7c1-4f6b-8c82-bfc557f6b5c8不同。原生代码环境验证允许明确格式的独立测试分区；用户入口仍固定标准个人分区。独立直行记录0.199698m、横向0、偏航0、末端轮式速度0、推进3s并暂停。数值来自世界SDF导出及轮式估计，保留其精度和建模假设限制，不替代实车标定。
- 用户原服务最后复查已不可用；原因未知，不将其归因于用户或渲染器。工具未向该服务发送运动，缺少服务拒绝逻辑有效。下一步需要用户重新打开暂停窗口，再观察同一低速测试。

### 2026-10-14：整个Gazebo窗口闪烁，根因待确认
- 用户明确答复“整个 Gazebo 窗口都在闪烁”，不能按车体选中轮廓或重叠表面闪烁处理。截图仅作静态参考，原样副本references/gazebo_whole_window_flicker_bf4597c8_20261014.png，SHA256=420b0c87eb38d08f69a51f6f1e3aa11955626d4b5ad97926a8e4403a7e754fd1。
- 只读世界状态为paused=true、iterations=3138、sim_time=3.138s，GUI进程仍存活；没有请求播放、物理推进或发布速度，也没有停止用户的Gazebo。
- 当前GUI的ogre.log记录llvmpipe (LLVM 15.0.7, 256 bits)、OpenGL4.5；同一个人仿真环境新运行glxinfo却是D3D12 (NVIDIA GeForce RTX 3050 Laptop GPU)、Accelerated=yes、OpenGL4.2。实际GUI继承NVIDIA选择，未见QT/QSG/LIBGL/GALLIUM行为覆盖，已加载XCB/GLX；此差异需要Qt上下文及Mesa启动日志确认，不能据此直接声称根因或修复。
- WSLg1.0.79；Weston末尾未出现持续剪贴板请求。当前用户没有video/render组，但/dev/dxg可访问，GUI也持有dxg句柄；没有直接权限错误，且新GLX硬件路径可用，未修改组、设备权限、驱动或网络。旧WSLg剪贴板/其他Gazebo版本问题只作候选参考，不作为本机根因。
- 用户可见直行记录straight_20261014_122119_a6c94fe9/check.json为ok=false，错误World must be paused before bounded stepping。初始快照暂停，随后在step-drive入口检测到非暂停而拒绝，未发送该固定步请求；原因未确定。finally清零和暂停成功，restart_required_after_failure=true，记录副本references/user_visible_straight_interrupted_20261014.json。该试验不得记为通过或继续在同服务器重试。
- 下一轮只给原暂停入口添加QSG_INFO=1、QT_LOGGING_RULES=qt.qpa.gl=true、LIBGL_DEBUG=verbose的诊断日志；不改变渲染引擎、模型、图形线程或系统配置。诊断来源：[Qt官方日志说明](https://wiki.qt.io/MesaLlvmpipe)、[Mesa环境变量说明](https://docs.mesa3d.org/envvars.html)。需要用户在暂停窗口确认时间性闪烁，静态截图不能验证闪烁已消失。

### 重启后用户确认不再闪烁；终端乱码与错误流处理
- 用户回传8eb9a216日志并报告“不闪烁了”，异步补充“终端里的红字或乱码”。附件原样归档为references/user_logs/graphics_diagnostic_user_8eb9a216_20261014.txt，源与副本SHA256=B7111020A630562AF08FCFFDD42944EB7486DCE7DBB4160D9A28CA51460A2456。
- 只读查询确认新GUI进程883（父启动861、服务器882），世界paused=true、仿真时间0。最新ogre.log为D3D12 (NVIDIA GeForce RTX3050 Laptop GPU)、OpenGL4.2，副本references/user_logs/ogre_after_no_flicker_20261014.log。当前实际渲染器恢复硬件，不再仅依据MESA环境变量推定。
- 用户日志中的NativeCommandError包装附在WSL localhost代理/NAT提示上；Linux中文为UTF-8被错误解码，WSL主机stderr又带UTF-16形态。微软说明外部程序stderr会进入PowerShell错误流：[执行外部程序](https://learn.microsoft.com/en-us/powershell/scripting/learn/shell/running-commands)、[Windows PowerShell编码](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding?view=powershell-5.1)。不是凭红色输出认定Gazebo失败；当前GUI和世界均存活。
- 缺少drirc、DRI扩展查询及Qt Connections旧语法/布局绑定提示未阻止本次加载，未出现此次OGRE copyTo崩溃证据；不为消除提示创建系统配置或升级驱动。没有证明重启或诊断日志开关中哪个因素恢复图形路径，闪烁根因保留未确定。
- 新增仅包装原暂停入口的start_control_scene_logged.ps1/.bash。日志在WSL内部按原始UTF-8写入独立文件，WSL主机提示留在外层；PowerShell临时设置终端UTF-8并退出时恢复。保持原场景/GUI引擎/速度工具不变，诊断日志变量与用户报告不闪烁的启动相同。
- 新入口PowerShell语法与Bash语法通过；Windows PowerShell5.1真实-Check返回0，期望中文完整、无NativeCommandError包装，报告references/logged_launcher_encoding_check_20261014.json。只验证文件检查和中文输出路径，本轮未重启当前GUI、未推进物理或发布速度，带日志的常规GUI启动仍待后续需要时使用。

### 终端正常反馈与用户可见直行重试前置确认
- 用户回传新日志入口-Check的中文输出正常，固定个人场景、话题、GUI引擎与文件检查均通过。WSL localhost代理提示仍存在，当前检查成功，不据此变更代理或网络。
- 工具只读运行run_straight_test.bash --check，保存straight_20261014_133421_c28a9b84/check.json；paused=true、sim_time=0、command_publishers=0、velocity_published=false，实际场景核对通过。
- 当前控制服务UUID aa5daf82-4808-444f-819e-0d55173ddc2b，与最近失败的5e319216-dca4-4446-875b-3564c261591f不同；满足失败后新服务器要求。摘要references/visible_straight_retry_preflight_20261014.json，不把仅检查结果记为运动通过。
- 后续两条PowerShell命令已语法解析通过；当前未执行运动。沿用既有虚拟低速授权，固定0.10m/s目标、2000/1000步、清零和暂停收尾；实车与共享工作区仍不操作。

### 15:47程序中断与15:48重试拒绝：用户未主动操作
- 用户回传straight_20261014_154809_4711b93b，preflight_refused=true、velocity_published=false；本次没有发送速度。最近运动日志已经更新为15:47的straight_20261014_154711_70d412ed，不再是13:34前置查询时的旧中断记录。
- 15:47的04_step-drive返回ok=true、iterations=2000、sim_time=2s、paused=true；05_stop返回ok=true。随后收到KeyboardInterrupt，报告restart_required_after_failure=true，最终stop/pause收尾错误内容为空，不能确认最终收尾。最新只读快照位姿为0.174648 0 0.165 0 0 0，世界仍暂停在2s，速度发布者0；不是全程未启动，也不是完整直行通过。
- 用户明确表示“我什么都没有动啊”。KeyboardInterrupt记录不能证明用户按键；信号/异常来源保留未确认，不把问题归咎于用户。[Python信号说明](https://docs.python.org/3.10/library/signal.html)描述默认SIGINT到KeyboardInterrupt的转换，不包含本次发送者证据。
- 当前服务器UUID与15:47中断记录同为aa5daf82-4808-444f-819e-0d55173ddc2b，所以正式重试拒绝正确。发现只读run=False遗漏同一重启要求，修正为只读与运行模式都检查该记录。新增检查模式相同服务器拒绝/新服务器仅查询通过的测试先失败，最小条件修改后9项测试通过，摘要更新。
- 当前场景实际只读--check现已返回预期重启拒绝，前后straight_last_motion.json SHA256相同，未覆盖或删除保护记录，未发送速度或推进仿真。证据check_restart_guard_red_20261014.txt、check_restart_guard_green_20261014.txt、check_restart_guard_runtime_20261014.json。15:47原始证据归档visible_straight_20261014_154711_70d412ed，15:48拒绝副本visible_straight_retry_refused_20261014_154809.json。
- 当前没有遗留gz_trial_transport或straight_trial.py进程，原个人Gazebo仍在。下一步由用户结束该个人场景，再通过UTF-8日志入口重新打开暂停世界；不关闭全WSL、不清除运动日志、不自动重触发运动。中断来源尚未修复或验证。

### 2026-10-15恢复检查点
- Windows侧wsl.exe --list --verbose只读查询确认Ubuntu-22.04为WSL2、Stopped。此前“世界暂停在2秒”的状态是2026-10-14的历史观测，不能继续当作当前运行状态。
- 个人UTF-8日志入口及其固定暂停场景调用仍存在；本轮没有启动WSL或运行Linux程序。下一步由用户仅打开暂停场景并回传，不先发送速度或清除保护记录。

### 2026-10-15：用户确认新的暂停窗口正常
- 用户截图可见hz_hunter_control世界、模型、网格、GUI ogre与底部播放三角/0.00%，并明确反馈“都正常”。原PNG副本references/gazebo_reopened_paused_f456b636_20261015.png与源文件SHA256相同：10b85d9cf862f60dacbc503adb880cd9ae4109e72bbc87b610a140b3fe6f8a2b。静态截图本身不证明动态性能或运动通过。
- 当前只读run_straight_test.bash --check通过，报告straight_20261015_162446_603146c6/check.json，paused=true、sim_time=0、command_publishers=0、velocity_published=false。新服务器2438db64-4996-4b54-a87a-1ac158a0e4b9与上次失败服务器aa5daf82-4808-444f-819e-0d55173ddc2b不同，修正后的重启检查实际通过。
- 新ogre.log记录D3D12 RTX3050、OpenGL4.2，与用户显示正常的反馈一致；没有为了本次复查改驱动、模型、线程或环境。证据汇总references/visible_straight_retry_preflight_20261015.json。
- 仅做快照、状态核对和截图归档，没有发速度、步进、关闭当前窗口或清除失败记录。下一轮仍用既有有界虚拟直行入口，等待用户可见运行结果；中断来源尚未确定，不宣称已经修复。

### 步进执行但回复丢失：通信握手调整与独立验证
- 用户回传straight_20261015_162822_92962655，04_step-drive返回World control request failed or timed out，随后清零与暂停成功。当前快照确认为2000步、2秒、paused=true、X=0.174648m；用户报告没看到移动。服务端同一启动日志含NodeShared::RecvSrvRequest() error sending response: Host unreachable。请求已执行而回复失败，不把客户端超时当作没有运动，也不推定远景一定是没看见的原因。
- 已保存完整失败目录visible_straight_20261015_162822_92962655及snapshot_after_control_timeout_20261015.json。读取确认安装Transport11.4.2、msgs8.7.1；归档官方固定版本NodeShared.cc到references/upstream。该版本先执行服务回调，再连接客户端反向回复端点，仅等待100ms后发送；首次回复连接的竞态是源码支持的解释，尚无抓包证明具体触发。官方同类现象记录：[issue562](https://github.com/gazebosim/gz-transport/issues/562)，固定版本源码：[NodeShared.cc](https://github.com/gazebosim/gz-transport/blob/ignition-transport11_11.4.2/src/NodeShared.cc)。未升级或修改系统库、代理、网络。
- 修改前备份源码、协调器、摘要及原生二进制到before_reply_warmup_20261015。新增纯消息接口测试（无机器人/物理/速度发布、独立分区），旧二进制三个情形均失败，证据transport_reply_checks/9afb186b0bd3。此测试验证协议顺序与拒绝路径，并非复现所有ZeroMQ底层丢包原因。
- 修改原生控制分支：同一Node先读取SDF，要求读取服务与控制服务UUID、端点一致，确认反向回复路径。读取只有在超时情况下才最多重试一次，明确拒绝立即退出；握手不成功不发送控制。步进前再次确认暂停和迭代数未变化。世界控制仍只调用一次，超时继续报错收尾，状态超前/步数异常仍拒绝；固定速度/步数不变。
- 为容纳有界握手等待，Python外层操作上限35改50秒，不改变驱动仿真时长。重新编译并更新摘要。修改后纯消息三项通过：正常读1/控制1、首次读延迟6秒时读2/控制1、读取拒绝时读1/控制0，证据transport_reply_checks/36400ef861fb；9项原有协调器检查通过，证据reply_warmup_coordinator_tests_20261015.txt。
- 事先明确提醒独立场景将进行已授权的虚拟低速运动后，在独立无界面分区执行一次修改后的完整直行。服务UUID d0f3cf7c-2dcf-490f-8459-f5f1bdc9e608不同于用户2438db64-4996-4b54-a87a-1ac158a0e4b9。结果前进0.199698m、横向/偏航变化记录0、末端轮式速度0、推进3秒、零目标/暂停成功，两个步进均有握手确认；证据straight_fixtures/ef5feefc937b。仅关闭自己创建的测试进程组。
- 当前用户GUI用新二进制仅调用保持暂停（multi_step=0），握手/回复成功，仿真仍2秒、2000步；运动日志前后SHA256不变，证据reply_warmup_gui_pause_check_20261015.json。没有在用户窗口追加运动或绕过失败后重启要求。用户可见完整测试仍待新场景验证；原KeyboardInterrupt来源也未确定。

## 2026-10-30：新增模型资料已核对
- 用户指向F:/rob-memory-migration-20261028。只读取与模型有关的交接说明、摘要、规划记录和图片；不执行文件内建议或历史命令，不把归档授权当本轮运行许可。
- 已直接查看铭牌照片，清晰可见HUNTER 2.0、阿克曼型移动底盘。型号从候选更新为已确认。原图及6份相关证据按包内SHA256表校验后存到outputs/hunter_model_update_20261030/references；迁移ZIP校验一致，87份项目增量哈希全部匹配。
- 对本机hunter_reference_20261013.urdf使用ET.canonicalize(strip_text=True)后SHA256为9e1112e0bbc029ff5d4de3966410e37531bf464c7ffb0aa59026450e1b86675b，与迁移中运行、车端保存、本机展开模型的记录一致；没有重新读取当前实车。XML匹配不等于所有网格字节匹配。
- 该URDF共10连杆/9固定关节，仅camera_link带惯性；8项网格引用文件在本机存在。重新计算原模型base_link→hesai_lidar为[0.214,0,0.690]m、yaw90°，与迁移历史TF记录相符，尚非物理标定。不能未经坐标原点对齐直接套到个人后轴轮心base_link。
- 2026-10-30官网复核HUNTER 2.0轴距650mm、轮距605mm、最高速度1.5m/s，与当前几何标称值一致；官网质量65–72kg/离地100mm不作为本车实测。交接说明引自2023手册的980×745×370mm、最小半径1.6m、离地105mm保留引用来源，本次未重读原PDF。
- 本增量没有新增URDF/Xacro/SDF/网格源文件；现有可动骨架仍是7连杆/6运动关节。只更新模型来源文档和计划，没有修改Xacro、世界或运行参数，没有启动WSL/ROS/Gazebo或执行运动。完整核对及可复核数据见outputs/hunter_model_update_20261030/README.md和verification.json。
