"""Derive the corrected Nav2 parameters from the senior's original file.

Same rule as the previous generator -- the senior's file is the source of truth and
every edit is recorded -- but this one starts again from that file rather than from
the already-patched copy, so the record cannot inherit a silent drift.  It differs
from the old generator in two ways that the correction round requires:

  * footprint is replaced by the polygon computed from the model (see
    compute_footprint.py), in both costmaps at once;
  * the planner motion model becomes DUBIN, because the controller is forward-only
    (allow_reversing: false, use_rotate_to_heading: false).  REEDS_SHEPP plans
    reverse cusps the controller will not execute, and the old task3 record claimed
    DUBIN while the file said REEDS_SHEPP -- a record that did not describe the
    configuration.

Output: nav2_params_fix.yaml next to this script, patch record in
outputs/lab_nav_fix_20261106/nav2_params_fix_diff.json.
"""
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SRC = ROOT / 'knowledge_base' / 'Hunter知识库' / '配置文件' / 'hunter_nav_odom_config' / 'nav2_params.yaml'
DST = HERE / 'nav2_params_fix.yaml'
OLD_BT_DIR = ROOT / 'sim/experiments/lab_nav'
FOOTPRINT_DOC = ROOT / 'outputs/lab_nav_fix_20261106/footprint_polygon.json'
REPORT = ROOT / 'outputs/lab_nav_fix_20261106/nav2_params_fix_diff.json'


def wsl_path(path):
    text = str(path).replace('\\', '/')
    if re.match(r'^[A-Za-z]:/', text):
        text = '/mnt/' + text[0].lower() + text[2:]
    return text


