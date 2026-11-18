#!/usr/bin/env bash
# Same world, same server: how fast does it run with the ROS bridge attached versus
# with it stopped?  The bridge subscribes to /scan, and every published scan costs a
# render readback, so this is the first thing to rule out.
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1

factor() {
    timeout 5 ign topic -e -t /world/hz_lab_2d/stats 2>/dev/null \
        | grep -o 'real_time_factor: [0-9.]*' | tail -1
}

echo "with bridge:    $(factor)"
pkill_bridge_pid=$(cat /tmp/lab_drive_stack/bridge.pid 2>/dev/null || true)
if [ -n "${pkill_bridge_pid:-}" ] && [ -d "/proc/$pkill_bridge_pid" ]; then
    kill -TERM "$pkill_bridge_pid" 2>/dev/null || true
    sleep 3
fi
echo "bridge stopped: $(factor)"
