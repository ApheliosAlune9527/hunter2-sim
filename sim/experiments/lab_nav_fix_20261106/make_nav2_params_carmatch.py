"""Derive a parameter file that is the car's file, not an improved version of it.

The user asked for the simulation to use the same data as the vehicle, so this
script does the opposite of make_nav2_params_fix.py: it takes the file exported
from /home/car/hz_nav_ws/config/nav2_params.yaml and changes only what cannot
travel between machines.

Two kinds of change, both listed in the diff file:
  * behaviour-tree paths -- they name /home/car/... files that do not exist here;
    the two XMLs are copied next to this script unchanged (they still contain the
    BackUp recovery the car uses).
  * absolute topic names -- the car file mixes bare names ("scan") with absolute
    ones ("/hz_nav/odom"); the bridge in this directory publishes /scan and /odom
    at the root namespace, so the absolute ones are rewritten.  Nothing else is
    touched: same footprint, same allow_unknown: true, same REEDS_SHEPP,
    same minimum_turning_radius 1.6, same allow_reversing: true, same 0.10 m/s,
    same behavior_plugins that include backup.

Every other line must be byte-identical to the car file; the script asserts it.
"""
import json
import pathlib
import shutil

HERE = pathlib.Path('/mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106')
OUT = pathlib.Path('/mnt/d/rob-memory/outputs/lab_nav_fix_20261106')
CAR_CFG = pathlib.Path('/mnt/d/rob-memory/inbox_car_20261108/hz_nav_ws_config_20261108/config')
CAR_PARAMS = CAR_CFG / 'nav2_params.yaml'
DEST = HERE / 'nav2_params_carmatch.yaml'
BT_NAV = HERE / 'navigate_no_spin_car.xml'
BT_THROUGH = HERE / 'navigate_through_poses_no_spin_car.xml'

# The two XMLs are the car's own files, copied verbatim.
for name in ('navigate_no_spin.xml', 'navigate_through_poses_no_spin.xml'):
    src = CAR_CFG / name
    dst = HERE / (name.replace('.xml', '_car.xml'))
    if src.exists():
        shutil.copyfile(src, dst)

text = CAR_PARAMS.read_text()
original = text.splitlines()

edits = []


def replace_all(old, new, why, expect_min=1):
    global text
    count = text.count(old)
    assert count >= expect_min, f'{old!r}: expected >= {expect_min}, found {count}'
    text = text.replace(old, new)
    edits.append({'old': old, 'new': new, 'occurrences': count, 'why': why})


# 1. Behaviour trees: keep the car's trees (they include BackUp), change the paths.
replace_all('default_nav_to_pose_bt_xml: "/home/car/hz_nav_ws/config/navigate_no_spin.xml"',
            f'default_nav_to_pose_bt_xml: "{BT_NAV}"',
            'same tree as the car, kept next to this file instead of /home/car')
replace_all('default_nav_through_poses_bt_xml: "/home/car/hz_nav_ws/config/navigate_through_poses_no_spin.xml"',
            f'default_nav_through_poses_bt_xml: "{BT_THROUGH}"',
            'same tree as the car, kept next to this file instead of /home/car')

# 2. Absolute topics that cannot resolve here.
replace_all('/hz_nav/odom', '/odom',
            'the bridge publishes odom at /odom; the car file names it absolutely')

DEST.write_text(text)

# Verify: every line is either unchanged or one of the rewritten ones.
after = text.splitlines()
assert len(after) == len(original), f'line count changed: {len(original)} -> {len(after)}'
changed = [(i + 1, a, b) for i, (a, b) in enumerate(zip(original, after)) if a != b]
allowed = sum(e['occurrences'] for e in edits)
assert len(changed) == allowed, f'{len(changed)} lines changed, expected {allowed}'

# The car's values that must survive, checked on the produced file.
must = {
    'footprint': '[[0.52, 0.395], [0.52, -0.395], [-0.50, -0.395], [-0.50, 0.395]]',
    'allow_unknown': 'true',
    'motion_model_for_search': 'REEDS_SHEPP',
    'minimum_turning_radius': '1.6',
    'allow_reversing': 'true',
    'desired_linear_vel': '0.10',
    'behavior_plugins': '["backup", "drive_on_heading", "assisted_teleop", "wait"]',
}
for key, value in must.items():
    line = [l.strip() for l in text.splitlines() if l.strip().startswith(key + ':')]
    assert line, f'{key} not found'
    assert any(value in l for l in line), f'{key} is not {value}: {line}'

# And the trees really do carry the recovery the parameters now allow.
assert 'BackUp' in BT_NAV.read_text(), 'car tree lost its BackUp node'

report = {
    'source': str(CAR_PARAMS),
    'output': str(DEST),
    'edits': edits,
    'lines_changed': len(changed),
    'lines_total': len(after),
    'kept_from_car': must,
    'delta_vs_car': changed,
}
(OUT / 'nav2_params_carmatch_diff.json').write_text(json.dumps(report, indent=1))
print(json.dumps({'edits': len(edits), 'lines_changed': len(changed),
                  'lines_total': len(after), 'output': str(DEST)}))
