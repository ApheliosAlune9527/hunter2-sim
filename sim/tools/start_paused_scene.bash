#!/usr/bin/env bash
set -eo pipefail

if [[ $# -gt 1 ]] || [[ $# -eq 1 && "$1" != '--check' ]]; then
  printf '错误：此预览入口不接受额外的仿真启动参数。\n' >&2
  exit 1
fi

source /mnt/d/rob-memory/wsl/hz_sim_env.bash
set -u

scene_dir=/mnt/d/rob-memory/sim/scenes
# Desktop adaptation: the _d copy carries the baseline digests with /mnt/d
# paths; hz_hunter_preview.sha256 keeps its 2026-10-21 bytes as evidence.
sha256sum --quiet --check "$scene_dir/hz_hunter_preview_d.sha256"

# Inspect files and environment before starting any simulator process.
python3 -B - <<'PY'
import os
from pathlib import Path
import pwd
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, '/mnt/d/rob-memory/sim/tools')
from check_ros_isolation import validate_environment
validate_environment(
    os.environ, Path('/proc/sys/kernel/osrelease').read_text(),
    pwd.getpwuid(os.getuid()).pw_name,
)

root = Path('/mnt/d/rob-memory/sim/scenes')
world = ET.parse(root / 'hz_hunter_preview.sdf').getroot().find('world')
allowed = {
    ('ignition-gazebo-physics-system', 'ignition::gazebo::systems::Physics'),
    ('ignition-gazebo-user-commands-system', 'ignition::gazebo::systems::UserCommands'),
    ('ignition-gazebo-scene-broadcaster-system', 'ignition::gazebo::systems::SceneBroadcaster'),
}
plugins = world.findall('.//plugin')
actual = {(p.get('filename'), p.get('name')) for p in plugins}
if len(plugins) != 3 or actual != allowed:
    raise SystemExit('场景检查失败：存在非预期插件')
if world.findall('.//include') or world.findall('.//uri'):
    raise SystemExit('场景检查失败：存在外部模型或资源引用')
models = world.findall('model')
if len(models) != 2 or {m.get('name') for m in models} != {'ground_plane', 'hz_hunter_core'}:
    raise SystemExit('场景检查失败：模型列表不符合预览要求')
vehicle = next(m for m in models if m.get('name') == 'hz_hunter_core')
if len(vehicle.findall('link')) != 7 or len(vehicle.findall('joint')) != 6:
    raise SystemExit('场景检查失败：车体结构与已检查骨架不符')

gui_text = (root / 'hz_hunter_preview_gui.config').read_text()
gui_text = re.sub(r'^\s*<\?xml[^?]*\?>', '', gui_text, count=1)
gui = ET.fromstring('<hz_gui>' + gui_text + '</hz_gui>')
if gui.findtext("plugin[@filename='WorldControl']/start_paused") != 'true':
    raise SystemExit('场景检查失败：GUI未设置初始暂停')
PY

if [[ "${1:-}" == '--check' ]]; then
  printf '暂停场景文件检查通过；未启动 ROS 检查节点或仿真进程。\n'
  exit 0
fi

# This short-lived context has no motion publisher and is destroyed on exit.
python3 -B /mnt/d/rob-memory/sim/tools/check_ros_isolation.py

printf '正在打开个人 Gazebo 模型预览，初始状态为暂停。\n'
printf '场景仅含平地和简化车体，没有底盘驱动、ROS 桥接或运动控制器。\n'
# Do not forward arguments or add -r: the server and GUI start paused.
exec /usr/bin/ign gazebo -v 3 \
  --gui-config "$scene_dir/hz_hunter_preview_gui.config" \
  "$scene_dir/hz_hunter_preview.sdf"
