#!/bin/bash
set -e
cd /mnt/d/rob-memory/outputs/go2_edu_research_20261109/tools || exit 1
export PATH=$HOME/.local/bin:$PATH
echo "== compile =="
python3 -m py_compile go2_status.py go2_move.py go2_record.py fake_go2.py && echo "compile ok"
echo "== move dry-run =="
python3 go2_move.py --dry-run --vx 0.2 --vy 0 --vyaw 0.1 --duration 2
echo "== sport client import =="
python3 -c "from unitree_sdk2py.go2.sport.sport_client import SportClient; print('SportClient ok')"
echo "== record against fake =="
python3 fake_go2.py --iface eth0 --domain 1 --seconds 7 > /tmp/fake2.log 2>&1 &
FAKE_PID=$!
sleep 2
python3 go2_record.py --iface eth0 --domain 1 --out /tmp/fake_rec.csv --seconds 3
wait $FAKE_PID || true
wc -l /tmp/fake_rec.csv
head -2 /tmp/fake_rec.csv
