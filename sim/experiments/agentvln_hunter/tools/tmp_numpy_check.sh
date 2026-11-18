#!/usr/bin/env bash
source /opt/ros/humble/setup.bash
echo "== default"
python3 -c "import numpy; print(numpy.__version__, numpy.__file__)"
echo "== PYTHONNOUSERSITE=1"
PYTHONNOUSERSITE=1 python3 -c "import numpy; print(numpy.__version__, numpy.__file__)"
echo "== cv_bridge import default"
python3 -c "import cv_bridge; print('ok')" 2>&1 | tail -2
echo "== cv_bridge import no-user-site"
PYTHONNOUSERSITE=1 python3 -c "import cv_bridge; print('ok')" 2>&1 | tail -2
