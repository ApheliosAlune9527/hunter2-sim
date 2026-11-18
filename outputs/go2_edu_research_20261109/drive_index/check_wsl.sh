#!/bin/bash
set +e
source /opt/ros/humble/setup.bash 2>/dev/null
echo "ROS_DISTRO=${ROS_DISTRO:-none}"
echo "pkgs=$(ros2 pkg list 2>/dev/null | wc -l)"
python3 -c 'import cyclonedds, sys; print("cyclonedds", getattr(cyclonedds, "__version__", "?"))' 2>&1 | head -3
echo "--- dirs ---"
ls -d ~/unitree* ~/hz_* 2>/dev/null
echo "--- proxy test ---"
curl -sS -m 8 -x http://172.24.0.1:7897 -o /dev/null -w 'github %{http_code}\n' https://github.com 2>&1 | tail -1
curl -sS -m 8 -o /dev/null -w 'direct %{http_code}\n' https://pypi.org 2>&1 | tail -1
echo "--- apt cyclonedds ---"
dpkg -l | grep -i cyclonedds | head -5
