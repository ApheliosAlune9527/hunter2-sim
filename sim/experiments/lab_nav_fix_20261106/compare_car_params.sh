#!/usr/bin/env bash
# Compare the car's running Nav2 parameters with the parameters verified in
# simulation.  The simulation file was derived from the same upstream file, so
# the diff is exactly "what we changed and the car has not".
set -u

CAR=/mnt/d/rob-memory/inbox_car_20261108/hz_nav_ws_config_20261108
SIM=/mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/nav2_params_fix.yaml

echo "=== diff (car -> verified sim) ==="
diff -u "$CAR/config/nav2_params.yaml" "$SIM" || true

echo
echo "=== navigation_launch.py: velocity path and time ==="
grep -nE "cmd_vel|blocked|remappings|use_sim_time|velocity_smoother" "$CAR/launch/navigation_launch.py" | head -30

echo
echo "=== amcl.yaml ==="
grep -nE "set_initial_pose|initial_pose|always_reset|update_min|laser_|max_beams|scan_topic" "$CAR/config/amcl.yaml"
