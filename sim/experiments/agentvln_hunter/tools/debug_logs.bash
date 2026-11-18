#!/usr/bin/env bash
LOG=/tmp/agentvln_step1/camera/nav2.log
echo "--- all message-filter lines ---"
grep -n 'Message Filter' "$LOG" | tail -20
echo "--- last amcl lines ---"
grep -n 'amcl-2' "$LOG" | tail -30
echo "--- map odom mentions ---"
grep -n -E 'map.*odom|odom.*map' "$LOG" | tail -20
echo "--- log size ---"
stat -c '%y %s' "$LOG"
