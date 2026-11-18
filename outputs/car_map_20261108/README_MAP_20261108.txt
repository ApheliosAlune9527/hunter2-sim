11 月 1 日新地图，用于实车 Nav2（2026-11-08）
==============================================
本目录只有两个文件，都是**新增**，不改动车上任何现有文件：

  lab_odom_11_01.pgm    241 x 465，0.05 m/格，sha256 98bb0c9e…6ec74f0
  lab_odom_11_01.yaml   与 pgm 同名，origin [-5.09, -4.89, 0]

两点说明
--------
1. free_thresh 用 0.196，与车上现有 lab_odom_06_nav.yaml 一致。
   这张图的灰色像素值是 205，概率 (255-205)/255 = 0.196078，所以
   free_thresh 写成 0.196 时 0.196078 > 0.196 不成立，灰色保持"未知"。
   若写成 0.25（lab_odom_06.yaml 的值），64,691 个未知格会被加载成"空闲"。
   这是在仿真里实际踩过的坑，不是理论问题。

2. 这张图与旧图**不是同一个坐标系**：
     旧 lab_odom_06     287 x 469   origin [-1.31, -15.4]
     新 lab_odom_11_01  241 x 465   origin [-5.09,  -4.89]
   同一个物理位置在两图上相差约 3.8 m。因此：
   - 初始位姿必须在 RViz 里按现场实际位置重新点，不能照抄旧坐标；
   - 任何之前记下的目标点（x, y）在新图上都不能直接用；
   - 两图几何也不是完全一致（新图外墙更闭合，旧图上部有雷达扇形噪点）。

安装（不改任何现有文件）
------------------------
在车上执行：

    cp ~/桌面/lab_odom_11_01.pgm ~/桌面/lab_odom_11_01.yaml \
       /home/car/hz_nav_ws/maps/

    ls -l /home/car/hz_nav_ws/maps/lab_odom_11_01.*

    sha256sum /home/car/hz_nav_ws/maps/lab_odom_11_01.pgm
    # 期望 98bb0c9ed71da56189d83658f9402eeb53d4bc71828981216e4dd66f86ec74f0

启动 Nav2 时只改 map:= 一个参数（其余与你现有命令完全一致）：

    ... bringup_launch.py \
        namespace:=hz_nav use_namespace:=true slam:=False \
        map:=/home/car/hz_nav_ws/maps/lab_odom_11_01.yaml \
        params_file:=/home/car/hz_nav_ws/config/nav2_params.yaml \
        use_sim_time:=false autostart:=false

回滚
----
把 map:= 换回 /home/car/hz_nav_ws/maps/lab_odom_06_nav.yaml 即可；
两个新文件删不删都不影响其他用法。

地图核对方法（可选，一条命令）
------------------------------
RViz 里 Map 显示正常、且 map 到 base_link 能查出变换，就说明 yaml 与 pgm
配对正确。若 Map 报 "Failed to load map"，多半是 pgm 与 yaml 没有放在同一
目录，或 yaml 里 image 名字与实际文件不一致。
