car_nav_fix_20261107 —— 实车 Nav2 修正包（只含参数、地图、行为树和核对脚本）

这个包解决的是“实车那套 Nav2 参数与地图的四个已知问题”，不是新的导航算法。
里面的 nav2_params_car.yaml 是从师兄原始参数文件派生的，只改了下面六处，每处都有理由：

  1. use_sim_time: false（14 处）
     师兄那份参数里是 true。仿真里等 /clock 是对的，实车上没有 /clock，节点会一直等时间。
  2. footprint 两处改成底盘包络 + 0.02 m
     [[-0.184, -0.393], [0.834, -0.393], [0.834, 0.393], [-0.184, 0.393]]
     base_link 在后轴轮心，所以车头是 0.834 m；师兄那份前边界是 0.52 m，车头少算了 0.314 m。
  3. motion_model_for_search: REEDS_SHEPP → DUBIN
     控制器禁倒车，规划器却允许 REEDS_SHEPP 的倒车段，两者矛盾。
  4. allow_reversing: false（控制器）
     与“前进策略”一致；仿真里设 true 时车会倒着走去“到达”目标，实测过。
  5. allow_unknown: false（规划器两处）
     坐标地图里有大量未知格，原值是 true，等于允许路径穿过未知区。
  6. behavior_plugins 只留 wait 和 drive_on_heading，行为树换成不带 BackUp 的版本
     原恢复分支里有 BackUp（倒车 0.30 m），和禁倒车冲突。

地图 lab_odom_06_fix.yaml 与 2026-11-01 那张图（sha256 98bb0c9e…6ec74f0）配对，
只改了 free_thresh: 0.25 → 0.10。原值下灰色未知像素的概率是 0.196，会被加载成“空闲”，
于是整张图的未知区都变成了可通行区，allow_unknown: false 保护的是一个空集合。仿真里实测过：
改之前 /map 里 -1 的格子是 0 个，改之后是 64,691 个。

文件清单
  nav2_params_car.yaml                 实车用参数（上面六处已改）
  navigate_no_spin.xml                 到点行为树，恢复分支只有清代价地图 + 等待
  navigate_through_poses_no_spin.xml   多点行为树，同上
  lab_odom_06_fix.yaml                 地图描述（free_thresh 0.10）
  lab_odom_06.pgm                      2026-11-01 的二维图副本，与上面配对
  verify_car.py                        只读核对：文件哈希、参数取值、地图取值、ROS 包是否存在
  SHA256SUMS                           上面这些文件的校验值
  实车导航命令清单.txt                 按“终端 1、终端 2……”排好的操作步骤
  README_CAR.txt                       本文件


安装（在小车上，三行）

  mkdir -p /home/car/hz_nav_ws/nav_fix_20261107
  tar xzf /home/car/桌面/car_nav_fix_20261107_package.tar.gz -C /home/car/hz_nav_ws/nav_fix_20261107 --strip-components=1
  python3 -B /home/car/hz_nav_ws/nav_fix_20261107/verify_car.py

不覆盖、不修改师兄的 ~/hunter_nav_odom_ws 里的任何文件；我们的参数与地图放在自己的目录，
通过 nav2_bringup 的 map:= 和 params_file:= 两个参数指过去。


两个必须先弄清的前提

【一】use_robot 是什么
它是小车上预定义的别名（见知识库 configuration/launch-files.md），作用是依次 source
/opt/ros/humble、hunter2.0_ws、d435i_ws、hesai_xt32_ws、ars548_ws、robot_bringup_ws，
并 export ROS_DOMAIN_ID=88。师兄那份《建图导航.txt》每个终端都先敲它，我们照抄，不自造新环境。

【二】实车当前的参数文件到底是哪一份
知识库里导出的小车参数副本（robot_assets/hunter_from_car_20261013_qjkgbbq5/.../nav2_params.yaml）
里 use_sim_time 是 true；但记录里也写过小车上的标准启动脚本用的是 use_sim_time=false。
两种记录不一致，所以命令清单第 0 部分安排了一条只读 grep，先看实车那份到底是 true 还是 false。
如果实车那份本来就是 false，那这一项我们只是保持一致；如果是 true，那它就是实车一直没跑通
导航的一个原因，需要单独说明。


验证分三层，前两层只读

第一层（不启动任何节点）：python3 -B verify_car.py
  检查文件哈希、参数取值（DUBIN、1.669、allow_reversing、allow_unknown、footprint、
  behavior_plugins、BT 路径存在、use_sim_time 全 false）、地图 YAML 的 free_thresh/分辨率/原点、
  地图图片哈希。全部 PASS 才算文件到位。

第二层（启动但不发目标）：按命令清单第 1、2 部分起终端 1～5，然后用 ros2 param get 和
  tf2_echo 核对“运行中的节点”读到的值，而不是只看文件。重点两条：
  绿框前端要在车头前方（0.834 m 这一点可以在地图上用眼睛量）；
  global_costmap 的 allow_unknown 必须是 false。

第三层（会让车动，需你明确同意且现场有人守急停）：发一个正前方 1 米的目标，看
  Goal accepted → SUCCEEDED / ABORTED，然后取消一次、确认停稳。这一层还没做过。


还没验证的东西（不要当成通过）
  实车碰撞检测、里程计漂移、长距离导航、动态障碍；
  本包只做过“文件与参数”层面的核对（仿真环境里同一套参数跑过，实车上没有跑过完整闭环）；
  实车用的地图与仿真用的是同一张（sha256 相同），但实车传感器视野、轮胎打滑、地面平整度都不同。
