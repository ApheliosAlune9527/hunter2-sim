"""Read-only contract for the full model's one-way observation interfaces."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = '/hz_sim/full'
FRAMES = 'hz_sim/full/'
BRIDGES = (
    ('/clock', '/clock', 'rosgraph_msgs/msg/Clock', 'ignition.msgs.Clock'),
    (PREFIX + '/lidar/points', PREFIX + '/lidar/points',
     'sensor_msgs/msg/PointCloud2', 'ignition.msgs.PointCloudPacked'),
    (PREFIX + '/camera/image', PREFIX + '/camera/image',
     'sensor_msgs/msg/Image', 'ignition.msgs.Image'),
    (PREFIX + '/camera/depth_image', PREFIX + '/camera/depth_image',
     'sensor_msgs/msg/Image', 'ignition.msgs.Image'),
    (PREFIX + '/camera/camera_info', PREFIX + '/camera/camera_info',
     'sensor_msgs/msg/CameraInfo', 'ignition.msgs.CameraInfo'),
    (PREFIX + '/imu', PREFIX + '/imu', 'sensor_msgs/msg/Imu', 'ignition.msgs.IMU'),
    (PREFIX + '/joint_states', PREFIX + '/joint_states',
     'sensor_msgs/msg/JointState', 'ignition.msgs.Model'),
    (PREFIX + '/odom', PREFIX + '/odom', 'nav_msgs/msg/Odometry', 'ignition.msgs.Odometry'),
    (PREFIX + '/tf', PREFIX + '/tf', 'tf2_msgs/msg/TFMessage', 'ignition.msgs.Pose_V'),
)


def validate_bridge_config(config):
    """Refuse missing, extra, reverse-direction or unscoped interfaces."""
    if not isinstance(config, list) or len(config) != len(BRIDGES):
        raise ValueError('Expected exactly nine observation bridges')
    expected = {(ros, gz, ros_type, gz_type) for ros, gz, ros_type, gz_type in BRIDGES}
    actual = set()
    keys = {'ros_topic_name', 'gz_topic_name', 'ros_type_name', 'gz_type_name',
            'direction', 'lazy', 'publisher_queue', 'subscriber_queue'}
    for entry in config:
        if not isinstance(entry, dict) or set(entry) != keys:
            raise ValueError('Unexpected bridge entry or bridge option')
        if entry['direction'] != 'GZ_TO_ROS' or entry['lazy'] is not False:
            raise ValueError('Only non-lazy Gazebo to ROS observation is allowed')
        if any(type(entry[key]) is not int or entry[key] != 2
               for key in ('publisher_queue', 'subscriber_queue')):
            raise ValueError('Observation queues must remain bounded to two samples')
        identity = tuple(entry[key] for key in
                         ('ros_topic_name', 'gz_topic_name', 'ros_type_name', 'gz_type_name'))
        if identity not in expected or identity in actual:
            raise ValueError('Unapproved or duplicate bridge interface: ' + str(identity))
        actual.add(identity)
    if actual != expected:
        raise ValueError('Incomplete observation interfaces')
    return {'bridge_count': len(actual), 'direction': 'GZ_TO_ROS', 'actuation_bridge': False}


def scan_parameters():
    # The old base_link was ground centred. The new one is at the rear wheel
    # axis, 0.165 m higher: preserve the old 0.10..0.85 m obstacle height band.
    return {
        'use_sim_time': True, 'target_frame': FRAMES + 'base_link',
        'transform_tolerance': .1, 'min_height': -.065, 'max_height': .685,
        'angle_min': -math.pi, 'angle_max': math.pi, 'angle_increment': math.pi / 360,
        'scan_time': .1, 'range_min': .5, 'range_max': 20.0, 'use_inf': True,
    }


def check_interfaces():
    filename = ROOT / 'sim/config/hunter_full_bridge.yaml'
    return validate_bridge_config(json.loads(filename.read_text(encoding='utf-8')))


if __name__ == '__main__':
    print(json.dumps(check_interfaces(), ensure_ascii=False))
