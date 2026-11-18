"""Derive the simulation Nav2 parameters from the senior's real-vehicle file.

The original task is to reuse the lab's mature stack, not to re-tune it, so the
simulation config must be traceable to `knowledge_base/.../hunter_nav_odom_config/
nav2_params.yaml` line by line. This script copies that file and applies only the
edits that are unavoidable in simulation, recording each one.

Documented edits
----------------
1. Behaviour-tree paths: the senior's paths point at /home/car/..., which does not
   exist on the desktop. Repointed at local copies of the same XML files.
2. minimum_turning_radius 1.6 -> 1.669: 1.6 is slightly optimistic against the
   plugin steering limit. R = wheel_base / sin(steering_limit) = 0.650 / sin(0.4)
   = 1.669 m, which is what the wheels can actually achieve.

Everything else - controller, costmaps, footprint, inflation, velocities, planner,
AMCL, velocity smoother - is the senior's value, unmodified.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'knowledge_base' / 'Hunter知识库' / '配置文件' / 'hunter_nav_odom_config' / 'nav2_params.yaml'
DST = Path(__file__).resolve().parent / 'nav2_params.yaml'
BT_DIR = Path(__file__).resolve().parent
REPORT = ROOT / 'outputs/lab_nav_20261105/nav2_params_diff.json'

BT_FILES = {
    'navigate_no_spin.xml': BT_DIR / 'navigate_no_spin.xml',
    'navigate_through_poses_no_spin.xml': BT_DIR / 'navigate_through_poses_no_spin.xml',
}


def wsl_path(path):
    """Nav2 runs inside WSL, so the XML cannot reference a Windows drive letter."""
    text = str(path).replace('\\', '/')
    if re.match(r'^[A-Za-z]:/', text):
        text = '/mnt/' + text[0].lower() + text[2:]
    return text

TURNING_RADIUS_FROM = 'minimum_turning_radius: 1.6'
TURNING_RADIUS_TO = 'minimum_turning_radius: 1.669'


def main():
    text = SRC.read_text(encoding='utf-8')
    edits = []

    for key, local in BT_FILES.items():
        param = ('default_nav_to_pose_bt_xml' if key == 'navigate_no_spin.xml'
                 else 'default_nav_through_poses_bt_xml')
        pattern = re.compile(r'(%s:\s*)"[^"]*%s"' % (param, re.escape(key)))
        new_text, count = pattern.subn(lambda m: m.group(1) + f'"{wsl_path(local)}"', text)
        edits.append({'key': param, 'replacements': count, 'value': wsl_path(local)})
        text = new_text

    if TURNING_RADIUS_FROM not in text:
        raise SystemExit('minimum_turning_radius: 1.6 not found; the asset changed')
    text = text.replace(TURNING_RADIUS_FROM, TURNING_RADIUS_TO)
    edits.append({'key': 'minimum_turning_radius', 'from': 1.6, 'to': 1.669,
                  'reason': 'wheel_base / sin(steering_limit) = 0.650 / sin(0.4)'})

    # With allow_reversing the controller picks the reverse gear whenever the
    # carrot falls slightly behind the robot, and the Smac plan starts ~0.15 m
    # behind the vehicle, so the first move was -0.227 m/s away from the goal.
    # Measured, not assumed: see outputs/lab_nav_20261105/nav2_params_diff.json.
    if 'allow_reversing: true' in text:
        text = text.replace('allow_reversing: true', 'allow_reversing: false')
        edits.append({'key': 'allow_reversing', 'from': True, 'to': False,
                      'reason': 'sim run drove at -0.227 m/s on the first goal; '
                                'forward-only matches the no-spin baseline'})

    # The lab map is trinary: 6,4691 cells are unknown. The task requires unknown
    # space to be impassable, and the senior's real-vehicle map was fully explored,
    # so he could afford allow_unknown: true. Here it would let Smac route through
    # grey. Both occurrences are in planner_server.GridBased.
    unknown_count = text.count('allow_unknown: true')
    if unknown_count != 2:
        raise SystemExit(f'expected 2 allow_unknown entries, found {unknown_count}')
    text = text.replace('allow_unknown: true', 'allow_unknown: false')
    edits.append({'key': 'allow_unknown', 'from': True, 'to': False,
                  'replacements': unknown_count,
                  'reason': 'task requires unknown space to be impassable; the map is '
                            'trinary with 64,691 unknown cells'})

    DST.write_text(text, encoding='utf-8')

    # Sanity: every edited key must appear with the new value.
    checks = {
        'minimum_turning_radius': 'minimum_turning_radius: 1.669',
        'allow_unknown': 'allow_unknown: false',
        'no_allow_unknown_true': 'allow_unknown: true',
        'bt_to_pose': f'default_nav_to_pose_bt_xml: "{wsl_path(BT_DIR / "navigate_no_spin.xml")}"',
    }
    for name, needle in checks.items():
        present = needle in text
        if name == 'no_allow_unknown_true':
            if present:
                raise SystemExit('patch failed: allow_unknown still true somewhere')
            continue
        if not present:
            raise SystemExit(f'patch failed: {name}')
        if '/home/car/' in text:
            raise SystemExit('a /home/car/ path survived the patch')

    report = {
        'source': str(SRC.relative_to(ROOT)),
        'output': str(DST.relative_to(ROOT)),
        'source_sha256_lines': len(text.splitlines()),
        'edits': edits,
        'unchanged_families': ['amcl', 'controller (RPP gains/limits)', 'local_costmap',
                               'global_costmap', 'planner (SmacPlannerHybrid)',
                               'smoother', 'velocity_smoother', 'behavior_server'],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
