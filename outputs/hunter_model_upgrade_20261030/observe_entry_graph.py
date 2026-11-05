"""Read the normal full entry's ROS graph; never publish vehicle commands."""
import json
import os
from pathlib import Path
import pwd
import sys
import time
import uuid

sys.path.insert(0, '/mnt/f/rob-memory/sim/tools')
from check_ros_isolation import validate_environment
from check_full_ros_interfaces import BRIDGES


def main():
    validate_environment(os.environ, Path('/proc/sys/kernel/osrelease').read_text(),
                         pwd.getpwuid(os.getuid()).pw_name)
    if sys.argv[1:]:
        raise ValueError('No arguments allowed')
    import rclpy
    rclpy.init(args=[])
    node = rclpy.create_node('entry_graph_probe_' + uuid.uuid4().hex[:8],
                            namespace='/hz_sim/full', enable_rosout=False,
                            use_global_arguments=False)
    report = {'ok': False, 'velocity_published': False}
    try:
        expected = {'sensor_bridge', 'state_publisher', 'scan_converter'}
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.2)
            names = {name for name, namespace in node.get_node_names_and_namespaces()
                     if namespace == '/hz_sim/full'}
            if expected <= names:
                break
        report['observation_nodes'] = sorted(expected & names)
        report['publishers'] = {ros: len(node.get_publishers_info_by_topic(ros))
                                for ros, _, _, _ in BRIDGES}
        report['tf_static_publishers'] = len(node.get_publishers_info_by_topic('/hz_sim/full/tf_static'))
        report['command_publishers'] = len(node.get_publishers_info_by_topic('/hz_sim/full/cmd_vel'))
        report['ok'] = (expected <= names and all(report['publishers'].values()) and
                        report['tf_static_publishers'] > 0 and report['command_publishers'] == 0)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
