#!/usr/bin/env bash
# Second attempt at the stale stack: kill the process *group* of the Gazebo launcher
# (children do not repeat the world path in their own command line) and the bridge by
# its exact pid.  Both are checked against markers that only this stack can have.
set -u

WORLD_MARK='lab_nav_world_drive.sdf'
BRIDGE_MARK='lab_bridge_fix.yaml'

stop_group() {
    local pid=$1
    local pgid cmd
    cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline")
    case "$cmd" in
        *"$WORLD_MARK"*) ;;
        *) echo "$pid SKIP leader cmdline mismatch"; return ;;
    esac
    pgid=$(ps -o pgid= -p "$pid" | tr -d ' ')
    echo "$pid -> group $pgid"
    kill -TERM "-$pgid" 2>/dev/null || true
    sleep 3
    if ps -o pid= -g "$pgid" >/dev/null 2>&1; then
        echo "  group $pgid still alive, sending KILL"
        kill -KILL "-$pgid" 2>/dev/null || true
    fi
}

stop_pid() {
    local pid=$1
    local cmd
    [ -r "/proc/$pid/cmdline" ] || { echo "$pid already gone"; return; }
    cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline")
    case "$cmd" in
        *"$BRIDGE_MARK"*) kill -TERM "$pid" 2>/dev/null || true ;;
        *) echo "$pid SKIP bridge cmdline mismatch: ${cmd:0:60}" ;;
    esac
}

stop_group 1662
stop_pid 1740
stop_pid 1742

sleep 2
echo "--- remaining"
ps -o pid=,args= -p 1662,1664,1665,1740,1742 2>/dev/null || echo none
