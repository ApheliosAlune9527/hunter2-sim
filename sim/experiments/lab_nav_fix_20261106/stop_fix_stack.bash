#!/usr/bin/env bash
# Stop only the processes this session started.
#
# The old stop_lab_stack.bash fell back to `pkill -f <pattern>` when a PID was
# missing, which can kill anything whose command line happens to match -- another
# session's bridge, or a shell whose text contains the pattern.  This version has
# no pattern fallback at all: every process must be in the registry with its PID,
# kernel start time and command line, and the start time is what proves the PID
# was not reused by something else.
set -o pipefail

LOG_DIR=${LOG_DIR:-/tmp/lab_fix_stack}
REG="$LOG_DIR/processes.tsv"

if [ ! -f "$REG" ]; then
  echo "[stop] no registry at $REG -- nothing to stop"
  exit 0
fi

read_start_time() {
  # Field 22 of /proc/<pid>/stat is the start time in clock ticks since boot.
  awk '{print $22}' "/proc/$1/stat" 2>/dev/null
}

is_alive() {
  # A zombie still answers kill -0, so a plain liveness check reported this script's
  # own success as a failure: the process was dead, unreaped, and counted as alive.
  local state
  state=$(awk '{print $3}' "/proc/$1/stat" 2>/dev/null) || return 1
  [ -n "$state" ] || return 1
  [ "$state" != "Z" ]
}

stopped=0
skipped=0
while IFS=$'\t' read -r name pid starttime cmdline; do
  [ -z "${name:-}" ] && continue
  case "$name" in \#*) continue ;; esac
  if ! is_alive "$pid"; then
    echo "[stop] $name pid=$pid already gone"
    continue
  fi
  now_start=$(read_start_time "$pid")
  if [ "$now_start" != "$starttime" ]; then
    echo "[stop] $name pid=$pid SKIPPED: start time differs (pid reused by another process)" >&2
    skipped=$((skipped + 1))
    continue
  fi
  # The group id was recorded as the pid by setsid, so a negative pid targets the
  # whole group and nothing outside it.
  kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
  stopped=$((stopped + 1))
done < "$REG"

sleep 3

while IFS=$'\t' read -r name pid starttime cmdline; do
  [ -z "${name:-}" ] && continue
  case "$name" in \#*) continue ;; esac
  is_alive "$pid" || continue
  now_start=$(read_start_time "$pid")
  [ "$now_start" = "$starttime" ] || continue
  echo "[stop] $name pid=$pid did not exit on TERM, sending KILL" >&2
  kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null
done < "$REG"

sleep 1
alive=0
while IFS=$'\t' read -r name pid starttime cmdline; do
  [ -z "${name:-}" ] && continue
  case "$name" in \#*) continue ;; esac
  is_alive "$pid" && alive=$((alive + 1))
done < "$REG"

echo "[stop] stopped=$stopped skipped=$skipped still_alive=$alive"
[ "$alive" -eq 0 ] || exit 1
