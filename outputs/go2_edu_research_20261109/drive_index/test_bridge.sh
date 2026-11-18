#!/bin/bash
source /opt/ros/humble/setup.bash
cd /mnt/d/rob-memory/outputs/go2_edu_research_20261109/tools || exit 1
export PYTHONPATH=$HOME/.local/lib/python3.10/site-packages:$PYTHONPATH
python3 go2_cmdvel_bridge.py --dry-run --timeout 0.5 > /tmp/bridge.log 2>&1 &
BRIDGE_PID=$!
sleep 2
timeout 3 ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2}, angular: {z: 0.1}}" > /tmp/pub.log 2>&1
sleep 2
kill -INT $BRIDGE_PID 2>/dev/null
sleep 1
kill -9 $BRIDGE_PID 2>/dev/null
echo "--- bridge log ---"
cat /tmp/bridge.log
echo "--- pub log tail ---"
tail -3 /tmp/pub.log
