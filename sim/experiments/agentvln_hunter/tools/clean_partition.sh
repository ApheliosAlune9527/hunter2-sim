#!/usr/bin/env bash
# Kill only the processes that belong to one Gazebo partition.
#   bash clean_partition.sh [partition] [dry]
# Default partition is the lab navigation stack; the reverse-dock experiment
# uses hz_agentvln_reverse_* and is never touched.
set -u
PART=${1:-hz_sim_aphelios_73}
DRY=${2:-}
found=0
for p in $(pgrep -f "ign|parameter_bridge|odom_tf|run_nav2|gz" 2>/dev/null); do
  [ -r "/proc/$p/environ" ] || continue
  if grep -aq "IGN_PARTITION=$PART" "/proc/$p/environ" 2>/dev/null; then
    found=$((found + 1))
    cmd=$(tr "\0" " " < "/proc/$p/cmdline" | cut -c1-80)
    if [ "$DRY" = dry ]; then
      echo "would kill $p  $cmd"
    else
      kill "$p" 2>/dev/null && echo "killed $p  $cmd"
    fi
  fi
done
echo "matched=$found partition=$PART"
