#!/usr/bin/env bash
# Go2 开发环境一键安装（Ubuntu 22.04 + ROS 2 Humble）
# 用法：bash setup_go2_ubuntu.sh [--with-ros2]
# 说明：不修改网络配置、不启动任何会动机器人的程序。
set -euo pipefail

WITH_ROS2=0
[[ "${1:-}" == "--with-ros2" ]] && WITH_ROS2=1

echo "== 0. 系统检查 =="
. /etc/os-release
echo "distro: ${PRETTY_NAME}"
if [[ "${VERSION_ID}" != "22.04" ]]; then
  echo "警告：脚本按 Ubuntu 22.04 写；其他版本请手动核对 ROS 发行版。" >&2
fi
python3 --version

echo "== 1. apt 依赖 =="
sudo apt update
sudo apt install -y git python3-pip python3-dev build-essential cmake libyaml-cpp-dev
if [[ ${WITH_ROS2} -eq 1 ]]; then
  sudo apt install -y ros-humble-rmw-cyclonedds-cpp ros-humble-rosidl-generator-dds-idl
fi

echo "== 2. unitree_sdk2_python =="
cd "$HOME"
if [[ ! -d unitree_sdk2_python ]]; then
  git clone --depth 1 https://github.com/unitreerobotics/unitree_sdk2_python.git
fi
cd unitree_sdk2_python
pip3 install -e .

echo "== 3. 验证 import =="
python3 - <<'PY'
import unitree_sdk2py, cyclonedds
print("unitree_sdk2py ok")
PY

if [[ ${WITH_ROS2} -eq 1 ]]; then
  echo "== 4. unitree_ros2 =="
  cd "$HOME"
  if [[ ! -d unitree_ros2 ]]; then
    git clone https://github.com/unitreerobotics/unitree_ros2.git
  fi
  cd unitree_ros2
  source /opt/ros/humble/setup.bash
  colcon build
  echo "已编译 unitree_ros2；请编辑 setup.sh，把 NetworkInterface 改成接狗的网卡名。"
fi

cat <<'EOF'

== 完成 ==
下一步：
  1. 配置有线网卡 192.168.123.99/24（见 Go2_EDU_上手指南.md 第 4 节）
  2. ping 192.168.123.161
  3. python3 tools/go2_status.py --iface <网卡名>
  4. 第一次控速：python3 tools/go2_move.py --iface <网卡名> --stand --vx 0.1 --duration 1
EOF
