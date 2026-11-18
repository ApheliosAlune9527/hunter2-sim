#!/bin/bash
cd /mnt/d/rob-memory/outputs/go2_edu_research_20261109/tools || exit 1
python3 fake_go2.py --iface eth0 --domain 1 --seconds 10 > /tmp/fake.log 2>&1 &
FAKE_PID=$!
sleep 2
python3 go2_status.py --iface eth0 --domain 1 --seconds 4
wait $FAKE_PID
echo "--- fake log ---"
cat /tmp/fake.log
