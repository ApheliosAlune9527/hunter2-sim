#!/usr/bin/env bash
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1
python3 - <<'PY'
mods = ['numpy', 'cv2', 'PIL', 'scipy', 'yaml']
for m in mods:
    try:
        mod = __import__(m)
        print(m, 'OK', getattr(mod, '__version__', ''))
    except Exception as e:
        print(m, 'FAIL', e)
PY
