"""Read the running stack back and compare it with the files this round wrote.

A parameter file on disk proves nothing: the launch may load another file, a node
may never have started, or the file may have been edited after the launch.  So this
script asks the live nodes what they are actually using and compares the answer with
`nav2_params_fix.yaml` and `footprint_polygon.json`.

Checks
  * /planner_server   GridBased.motion_model_for_search == DUBIN
  * /planner_server   GridBased.minimum_turning_radius == 1.669
  * /planner_server   GridBased.allow_unknown == false
  * /controller_server FollowPath.allow_reversing == false
  * /controller_server FollowPath.use_rotate_to_heading == false
  * /global_costmap/global_costmap footprint == the computed polygon
  * /local_costmap/local_costmap   footprint == the same polygon
  * /map is 241 x 465 at 0.05 m with the recorded origin
  * /scan produces a finite beam within the wait

Exit code 0 only when every check passed.  Results go to
outputs/lab_nav_fix_20261106/verify_fix_config.json.
"""
import json
import math
import sys
import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid
from rcl_interfaces.srv import GetParameters
from rclpy.node import Node
from rclpy.qos import (QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile,
                       QoSReliabilityPolicy, qos_profile_sensor_data)
from sensor_msgs.msg import LaserScan

ROOT = Path('/mnt/d/rob-memory')
HERE = ROOT / 'sim/experiments/lab_nav_fix_20261106'
OUT = ROOT / 'outputs/lab_nav_fix_20261106'

EXPECTED = [
    ('/planner_server', 'GridBased.motion_model_for_search', 'DUBIN'),
    ('/planner_server', 'GridBased.minimum_turning_radius', 1.669),
    ('/planner_server', 'GridBased.allow_unknown', False),
    ('/controller_server', 'FollowPath.allow_reversing', False),
    ('/controller_server', 'FollowPath.use_rotate_to_heading', False),
    # The behaviour server had BackUp and Spin advertised even after the trees stopped
    # calling them; a behaviour that exists can still be invoked.
    ('/behavior_server', 'behavior_plugins', ['wait', 'drive_on_heading']),
    # Inflation lives under the inflation layer's namespace, not at costmap top level.
    ('/global_costmap/global_costmap', 'inflation_layer.inflation_radius', 0.20),
    ('/local_costmap/local_costmap', 'inflation_layer.inflation_radius', 0.20),
    # Which tree is loaded is a runtime fact, not a file fact: the parameter is what
    # bt_navigator actually parses.
    ('/bt_navigator', 'default_nav_to_pose_bt_xml', 'BT_POSE'),
    ('/bt_navigator', 'default_nav_through_poses_bt_xml', 'BT_THROUGH'),
]


def get_params(node, target, names, timeout=5.0):
    cli = node.create_client(GetParameters, f'{target}/get_parameters')
    if not cli.wait_for_service(timeout_sec=timeout):
        return None
    req = GetParameters.Request()
    req.names = names
    fut = cli.call_async(req)
    end = time.time() + timeout
    while not fut.done() and time.time() < end:
        rclpy.spin_once(node, timeout_sec=0.1)
    if not fut.done():
        return None
    return {n: v for n, v in zip(names, fut.result().values)}


# rcl_interfaces/msg/ParameterValue type constants: 1 bool, 2 integer, 3 double,
# 4 string, 5 byte array, 6 bool array, 7 integer array, 8 double array,
# 9 string array.  Getting this mapping wrong is silent: a string parameter read as
# an integer returns 0, which once made the motion model look unset while it was
# in fact DUBIN.
def as_python(value):
    kind = value.type
    if kind == 1:
        return value.bool_value
    if kind == 2:
        return value.integer_value
    if kind == 3:
        return value.double_value
    if kind == 4:
        return value.string_value
    if kind == 7:
        return list(value.integer_array_value)
    if kind == 8:
        return list(value.double_array_value)
    if kind == 9:
        return list(value.string_array_value)
    return None


def parse_polygon(text):
    if not text:
        return None
    text = text.strip().strip('"')
    return json.loads(text)


