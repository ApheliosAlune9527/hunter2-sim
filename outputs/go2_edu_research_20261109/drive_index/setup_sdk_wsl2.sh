#!/bin/bash
set -x
export http_proxy=http://172.24.0.1:7897
export https_proxy=http://172.24.0.1:7897
cd ~ || exit 1
curl -sS -m 120 https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py || exit 1
python3 /tmp/get-pip.py --user 2>&1 | tail -3
export PATH=$HOME/.local/bin:$PATH
python3 -m pip install --user cyclonedds==0.10.2 2>&1 | tail -5
python3 -c "import cyclonedds; print('cyclonedds ok', cyclonedds.__version__)" 2>&1 | tail -3
