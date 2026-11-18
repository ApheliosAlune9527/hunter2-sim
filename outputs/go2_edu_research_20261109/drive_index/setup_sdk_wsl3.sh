#!/bin/bash
set -x
export http_proxy=http://172.24.0.1:7897
export https_proxy=http://172.24.0.1:7897
export PATH=$HOME/.local/bin:$PATH
cd ~ || exit 1
if [ ! -d ~/unitree_sdk2_python ]; then
  git clone --depth 1 https://github.com/unitreerobotics/unitree_sdk2_python.git || exit 1
fi
cd ~/unitree_sdk2_python || exit 1
python3 -m pip install --user -e . 2>&1 | tail -8
python3 -c "import unitree_sdk2py; print('sdk import ok')" 2>&1 | tail -3
