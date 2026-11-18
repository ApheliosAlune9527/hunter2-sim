#!/usr/bin/env bash
# The vehicle is against the wall; push it and watch the gz contact topic directly.
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
source /opt/ros/humble/setup.bash

TOPIC='/world/hz_lab_2d/model/hz_hunter_full/link/base_link/sensor/chassis_contact/contact'
echo "advertised:"; ign topic -l | grep -i contact

echo "== pose"; python3 -B /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/read_pose_simple.py

( timeout 6 ign topic -e -t "$TOPIC" > /tmp/contact_watch2.log 2>&1 & )
timeout 5 ros2 topic pub /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.3}, angular: {}}' -r 10 >/dev/null 2>&1 || true
sleep 1
echo "== gz contact bytes: $(wc -c < /tmp/contact_watch2.log)"
head -c 300 /tmp/contact_watch2.log
echo
echo "== pose after"; python3 -B /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/read_pose_simple.py
