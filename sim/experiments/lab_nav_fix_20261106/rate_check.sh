#!/usr/bin/env bash
# How fast is this world actually running, and what is the server doing with the CPU?
# The ratio is measured over a window: sim seconds from /clock, wall seconds from date.
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1

read_sim() {
    timeout 2 ign topic -e -t /clock 2>/dev/null | awk '/^sim \{/{f=1} f&&/sec:/{print $2; exit}'
}

a=$(read_sim); ta=$(date +%s.%N)
sleep 5
b=$(read_sim); tb=$(date +%s.%N)

awk -v a="$a" -v b="$b" -v ta="$ta" -v tb="$tb" 'BEGIN{
  ds=b-a; dt=tb-ta;
  printf "sim %.3f -> %.3f (%.3f s) in %.2f s wall\n", a, b, ds, dt;
  if (dt>0) printf "realtime factor %.4f\n", ds/dt;
}'

echo "== scan rate over 5 s"
timeout 5 ign topic -e -t /hz_sim/lab/scan 2>/dev/null | grep -c "ranges" || true

echo "== server cpu"
ps -o pid,pcpu,etime,args -p "$(pgrep -f 'ign gazebo server' | head -1)" 2>/dev/null || true