def main():
    want = json.loads((OUT / 'footprint_polygon.json').read_text(encoding='utf-8'))
    # The costmap must carry the chassis polygon, not the swept-wheel rectangle.  The
    # old receipt compared against footprint_polygon_m (the 0.457 m swept rectangle) and
    # so recorded a footprint the running stack never had.
    ch = want['chassis_with_margin_m']
    poly = [[ch['min'][0], ch['min'][1]], [ch['max'][0], ch['min'][1]],
            [ch['max'][0], ch['max'][1]], [ch['min'][0], ch['max'][1]]]
    swept = want.get('swept_wheel_envelope_m')

    rclpy.init()
    node = Node('fix_config_check')
    checks = []

    # 1. Simple scalar parameters.
    placeholders = {'BT_POSE': str(HERE / 'navigate_no_spin.xml'),
                    'BT_THROUGH': str(HERE / 'navigate_through_poses_no_spin.xml')}
    for target, name, expected in EXPECTED:
        if isinstance(expected, str):
            expected = placeholders.get(expected, expected)
        got = get_params(node, target, [name])
        if got is None:
            checks.append({'check': f'{target} {name}', 'ok': False,
                           'reason': 'service unavailable'})
            continue
        value = as_python(got[name]) if name in got else None
        if name not in got:
            checks.append({'check': f'{target} {name}', 'expected': expected,
                           'got': None, 'ok': False, 'reason': 'parameter not declared'})
            continue
        if isinstance(expected, list):
            ok = value == expected
        elif isinstance(expected, float):
            ok = value is not None and abs(value - expected) < 1e-6
        else:
            ok = value == expected
        checks.append({'check': f'{target} {name}', 'expected': expected, 'got': value, 'ok': ok})

    # 2. Footprints of both costmaps.
    for target in ('/global_costmap/global_costmap', '/local_costmap/local_costmap'):
        got = get_params(node, target, ['footprint'])
        if got is None:
            checks.append({'check': f'{target} footprint', 'ok': False,
                           'reason': 'service unavailable'})
            continue
        raw = as_python(got['footprint'])
        parsed = parse_polygon(raw)
        # The YAML stores three decimals, so the live value is the rounded polygon; the
        # comparison tolerance is stated instead of being hidden in an exact match.
        tol = 1e-3
        ok = parsed is not None and len(parsed) == len(poly) and all(
            abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol
            for a, b in zip(parsed, poly))
        # Also state explicitly that the swept rectangle is *not* what is loaded, so the
        # record cannot be read as the older 0.457 m footprint.
        is_swept = bool(parsed) and len(parsed) == 4 and all(
            abs(abs(p[1]) - swept['max'][1]) < 1e-3 for p in parsed) if swept else False
        checks.append({'check': f'{target} footprint', 'expected': poly,
                       'got': parsed, 'raw': raw, 'ok': ok,
                       'equals_swept_rectangle': is_swept,
                       'swept_half_width_m': round(swept['max'][1], 4) if swept else None})

    # 3. The behaviour trees themselves: the loaded path above proves which file, this
    #    proves the file has no reversing recovery left in it.
    import hashlib
    for fname in ('navigate_no_spin.xml', 'navigate_through_poses_no_spin.xml'):
        p = HERE / fname
        xml = p.read_text(encoding='utf-8')
        sha = hashlib.sha256(xml.encode('utf-8')).hexdigest()
        bad = [node_name for node_name in ('<BackUp', '<Spin') if node_name in xml]
        checks.append({'check': f'{fname} has no reversing recovery',
                       'sha256': sha, 'found': bad, 'ok': not bad})

    # 4. Map metadata, from the map server itself.
    map_msg = {}

    def on_map(msg):
        map_msg['info'] = {'width': msg.info.width, 'height': msg.info.height,
                           'resolution': msg.info.resolution,
                           'origin': [round(msg.info.origin.position.x, 3),
                                      round(msg.info.origin.position.y, 3)]}

    qos = QoSProfile(depth=1, reliability=QoSReliabilityPolicy.RELIABLE,
                     durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
                     history=QoSHistoryPolicy.KEEP_LAST)
    node.create_subscription(OccupancyGrid, '/map', on_map, qos)
    end = time.time() + 10
    while 'info' not in map_msg and time.time() < end:
        rclpy.spin_once(node, timeout_sec=0.2)
    info = map_msg.get('info')
    map_ok = bool(info and info['width'] == 241 and info['height'] == 465
                  and abs(info['resolution'] - 0.05) < 1e-9
                  and info['origin'] == [-5.09, -4.89])
    checks.append({'check': '/map metadata', 'got': info, 'ok': map_ok})

    # 5. The scan has to be alive, otherwise nothing downstream matters.
    scan = {}

    def on_scan(msg):
        finite = [r for r in msg.ranges if math.isfinite(r)]
        scan['frame'] = msg.header.frame_id
        scan['beams'] = len(msg.ranges)
        scan['finite'] = len(finite)
        scan['min'] = round(min(finite), 3) if finite else None

    node.create_subscription(LaserScan, '/scan', on_scan, qos_profile_sensor_data)
    end = time.time() + 10
    while 'beams' not in scan and time.time() < end:
        rclpy.spin_once(node, timeout_sec=0.2)
    scan_ok = scan.get('finite', 0) > 100 and scan.get('frame') == 'laser'
    checks.append({'check': '/scan', 'got': scan, 'ok': scan_ok})

    ok = all(c['ok'] for c in checks)
    doc = {'checked_at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'ok': ok,
           'params_file': str(HERE / 'nav2_params_fix.yaml'),
           'checks': checks}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'verify_fix_config.json').write_text(json.dumps(doc, indent=1), encoding='utf-8')
    for c in checks:
        print(('PASS ' if c['ok'] else 'FAIL ') + c['check'])
    print('overall', ok)
    node.destroy_node()
    rclpy.shutdown()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
