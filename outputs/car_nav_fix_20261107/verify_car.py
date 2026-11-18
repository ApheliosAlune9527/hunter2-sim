#!/usr/bin/env python3
"""Read-only checks for the files that were copied onto the car.

Nothing here launches a node, publishes a topic or moves the vehicle: it only reads the
package and, if ROS is already loaded in this shell, asks which packages exist.  Every
check prints PASS or FAIL, and the script exits non-zero if anything failed, so a
terminal transcript is enough evidence for the record.
"""
import hashlib
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXPECTED_FOOTPRINT = [[-0.184, -0.393], [0.834, -0.393], [0.834, 0.393], [-0.184, 0.393]]
EXPECTED_PGM_SHA = '98bb0c9ed71da56189d83658f9402eeb53d4bc71828981216e4dd66f86ec74f0'

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  [' + detail + ']') if detail else ''))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def walk(node, key):
    """Yield every value stored under `key` anywhere in a nested dict."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                yield v
            yield from walk(v, key)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v, key)


def main():
    try:
        import yaml
    except ImportError:
        print('FAIL  PyYAML missing; install python3-yaml or run this where ROS is loaded')
        return 2

    files = ['nav2_params_car.yaml', 'navigate_no_spin.xml',
             'navigate_through_poses_no_spin.xml', 'lab_odom_06_fix.yaml',
             'lab_odom_06.pgm', 'SHA256SUMS']
    for name in files:
        check(f'{name} present', os.path.isfile(os.path.join(HERE, name)))

    sums_path = os.path.join(HERE, 'SHA256SUMS')
    if os.path.isfile(sums_path):
        bad = []
        for line in open(sums_path, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            want, name = line.split(None, 1)
            name = name.lstrip('*')
            p = os.path.join(HERE, name)
            if not os.path.isfile(p):
                bad.append(name + ' missing')
            elif sha256(p) != want:
                bad.append(name + ' differs')
        check('file hashes match SHA256SUMS', not bad, '; '.join(bad))

    params_path = os.path.join(HERE, 'nav2_params_car.yaml')
    if os.path.isfile(params_path):
        params = yaml.safe_load(open(params_path, encoding='utf-8'))
        planner = params['planner_server']['ros__parameters']['GridBased']
        follow = params['controller_server']['ros__parameters']['FollowPath']
        check('planner motion model is DUBIN',
              planner.get('motion_model_for_search') == 'DUBIN',
              str(planner.get('motion_model_for_search')))
        check('planner minimum_turning_radius is 1.669',
              abs(float(planner.get('minimum_turning_radius', 0)) - 1.669) < 1e-6,
              str(planner.get('minimum_turning_radius')))
        check('controller does not reverse', follow.get('allow_reversing') is False,
              str(follow.get('allow_reversing')))
        check('controller does not rotate in place',
              follow.get('use_rotate_to_heading') is False,
              str(follow.get('use_rotate_to_heading')))
        # The YAML has two allow_unknown keys in the same map, so a parser keeps only the
        # last one; count the text instead, which is what the node will actually read.
        text = open(params_path, encoding='utf-8').read()
        n_true = text.count('allow_unknown: true') + text.count('allow_unknown: True')
        n_false = text.count('allow_unknown: false') + text.count('allow_unknown: False')
        check('allow_unknown false everywhere (planner + costmaps)',
              n_true == 0 and n_false >= 2, f'{n_false} false, {n_true} true')
        plan = params['behavior_server']['ros__parameters'].get('behavior_plugins')
        check('behavior plugins are wait + drive_on_heading',
              plan == ['wait', 'drive_on_heading'], str(plan))
        fps = []
        for value in walk(params, 'footprint'):
            if isinstance(value, str) and value.strip().startswith('[['):
                try:
                    fps.append(json.loads(value))
                except json.JSONDecodeError:
                    pass

        def same_polygon(a, b):
            if len(a) != len(b):
                return False
            return all(abs(pa[0] - pb[0]) < 1e-6 and abs(pa[1] - pb[1]) < 1e-6
                       for pa, pb in zip(a, b))

        check('both costmap footprints equal the chassis envelope',
              len(fps) == 2 and all(same_polygon(fp, EXPECTED_FOOTPRINT) for fp in fps),
              f'{len(fps)} footprint(s)')
        n_sim_true = text.count('use_sim_time: True') + text.count('use_sim_time: true')
        n_sim_false = (text.count('use_sim_time: False')
                       + text.count('use_sim_time: false'))
        check('use_sim_time is false on hardware',
              n_sim_true == 0 and n_sim_false >= 1,
              f'{n_sim_false} false, {n_sim_true} true')
        bts = list(walk(params, 'default_nav_to_pose_bt_xml'))
        bts += list(walk(params, 'default_nav_through_poses_bt_xml'))
        # The paths point at the install directory on the car, which is where this file
        # lives too, so the shipped copy is the right thing to compare against.
        # The params carry the install path, not the path this copy happens to sit in,
        # so the check needs to know which path was promised.  It lives in INSTALL_DIR
        # next to this file; the staging copy can then be verified anywhere.
        declared = ''
        marker = os.path.join(HERE, 'INSTALL_DIR')
        if os.path.isfile(marker):
            declared = open(marker, encoding='utf-8').read().strip()
        dirs = sorted({os.path.dirname(v) for v in bts})
        check('behaviour tree paths all sit in one directory',
              bool(bts) and len(dirs) == 1, '; '.join(dirs) or 'none')
        check('behaviour tree paths match INSTALL_DIR',
              bool(declared) and dirs == [declared],
              (dirs[0] if dirs else 'none') + ' vs ' + (declared or 'no INSTALL_DIR'))
        if declared and HERE == declared:
            check('behaviour trees exist at the install path',
                  all(os.path.isfile(v) for v in bts),
                  '; '.join(sorted({os.path.basename(v) for v in bts})))
        else:
            print('SKIP  behaviour trees exist at the install path '
                  '(staging copy; unpack at INSTALL_DIR to check)')

    map_yaml = os.path.join(HERE, 'lab_odom_06_fix.yaml')
    if os.path.isfile(map_yaml):
        m = yaml.safe_load(open(map_yaml, encoding='utf-8'))
        check('map free_thresh is 0.10 (unknown stays unknown)',
              abs(float(m.get('free_thresh', 0)) - 0.10) < 1e-9, str(m.get('free_thresh')))
        check('map resolution is 0.05', abs(float(m.get('resolution', 0)) - 0.05) < 1e-9,
              str(m.get('resolution')))
        origin = m.get('origin') or [None, None, None]
        check('map origin is (-5.09, -4.89)',
              abs(float(origin[0]) + 5.09) < 1e-6 and abs(float(origin[1]) + 4.89) < 1e-6,
              str(origin))
        img = os.path.join(HERE, str(m.get('image')))
        check('map image exists next to the yaml', os.path.isfile(img), str(m.get('image')))
        if os.path.isfile(img):
            check('map image is the 2026-11-01 scan', sha256(img) == EXPECTED_PGM_SHA,
                  sha256(img)[:16])

    if subprocess.run(['bash', '-lc', 'command -v ros2'], capture_output=True).returncode == 0:
        for pkg in ('nav2_bringup', 'nav2_smac_planner',
                    'nav2_regulated_pure_pursuit_controller', 'nav2_amcl',
                    'pointcloud_to_laserscan'):
            r = subprocess.run(['bash', '-lc', f'ros2 pkg prefix {pkg}'],
                               capture_output=True, text=True)
            check(f'ROS package {pkg} present', r.returncode == 0,
                  (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else '')
        domain = os.environ.get('ROS_DOMAIN_ID', '(unset)')
        check('ROS_DOMAIN_ID is 88 on the vehicle', domain == '88', domain)
    else:
        print('SKIP  ROS checks (ros2 not on PATH in this shell)')

    failed = [r for r in results if not r[1]]
    print()
    print(f'{len(results) - len(failed)}/{len(results)} checks passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
