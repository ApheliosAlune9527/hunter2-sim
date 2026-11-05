"""Full model observation nodes only; no actuator bridge or hardware driver."""
from pathlib import Path
import sys

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

ROOT = Path('/mnt/f/rob-memory')
sys.path.insert(0, str(ROOT / 'sim/tools'))
from check_full_ros_interfaces import check_interfaces, scan_parameters


def generate_launch_description():
    check_interfaces()
    description = (Path(get_package_share_directory('hz_hunter_full_description')) /
                   'urdf/hunter_full.urdf').read_text(encoding='utf-8')
    namespace = '/hz_sim/full'
    tf_remaps = [('/tf', namespace + '/tf'), ('/tf_static', namespace + '/tf_static')]
    return LaunchDescription([
        Node(package='ros_gz_bridge', executable='parameter_bridge',
             name='sensor_bridge', namespace=namespace, output='screen',
             parameters=[{'config_file': str(ROOT / 'sim/config/hunter_full_bridge.yaml'),
                          'use_sim_time': True}]),
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             name='state_publisher', namespace=namespace, output='screen',
             parameters=[{'robot_description': description, 'use_sim_time': True,
                          'frame_prefix': 'hz_sim/full/'}],
             remappings=tf_remaps + [('joint_states', namespace + '/joint_states')]),
        Node(package='pointcloud_to_laserscan', executable='pointcloud_to_laserscan_node',
             name='scan_converter', namespace=namespace, output='screen',
             parameters=[scan_parameters()], remappings=tf_remaps + [
                 ('cloud_in', namespace + '/lidar/points'), ('scan', namespace + '/scan')]),
    ])
