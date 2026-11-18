#!/usr/bin/env bash
# Show the IGN_PARTITION / ROS domain of leftover sim processes, optionally kill matching ones.
set -u
killit=${1:-no}
for p in $(pgrep -f "ign gazebo|parameter_bridge|odom_tf.py|run_nav2_fix.launch.py"); do
  part=$(grep -a -o "IGN_PARTITION=[^ ]*" /proc/$p/environ 2>/dev/null | head -1)
  dom=$(grep -a -o "ROS_DOMAIN_ID=[0-9]*" /proc/$p/environ 2>/dev/null | head -1)
  echo "pid=$p $part $dom $(tr -d "\n" < /proc/$p/comm 2>/dev/null)"
  if [ "$killit" = kill ] && [[ "$part" == *hz_agentvln_reverse* ]]; then kill -TERM "$p" 2>/dev/null; fi
done
