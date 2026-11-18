#!/usr/bin/env bash
# Kill one pid only if its command line contains a marker given by the caller.
# Used for leftovers of stacks whose registry was overwritten before they were stopped.
marker=${1:?marker}
shift
for pid in "$@"; do
    if [ ! -d "/proc/$pid" ]; then
        echo "$pid already gone"
        continue
    fi
    cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline")
    case "$cmd" in
        *"$marker"*)
            echo "$pid matches, terminating"
            kill -TERM "$pid" 2>/dev/null || true
            ;;
        *)
            echo "$pid SKIP: ${cmd:0:70}"
            ;;
    esac
done
sleep 2
for pid in "$@"; do
    [ -d "/proc/$pid" ] && echo "$pid still alive"
done
true
