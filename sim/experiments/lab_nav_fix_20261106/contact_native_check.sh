#!/usr/bin/env bash
# Does the vehicle move at all, and does the contact sensor fire, when the command is
# injected straight into Gazebo (no ROS bridge in the loop)?
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1

TOPIC='/world/hz_lab_2d/model/hz_hunter_full/link/base_link/sensor/chassis_contact/contact'

echo "== server log: plugin and contact mentions"
grep -iE "ackermann|contact|error|warn" /tmp/lab_contact_stack/server.log | tail -12

echo
echo "== clock sample"
timeout 3 ign topic -e -t /clock 2>/dev/null | head -6

echo
echo "== publish a gz-native velocity for 6 s"
( ign topic -t /hz_sim/lab/cmd_vel -m ignition.msgs.Twist -p 'linear: {x: 0.2}' >/dev/null 2>&1 & echo $! > /tmp/gzpub.pid )
sleep 1
timeout 5 ign topic -e -t "$TOPIC" > /tmp/gz_contact2.log 2>&1 || true
kill "$(cat /tmp/gzpub.pid)" 2>/dev/null || true
echo "contact bytes: $(wc -c < /tmp/gz_contact2.log)"

echo
echo "== pose after"
timeout 3 ign topic -e -t /world/hz_lab_2d/pose/info 2>/dev/null | grep -A3 'name: "hz_hunter_full"' | head -6
