#!/bin/bash
set -x
export http_proxy=http://172.24.0.1:7897
export https_proxy=http://172.24.0.1:7897
cd ~ || exit 1
python3 -m venv ~/go2_env || exit 1
source ~/go2_env/bin/activate
python -m pip install -U pip wheel 2>&1 | tail -3
python -m pip install cyclonedds==0.10.2 2>&1 | tail -5
if [ ! -d ~/unitree_sdk2_python ]; then
  git clone --depth 1 https://github.com/unitreerobotics/unitree_sdk2_python.git
fi
cd ~/unitree_sdk2_python || exit 1
CYCLONEDDS_HOME=/opt/ros/humble python -m pip install -e . 2>&1 | tail -8
python -c "import unitree_sdk2py, cyclonedds; print('import ok')" 2>&1 | tail -3
