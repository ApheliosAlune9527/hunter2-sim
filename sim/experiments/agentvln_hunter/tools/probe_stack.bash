#!/usr/bin/env bash
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash || exit 1
echo "ENV domain=$ROS_DOMAIN_ID local=$ROS_LOCALHOST_ONLY rmw=$RMW_IMPLEMENTATION part=$IGN_PARTITION"
echo "--- topics ---"
ros2 topic list -t 2>/dev/null | sort
echo "--- scan hz ---"
timeout 8 ros2 topic hz /scan --window 20 2>&1 | tail -6
echo "--- odom hz ---"
timeout 5 ros2 topic hz /odom --window 50 2>&1 | tail -4
echo "--- scan header ---"
timeout 6 ros2 topic echo /scan --once --field header 2>&1
echo "--- odom header ---"
timeout 6 ros2 topic echo /odom --once --field header 2>&1
echo "--- clock once ---"
timeout 6 ros2 topic echo /clock --once 2>&1
