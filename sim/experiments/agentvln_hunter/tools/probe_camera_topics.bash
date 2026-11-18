#!/usr/bin/env bash
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash || exit 1
echo "--- camera topic rates ---"
for t in /hz_sim/agentvln/camera/image /hz_sim/agentvln/camera/depth_image /hz_sim/agentvln/camera/camera_info; do
  echo "TOPIC $t"
  timeout 6 ros2 topic hz "$t" --window 10 2>&1 | tail -3
done
echo "--- camera info once ---"
timeout 8 ros2 topic echo /hz_sim/agentvln/camera/camera_info --once 2>&1 | head -40
echo "--- image header once ---"
timeout 8 ros2 topic echo /hz_sim/agentvln/camera/image --once --field header 2>&1
echo "--- depth header once ---"
timeout 8 ros2 topic echo /hz_sim/agentvln/camera/depth_image --once --field header 2>&1
echo "--- amcl pose once ---"
timeout 8 ros2 topic echo /amcl_pose --once --field pose.pose 2>&1