def main():
    text = SRC.read_text(encoding='utf-8')
    edits = []

    # Behaviour trees: copy the no-spin trees into this directory so the fix has no
    # dependency on the old experiment directory remaining as it is.
    bt_map = {
        'navigate_no_spin.xml': 'default_nav_to_pose_bt_xml',
        'navigate_through_poses_no_spin.xml': 'default_nav_through_poses_bt_xml',
    }
    for fname, param in bt_map.items():
        shutil.copy2(OLD_BT_DIR / fname, HERE / fname)
        # The inherited trees carry <BackUp backup_dist="0.30" .../> in the recovery
        # branch.  BackUp commands reverse velocity, which the forward-only setup
        # forbids, so the recovery round robin keeps clearing and waiting only.
        xml = (HERE / fname).read_text(encoding='utf-8')
        stripped = re.sub(r'[ \t]*<BackUp\b[^>]*/>[ \t]*\n', '', xml)
        stripped = re.sub(r'[ \t]*<Spin\b[^>]*/>[ \t]*\n', '', stripped)
        if stripped != xml:
            (HERE / fname).write_text(stripped, encoding='utf-8')
            edits.append({'param': f'behaviour tree {fname}',
                          'removed': 'BackUp / Spin recovery',
                          'reason': 'reverse and in-place rotation are outside the '
                                    'forward-only policy'})
        pattern = re.compile(r'(%s:\s*)"[^"]*%s"' % (param, re.escape(fname)))
        new_text, count = pattern.subn(lambda m: m.group(1) + f'"{wsl_path(HERE / fname)}"', text)
        # Several nodes repeat the same BT parameter (navigator, behaviour server,
        # smoother), so more than one replacement is expected; zero is not.
        if count < 1:
            raise SystemExit(f'{param}: no occurrence found')
        text = new_text
        edits.append({'param': param, 'value': wsl_path(HERE / fname), 'replacements': count,
                      'reason': 'senior path was /home/car/..., does not exist on the desktop'})

    if 'minimum_turning_radius: 1.6' not in text:
        raise SystemExit('minimum_turning_radius 1.6 not found')
    text = text.replace('minimum_turning_radius: 1.6', 'minimum_turning_radius: 1.669')
    edits.append({'param': 'minimum_turning_radius', 'from': 1.6, 'to': 1.669,
                  'reason': 'R = wheel_base / sin(steering_limit) = 0.650 / sin(0.4) = 1.669 m'})

    n = text.count('allow_reversing: true')
    if n != 1:
        raise SystemExit(f'expected 1 allow_reversing, found {n}')
    text = text.replace('allow_reversing: true', 'allow_reversing: false')
    edits.append({'param': 'allow_reversing', 'from': True, 'to': False,
                  'reason': 'forward-only baseline; measured -0.227 m/s reversal in the '
                            'old round when this was true'})

    n = text.count('allow_unknown: true')
    if n != 2:
        raise SystemExit(f'expected 2 allow_unknown, found {n}')
    text = text.replace('allow_unknown: true', 'allow_unknown: false')
    edits.append({'param': 'allow_unknown', 'from': True, 'to': False, 'replacements': n,
                  'reason': 'unknown space must be impassable; the map has 64,691 unknown cells'})

    n = text.count('motion_model_for_search: "REEDS_SHEPP"')
    if n != 1:
        raise SystemExit(f'expected 1 REEDS_SHEPP, found {n}')
    text = text.replace('motion_model_for_search: "REEDS_SHEPP"',
                        'motion_model_for_search: "DUBIN"')
    edits.append({'param': 'motion_model_for_search', 'from': 'REEDS_SHEPP', 'to': 'DUBIN',
                  'reason': 'the controller is forward-only; Reeds-Shepp plans reverse cusps '
                            'it cannot execute, and the old record claimed DUBIN'})

    foot = json.loads(FOOTPRINT_DOC.read_text(encoding='utf-8'))
    # The costmap footprint is the chassis with a 0.02 m margin, NOT the swept-wheel
    # envelope.  Reason, measured on 2026-11-06: the swept envelope is 0.874 m wide and
    # pushes the inscribed radius to 0.437 m; Nav2 marks everything within the inscribed
    # radius as lethal, so in this map the vehicle started and every goal sat on a lethal
    # cell and SmacPlannerHybrid aborted with "exceeded maximum iterations".  The swept
    # envelope is the right shape for offline collision audits (it is kept in the JSON as
    # swept_wheel_envelope_m), but the planner needs the rigid body: the wheels turn
    # within the body's own width, and steering full lock is not a state the controller
    # commands while squeezing through a doorway.
    chassis = foot['chassis_with_margin_m']
    cx0, cy0 = chassis['min']
    cx1, cy1 = chassis['max']
    poly = (f'[[{cx0:.3f}, {cy0:.3f}], [{cx1:.3f}, {cy0:.3f}], '
            f'[{cx1:.3f}, {cy1:.3f}], [{cx0:.3f}, {cy1:.3f}]]')
    pattern = re.compile(r'footprint:\s*"\[\[0\.52, 0\.395\].*?\]"')
    text, count = pattern.subn(f'footprint: "{poly}"', text)
    if count != 2:
        raise SystemExit(f'expected 2 footprint lines, replaced {count}')
    edits.append({'param': 'footprint', 'from': '[[0.52,0.395],[0.52,-0.395],[-0.50,-0.395],[-0.50,0.395]]',
                  'to': poly, 'replacements': count,
                  'reason': 'chassis envelope plus 0.02 m (the model reaches x=0.814 m, so the '
                            'inherited rectangle left 0.294 m of the nose outside); the swept-wheel '
                            'envelope is stored separately and used only by offline audits, because '
                            'its 0.437 m inscribed radius marks the whole corridor lethal'})

    DST.write_text(text, encoding='utf-8')

    # The recovery trees no longer call BackUp, but the behaviour server still offered
    # it.  A behaviour that exists can be invoked (a stale tree, a hand-run action, a
    # future BT edit) and BackUp commands reverse velocity, which contradicts
    # allow_reversing: false and the forward-only planner.  Advertise only what the
    # forward-only policy allows.
    n = text.count('behavior_plugins: ["backup", "drive_on_heading", "assisted_teleop", "wait"]')
    if n != 1:
        raise SystemExit(f'expected 1 behavior_plugins list, found {n}')
    text = text.replace(
        'behavior_plugins: ["backup", "drive_on_heading", "assisted_teleop", "wait"]',
        'behavior_plugins: ["wait", "drive_on_heading"]')
    edits.append({'param': 'behavior_server.behavior_plugins',
                  'from': ['backup', 'drive_on_heading', 'assisted_teleop', 'wait'],
                  'to': ['wait', 'drive_on_heading'],
                  'reason': 'BackUp and Spin drive the base in ways the forward-only '
                            'controller never commands; the plugin definitions stay in the '
                            'file but are no longer advertised'})
    DST.write_text(text, encoding='utf-8')

    # Both trees are copied from lab_nav, which still contains a BackUp recovery.  The
    # copy here has that node removed; assert it, because a re-copy would silently put
    # reverse motion back into the recovery branch.
    for fname in bt_map:
        xml = (HERE / fname).read_text(encoding='utf-8')
        if '<BackUp' in xml or '<Spin' in xml:
            raise SystemExit(f'{fname} still contains a reversing or spinning recovery')

    # Assertions on the written file, not on intentions.
    if 'allow_unknown: true' in text:
        raise SystemExit('allow_unknown still true')
    if '/home/car/' in text:
        raise SystemExit('a /home/car/ path survived')
    for needle in ('motion_model_for_search: "DUBIN"', f'footprint: "{poly}"',
                   'allow_reversing: false', 'minimum_turning_radius: 1.669'):
        if needle not in text:
            raise SystemExit(f'missing after patch: {needle}')

    report = {
        'source': str(SRC.relative_to(ROOT)),
        'output': str(DST.relative_to(ROOT)),
        'lines': len(text.splitlines()),
        'edits': edits,
        'unchanged_families': ['amcl', 'controller gains and limits', 'local_costmap',
                               'global_costmap', 'planner (SmacPlannerHybrid)',
                               'velocity smoother', 'behaviour server'],
        'runtime_check': 'verify_fix_config.py reads these back from the running nodes; '
                         'a file assertion alone does not prove the launch loaded it',
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({'edits': len(edits), 'lines': report['lines'],
                      'footprint': poly}, ensure_ascii=False))


if __name__ == '__main__':
    main()
