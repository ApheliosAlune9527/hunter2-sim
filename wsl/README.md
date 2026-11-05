# Hunter 电脑端 WSL2 环境

2026-10-13，个人 WSL Ubuntu22.04.5/Jammy 已在F盘正常运行。ROS2 Humble、开发工具、Gazebo Fortress6.18.0、Nav2及所列模型/传感器工具已安装并核对包版本。用户要求默认使用独显；NVIDIA RTX3050 Laptop、硬件加速与OpenGL4.2已检查通过，并写入个人WSL的.bashrc，新交互终端的自动选择已验证。用户已在现有终端执行export，Gazebo命令行版本回传6.18.0；个人仿真和通信隔离待后续完成。

Jammy 是 Ubuntu22.04 的代号，Humble 是 ROS2 的发行版名。小车 `car@car-NUC15JNKU7X4` 与个人WSL均为Ubuntu22.04.5，分别确认使用Humble；两套环境独立，WSL的安装状态通过其自身输出和包检查确认。后续更新与安装步骤的执行终端为个人电脑 `aphelios@DESKTOP-P717CH9`，共享小车仍保持只读。

WSL2 不要求 Ubuntu 24.04。用户进一步指出实车采用 Ubuntu22.04/Humble；为方便参考现有模型、Nav2 配置和后续实车适配，当前建议组合调整为 **WSL2 + Ubuntu 22.04 + ROS 2 Humble + Gazebo Fortress**。Ubuntu22.04 是 [Humble 官方二进制包平台](https://github.com/ros2/ros2_documentation/blob/humble/source/Installation/Ubuntu-Install-Debs.rst)，Humble/Fortress 属于[官方推荐配对](https://gazebosim.org/docs/harmonic/ros_installation/)。相同 ROS 版本有助于减少版本迁移工作，仍需验证个人仿真模型和导航配置，不能据此认定原实车程序可以直接作为仿真入口。

此前的 Ubuntu24.04/Jazzy/Harmonic 是支持周期更长的备选方案，并非硬性要求。2026-10-13 核对[Gazebo 当前发布表](https://gazebosim.org/docs/all/releases/)：Fortress 支持到 2027 年 5 月，Harmonic 支持到 2029 年 5 月。后续长期研究需提前评估升级。现有双系统 Ubuntu22.04/Humble 是另一套环境，其 ROS 安装不会自动出现在当前新建的 WSL Ubuntu 中。

Ubuntu22.04 的安装目标为 `F:\rob-memory\wsl\Ubuntu22.04`。本机 WSL 帮助已确认安装命令支持 `--location` 与 `--version`，用户在线列表确认发行版名称为 `Ubuntu-22.04`。项目资料和执行记录继续保存在 `F:\rob-memory`；Linux 源码编译目录安排在 Ubuntu 自身文件系统，其虚拟磁盘集中到上述 F 盘目录。

后续步骤按用户每轮 1～2 条命令推进：

1. WSL 基础组件安装输出及后续状态、在线发行版列表已回传。默认版本为2，WSL1未启用，不因此增加 WSL1 安装步骤。
2. 用户已将 Ubuntu22.04 安装到计划目录，个人用户初始化成功；安装位置和实际 WSL2 运行状态已核对。
3. WSL 系统版本、Ubuntu软件源、基础系统升级及 UTF-8 语言环境已核对成功。图形与 GPU 后续验证，当前不承诺 Gazebo 实际性能。
4. Humble及仿真依赖均已安装。WSLg NVIDIA独显硬件加速和新交互终端的默认选择已验证；用户已激活当前终端设置并确认Gazebo命令行版本6.18.0，下一轮设置和显示个人ROS通信环境。
5. 在任何 ROS 仿真启动前配置并验证独立控制通道与本机通信隔离，避免接入实车域；实车底盘程序不作为个人仿真入口。

基础安装命令 `wsl --install --no-distribution`、后续 `wsl --status` 与 `wsl --list --online` 已由用户执行并回传。发行版安装依据[微软命令说明](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)与本机帮助，用户已执行成功：

```powershell
wsl --install Ubuntu-22.04 --location "F:\rob-memory\wsl\Ubuntu22.04" --version 2
```

首次启动已创建 `aphelios` 用户并设置密码，当前终端为 `aphelios@DESKTOP-P717CH9:/mnt/c/Users/Aphelios$`。安装验证见执行记录 references/wsl_installation_check_20261013.json。

启动出现 localhost 代理未镜像的 NAT 模式提示，但 Ubuntu软件源和ROS软件源索引更新均已成功。当前未据此提示调整网络配置。网络原理见[微软 WSL 网络说明](https://learn.microsoft.com/en-us/windows/wsl/networking)。Humble 安装前的基础系统升级已按官方文档完成。

ROS2 软件源配置使用[官方 ros2-apt-source 包方式](https://github.com/ros2/ros2_documentation/blob/humble/source/Installation/_Apt-Repositories.rst)。[1.3.0 发布版](https://github.com/ros-infrastructure/ros-apt-source/releases/tag/1.3.0)的 Jammy 包已通过 Windows 下载到 `F:\rob-memory\wsl\downloads\ros2-apt-source_1.3.0.jammy_all.deb`，4538字节，SHA256与GitHub资产digest匹配。用户已安装版本1.3.0~jammy，ROS索引刷新成功，下载3772 kB、耗时7秒。此配置包版本号独立于 ROS2 Humble 版本。

已完成的 ROS2 软件源配置步骤：

```bash
sudo dpkg -i /mnt/f/rob-memory/wsl/downloads/ros2-apt-source_1.3.0.jammy_all.deb
sudo apt update
```

下载与安装核对见执行目录 references/ros2_apt_source_1.3.0_20261013.json，升级与locale回传副本保存在 references/user_logs/wsl_upgrade_locale_20261013.txt。

已按[官方 Humble 安装文档](https://github.com/ros2/ros2_documentation/blob/humble/source/Installation/Ubuntu-Install-Debs.rst)在个人WSL完成：

```bash
sudo apt install ros-humble-desktop ros-dev-tools
source /opt/ros/humble/setup.bash && printenv ROS_DISTRO
```

用户回传环境值为 humble。只读dpkg-query确认ros-humble-desktop=0.10.0-1jammy.20260916.003705、ros-dev-tools=1.0.3。此检查尚未验证RViz/Gazebo图形或仿真质量，当前未启动ROS节点或控制程序；终端图形默认选择按后续用户请求单独设置。

已在个人WSL完成配套软件安装及默认图形信息检查：

```bash
sudo apt install \
  ros-humble-ros-gz \
  ros-humble-navigation2 ros-humble-nav2-bringup \
  ros-humble-xacro ros-humble-pointcloud-to-laserscan \
  ros-humble-rmw-cyclonedds-cpp mesa-utils
glxinfo -B
```

安装回传确认354个新增依赖、无包移除，176 MB在33秒下载；触发器完成并返回提示符。只读dpkg-query确认七个目标包版本与候选记录一致，libignition-gazebo6=6.18.0-1~jammy。记录见 references/wsl_sim_dependency_candidates_20261013.json，原回传保存在 references/user_logs/wsl_sim_install_glxinfo_20261013.txt。

图形检查确认display=:0、direct rendering=Yes、Accelerated=yes、D3D12 Intel UHD、OpenGL4.1。记录见 references/wsl_graphics_check_20261013.json；这是OpenGL设备检查，尚未验证实际Gazebo性能或CUDA训练。

已按[微软WSLg GPU选择说明](https://github.com/microsoft/wslg/wiki/GPU-selection-in-WSLg)临时指定NVIDIA进行图形信息检查，随后按用户要求保存默认设置：

```bash
export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
```

该行已追加到 `/home/aphelios/.bashrc` 的独立标记块中，作用于新开的个人WSL交互Bash终端及其启动的Mesa D3D12图形应用。原文件已备份到 `F:\rob-memory\wsl\backups\bashrc_before_nvidia_20261013_d524402a.bak`，原文件与备份SHA256一致；配置记录见 references/wsl_nvidia_default_config_20261013.json。

验证时先清除继承的显卡选择变量，再启动新交互Bash：自动值为NVIDIA，glxinfo显示D3D12 NVIDIA GeForce RTX3050 Laptop、Accelerated=yes、OpenGL4.2。原始验证结果保存在 references/user_logs/wsl_nvidia_default_check_20261013.txt。该设置范围为终端启动的OpenGL图形应用，CUDA能力仍待独立检查。

用户已在当前个人WSL终端执行以下命令，export没有输出，版本回传6.18.0：

```bash
export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
ign gazebo --versions
```

版本选项已经通过本机帮助确认仅显示可用版本，不启动仿真服务器。当前未运行ROS节点、Gazebo场景或实车程序，启动前必须先完成个人通信与控制通道隔离。

用户已在个人WSL终端加载官方Humble环境并设置个人通信参数：

```bash
source /opt/ros/humble/setup.bash && export ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
env | grep -E '^(ROS_DISTRO|ROS_DOMAIN_ID|ROS_LOCALHOST_ONLY|RMW_IMPLEMENTATION|CYCLONEDDS_URI|MESA_D3D12_DEFAULT_ADAPTER_NAME)='
```

第一条成功时通常没有输出；用户回传humble、域73、本机通信1、CycloneDDS及NVIDIA，符合预期。73与实车脚本中的88分开，位于[ROS官方建议的0至101范围](https://github.com/ros2/ros2_documentation/blob/humble/source/Concepts/Intermediate/About-Domain-ID.rst)内；ROS_LOCALHOST_ONLY依据[Humble官方环境配置说明](https://github.com/ros2/ros2_documentation/blob/humble/source/Tutorials/Beginner-CLI-Tools/Configuring-ROS2-Environment.rst)限制本机通信。变量检查不等同于完整运行隔离验证，Gazebo Transport、独立控制话题与后续运行检查仍待完成。

已创建个人环境文件 `F:\rob-memory\wsl\hz_sim_env.bash`。以后每个个人WSL终端手动加载一次即可获得上述设置；文件本身不启动进程，不加入全局自动ROS启动。Bash语法与新终端加载检查均退出0；记录见 references/personal_sim_environment_check_20261013.json。

文件清除继承的CYCLONEDDS_URI，避免自定义DDS配置覆盖本机通信选择；Humble的行为依据[rmw_cyclonedds源码](https://github.com/ros2/rmw_cyclonedds/blob/humble/rmw_cyclonedds_cpp/src/rmw_node.cpp)。另清除IGN_RELAY并设置IGN_PARTITION=hz_sim_aphelios_73、IGN_IP=127.0.0.1；[Transport11说明](https://gazebosim.org/api/transport/11/envvars.html)明确分区属于逻辑分隔、IGN_IP选择公告地址，不能据此宣称发现通信全部受到网络封闭。实际运行隔离检查仍待完成。

下一轮在个人WSL终端加载文件并建立个人仿真工作区：

```bash
source /mnt/f/rob-memory/wsl/hz_sim_env.bash
mkdir -p ~/hz_sim_ws/src && realpath ~/hz_sim_ws
```

用户已回传第一条成功加载环境、第二条显示 `/home/aphelios/hz_sim_ws`。源码与编译工作区位于WSL自身Linux文件系统内，实际储存在F盘的Ubuntu22.04虚拟磁盘。

个人工作区中已准备两个只含模型数据的描述包：hunter_description、realsense2_description。对应urdf/meshes共42个文件与Windows导出原件逐项SHA256一致；colcon已识别两个预期包。个人CMake/package.xml封装模板及说明见 `F:\rob-memory\sim\reference_packages`；相机导出来自安装共享目录，未直接执行或使用它的车端安装脚本。

下一轮在当前已加载个人环境的WSL终端构建这两个描述包：

```bash
cd ~/hz_sim_ws && colcon build --symlink-install --packages-select realsense2_description hunter_description
```

第一条成功后，再加载个人安装环境，离线展开Xacro并显示生成文件大小：

```bash
source ~/hz_sim_ws/install/setup.bash && xacro ~/hz_sim_ws/src/hunter_description/urdf/hunter.urdf.xacro -o ~/hz_sim_ws/reports/hunter_reference.urdf && ls -lh ~/hz_sim_ws/reports/hunter_reference.urdf
```

用户已回传两包构建成功（0.63秒）、参考URDF生成（7349字节）。检查确认10连杆、9固定关节及8个独立网格安装资源可读。现有模型主要为外形与坐标参考，尚不具备车轮/转向关节及车体惯性，不能直接作为运动仿真模型。

个人简化物理模型已准备在 `/home/aphelios/hz_sim_ws/src/hz_hunter_sim`，Windows源文件与参数说明位于 `F:\rob-memory\sim\hz_hunter_sim`。包含四个车轮旋转和两个前轮转向关节；质量与箱体尺寸明确为初始假设。离线Xacro/URDF/SDF检查通过，无控制插件或启动程序；尚未运行物理仿真。

下一轮构建新个人包：

```bash
cd ~/hz_sim_ws && colcon build --symlink-install --packages-select hz_hunter_sim
```

第一条成功后从安装目录展开模型，验证资源已正确安装并检查格式：

```bash
source ~/hz_sim_ws/install/setup.bash && xacro ~/hz_sim_ws/install/hz_hunter_sim/share/hz_hunter_sim/urdf/hunter_core.urdf.xacro -o ~/hz_sim_ws/reports/hz_hunter_core.urdf && ign sdf -k ~/hz_sim_ws/reports/hz_hunter_core.urdf
```

用户已回传骨架包构建成功（2.34秒）与安装模型Valid，实际生成XML与预检查语义相同。hunter_base硬件驱动、导航启动文件和共享旧地图均未导入个人执行工作区。

已运行一个无运动发布器的短时ROS诊断节点，证实域73、CycloneDDS实际选择127.0.0.1，随后销毁并退出。拒绝条件与日志解析测试4项通过。此证据仅覆盖该ROS上下文的配置与实际接口选择，不代表OS级网络防火墙或Gazebo Transport网络沙箱已实现。

暂停预览场景与入口已准备并通过离线格式/参数检查，当前尚未打开窗口。下一轮个人WSL只运行：

```bash
bash /mnt/f/rob-memory/sim/tools/start_paused_scene.bash
```

入口自行加载个人环境、核对预览文件，执行并退出短时ROS通信诊断，再打开Gazebo。初始暂停，场景只有平地、灰色简化车体和四个黑色轮子，没有车体控制插件、ROS桥接或底盘驱动。用户截图已确认初次窗口和模型显示成功；终端持续输出Gazebo日志属于正常启动过程。

场景说明见 `F:\rob-memory\sim\scenes\README.md`。下一轮只在当前Gazebo点击播放，运行约10秒再暂停，回传车体是否平稳及有无翻倒、穿地或明显漂移。此操作只推进电脑仿真，实车驱动和控制桥接未接入。物理接触质量、控制、传感器、渲染帧率及个人新地图场景仍待验证。

首批机器人资料见 [robot_assets](../robot_assets/README.md)，当前进度见[执行记录](../outputs/hunter_sim_execution_20261012/task_plan.md)。未经用户明确下令，禁止提供或执行可能使实车移动的命令；本环境准备阶段不启动底盘或导航。
