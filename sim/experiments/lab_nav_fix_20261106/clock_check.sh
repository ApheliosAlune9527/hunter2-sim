#!/usr/bin/env bash
# Is the world actually advancing?  Two clock samples three seconds apart, plus the
# pause state as Gazebo itself reports it.
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1

sim_sec() {
    timeout 2 ign topic -e -t /clock 2>/dev/null | grep -A2 '^sim {' | sed -n '2p' | tr -dc '0-9'
}

a=$(sim_sec)
sleep 3
b=$(sim_sec)
echo "sim seconds: $a -> $b"
[ -n "$a" ] && [ -n "$b" ] && echo "advanced: $((b - a)) s in 3 s wall"

echo "== server log tail"
tail -6 /tmp/lab_contact_stack/server.log
