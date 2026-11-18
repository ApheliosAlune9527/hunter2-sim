"""个人定位入口：复用已运行的地图服务，默认等待手动配置和激活。"""

from pathlib import Path

import yaml

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    workspace = Path(__file__).resolve().parent.parent
    params_file = workspace / 'config' / 'amcl.yaml'
    log_dir = workspace / 'logs'

    if not params_file.is_file():
        raise FileNotFoundError(f'缺少个人定位配置：{params_file}')
    if not log_dir.is_dir():
        raise FileNotFoundError(f'缺少个人日志目录：{log_dir}')

    config = yaml.safe_load(params_file.read_text(encoding='utf-8'))
    try:
        amcl_parameters = config['/hz_nav/amcl']['ros__parameters']
    except (KeyError, TypeError) as exc:
        raise ValueError('amcl.yaml 必须包含 /hz_nav/amcl 的 ros__parameters') from exc
    if not isinstance(amcl_parameters, dict):
        raise ValueError('AMCL ros__parameters 必须是参数字典')

    expected_parameters = {
        'use_sim_time': False,
        'scan_topic': '/hz_nav/scan',
        'map_topic': '/hz_nav/map',
        'base_frame_id': 'base_link',
        'odom_frame_id': 'odom',
        'global_frame_id': 'map',
        'set_initial_pose': False,
        'tf_broadcast': True,
    }
    for key, expected in expected_parameters.items():
        actual = amcl_parameters.get(key)
        if type(actual) is not type(expected) or actual != expected:
            raise ValueError(
                f'个人定位参数不符合当前接线：{key}={actual!r}，应为 {expected!r}')

    autostart = ParameterValue(
        LaunchConfiguration('autostart'), value_type=bool)

    return LaunchDescription([
        DeclareLaunchArgument(
            'autostart',
            default_value='false',
            description='Automatically configure and activate AMCL; default is false.',
        ),
        Node(
            package='nav2_amcl',
            executable='amcl',
            namespace='/hz_nav',
            name='amcl',
            output='screen',
            cwd=str(log_dir),
            parameters=[str(params_file)],
        ),
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            namespace='/hz_nav',
            name='lifecycle_manager_localization',
            output='screen',
            cwd=str(log_dir),
            parameters=[{
                'use_sim_time': False,
                'autostart': autostart,
                'node_names': ['amcl'],
            }],
        ),
    ])
