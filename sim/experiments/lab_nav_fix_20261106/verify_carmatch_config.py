"""Read back the values that make the simulator behave like the vehicle.

The point is not "did the file change" -- the generator already proved the file is
the car's file plus seven lines -- but "did the running stack load those values".
A parameter file that is never used looks exactly like a correct one on disk.

Expectations are the car's: old rectangular footprint, unknown space plannable,
REEDS_SHEPP at 1.6 m, reversing allowed, 0.10 m/s, the recovery plugins the car
declares, and the car's behaviour tree (which contains BackUp).
"""
import json
import pathlib
import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from rcl_interfaces.srv import GetParameters
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import LaserScan

OUT = pathlib.Path('/mnt/d/rob-memory/outputs/lab_nav_fix_20261106/verify_carmatch_config.json')
FOOT = '[[0.52, 0.395], [0.52, -0.395], [-0.50, -0.395], [-0.50, 0.395]]'
BT = '/mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/navigate_no_spin_car.xml'

CHECKS = [
    ('/planner_server', 'GridBased.motion_model_for_search', 'REEDS_SHEPP'),
    ('/planner_server', 'GridBased.minimum_turning_radius', 1.6),
    ('/planner_server', 'GridBased.allow_unknown', True),
    ('/controller_server', 'FollowPath.allow_reversing', True),
    ('/controller_server', 'FollowPath.desired_linear_vel', 0.10),
    ('/global_costmap/global_costmap', 'footprint', FOOT),
    ('/local_costmap/local_costmap', 'footprint', FOOT),
    ('/bt_navigator', 'default_nav_to_pose_bt_xml', BT),
]


def value_to_python(v):
    """ParameterValue -> python.  The type numbers are 1 bool, 2 int, 3 double,
    4 string, then 7/8/9 for the arrays; getting them wrong is what made an earlier
    version of this check report failures on a correct stack."""
    t = v.type
    if t == 1:
        return v.bool_value
    if t == 2:
        return v.integer_value
    if t == 3:
        return v.double_value
    if t == 4:
        return v.string_value
    if t == 7:
        return list(v.bool_array_value)
    if t == 8:
        return list(v.integer_array_value)
    if t == 9:
        return list(v.double_array_value)
    if t == 5:
        return list(v.string_array_value)
    return None


class Checker(Node):
    def __init__(self):
        super().__init__('verify_carmatch')
        self.results = []
        self.map_info = None
        self.scan = None
        # map_server publishes once and latches; a volatile subscription that starts
        # later receives nothing at all.
        map_qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                             reliability=ReliabilityPolicy.RELIABLE)
        self.create_subscription(OccupancyGrid, '/map', self.on_map, map_qos)
        self.create_subscription(LaserScan, '/scan', self.on_scan, 10)

    def on_map(self, msg):
        if self.map_info is None:
            origin = msg.info.origin.position
            self.map_info = (msg.info.width, msg.info.height,
                             round(msg.info.resolution, 6),
                             (round(origin.x, 3), round(origin.y, 3)))

    def on_scan(self, msg):
        if self.scan is None:
            finite = sum(1 for r in msg.ranges if r == r and r > 0.0)
            self.scan = (msg.header.frame_id, len(msg.ranges), finite)

    def ask(self, node_name, param):
        cli = self.create_client(GetParameters, f'{node_name}/get_parameters')
        if not cli.wait_for_service(timeout_sec=5.0):
            return None, 'service not available'
        req = GetParameters.Request()
        req.names = [param]
        fut = cli.call_async(req)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=5.0)
        if not fut.done() or fut.result() is None:
            return None, 'no answer'
        return value_to_python(fut.result().values[0]), None

    def run_checks(self):
        for node_name, param, want in CHECKS:
            got, err = self.ask(node_name, param)
            ok = (got == want)
            self.results.append({'node': node_name, 'parameter': param,
                                 'expected': want, 'got': got,
                                 'pass': ok, 'error': err})


def main():
    rclpy.init()
    node = Checker()
    deadline = node.get_clock().now().nanoseconds + 60 * 10**9
    while rclpy.ok() and (node.map_info is None or node.scan is None):
        rclpy.spin_once(node, timeout_sec=0.2)
        if node.get_clock().now().nanoseconds > deadline:
            break
    node.run_checks()

    checks = list(node.results)

    # Evidence for the recovery plugins has to come from the log: nav2_behaviors
    # resets behavior_plugins to [] once it has created the plugins, so asking the
    # running node returns an empty list even when the file was loaded correctly.
    log = pathlib.Path('/tmp/lab_fix_stack/nav2.log')
    text = log.read_text(errors='ignore') if log.exists() else ''
    for plugin, typ in (('backup', 'nav2_behaviors/BackUp'),
                        ('drive_on_heading', 'nav2_behaviors/DriveOnHeading'),
                        ('assisted_teleop', 'nav2_behaviors/AssistedTeleop'),
                        ('wait', 'nav2_behaviors/Wait')):
        line = f'Creating behavior plugin {plugin} of type {typ}'
        checks.append({'node': 'log:behavior_server', 'parameter': f'plugin {plugin}',
                       'expected': line, 'got': line if line in text else 'absent',
                       'pass': line in text})
    info = node.map_info or (None, None, None, None)
    w, h, res = info[0], info[1], info[2]
    checks.append({'node': '/map', 'parameter': 'size', 'expected': '241x465',
                   'got': f'{w}x{h}' if w else None, 'pass': (w, h) == (241, 465)})
    checks.append({'node': '/map', 'parameter': 'resolution', 'expected': 0.05,
                   'got': res, 'pass': res == 0.05})
    checks.append({'node': '/scan', 'parameter': 'frame_id', 'expected': 'laser',
                   'got': node.scan[0] if node.scan else None,
                   'pass': bool(node.scan) and node.scan[0] == 'laser'})
    checks.append({'node': '/scan', 'parameter': 'finite_beams',
                   'expected': '>100', 'got': node.scan[2] if node.scan else None,
                   'pass': bool(node.scan) and node.scan[2] > 100})

    ok = all(c['pass'] for c in checks)
    OUT.write_text(json.dumps({'ok': ok, 'checks': checks,
                               'parameters_file': 'nav2_params_carmatch.yaml',
                               'source': '/home/car/hz_nav_ws/config/nav2_params.yaml'},
                              indent=1))
    for c in checks:
        print(f"{'PASS' if c['pass'] else 'FAIL'} {c['node']} {c['parameter']}: "
              f"got={c['got']!r} want={c['expected']!r}")
    print(json.dumps({'ok': ok, 'checks': len(checks),
                      'failed': sum(1 for c in checks if not c['pass'])}))
    node.destroy_node()
    rclpy.shutdown()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
