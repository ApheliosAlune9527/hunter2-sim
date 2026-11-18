#!/usr/bin/env bash
# Drive into the wall by hand and watch the gz-side contact topic directly, so the
# bridge cannot be blamed for a message that never existed.
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
source /opt/ros/humble/setup.bash

TOPIC='/world/hz_lab_2d/model/hz_hunter_full/link/base_link/sensor/chassis_contact/contact'

echo "== teleport"
ign service -s /world/hz_lab_2d/set_pose --reqtype ignition.msgs.Pose --reptype ignition.msgs.Boolean \
  --timeout 5000 --req 'name: "hz_hunter_full", position: {x: 0.985, y: 3.135, z: 0.165}, orientation: {x: 0, y: 0, z: 0, w: 1}'
sleep 2

echo "== pose before"
python3 -B /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/read_pose_simple.py

( timeout 8 ign topic -e -t "$TOPIC" > /tmp/contact_watch.log 2>&1 & echo $! > /tmp/contact_watch.pid )
timeout 7 ros2 topic pub /cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 0.15}, angular: {}}' -r 10 >/dev/null 2>&1 || true
sleep 1

echo "== contact log bytes: $(wc -c < /tmp/contact_watch.log)"
head -c 400 /tmp/contact_watch.log

echo
echo "== pose after"
python3 -B /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/read_pose_simple.py
