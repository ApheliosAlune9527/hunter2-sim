#!/usr/bin/env bash
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
echo "--- odom once ---"
timeout 5 ros2 topic echo /odom --once 2>&1 | tail -25
echo "--- tf map base ---"
timeout 6 ros2 run tf2_ros tf2_echo map base_link 2>&1 | head -12
echo "--- tf map camera ---"
timeout 6 ros2 run tf2_ros tf2_echo map agentvln_camera_optical_frame 2>&1 | head -12
