#!/usr/bin/env bash
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash || exit 1
setsid nohup python3 -B /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/odom_tf.py --ros-args -p use_sim_time:=true > /tmp/odom_tf_debug.log 2>&1 &
echo $! > /tmp/odom_tf_debug.pid
sleep 3
echo "--- tf_static once ---"
timeout 8 ros2 topic echo /tf_static --once 2>&1
echo "--- tf once ---"
timeout 8 ros2 topic echo /tf --once 2>&1 | head -20
kill $(cat /tmp/odom_tf_debug.pid) 2>/dev/null
