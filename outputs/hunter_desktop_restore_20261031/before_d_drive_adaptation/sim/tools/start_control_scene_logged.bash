#!/usr/bin/env bash
set -eo pipefail

if [[ $# -gt 1 ]] || [[ $# -eq 1 && "$1" != '--check' ]]; then
  printf '错误：完整模型日志入口只接受无参数或 --check。\n' >&2
  exit 1
fi

if [[ "${1:-}" == '--check' ]]; then
  exec /bin/bash /mnt/f/rob-memory/sim/tools/start_hunter_full_scene.bash --check
fi
exec /bin/bash /mnt/f/rob-memory/sim/tools/start_hunter_full_scene.bash
