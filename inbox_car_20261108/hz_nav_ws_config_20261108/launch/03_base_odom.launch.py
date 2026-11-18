"""个人底盘里程计入口，默认不连接底盘。

启用后，现有驱动会连接 CAN 并调用 EnableCommandedMode。
速度话题重映射仅用于 ROS 接线隔离，不构成硬件制动或只读模式。
"""

from pathlib import Path

from ament_index_python.packages import get_package_prefix
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    workspace = Path(__file__).resolve().parent.parent
    log_dir = workspace / 'logs'
    if not log_dir.is_dir():
        raise FileNotFoundError(f'缺少个人日志目录：{log_dir}')

    expected_prefix = Path('/home/car/hunter2.0_ws/install/hunter_base')
    actual_prefix = Path(get_package_prefix('hunter_base'))
    if actual_prefix.resolve() != expected_prefix.resolve():
        raise RuntimeError(
            f'hunter_base 来源改变：{actual_prefix}；预期为 {expected_prefix}')

    connect_chassis = LaunchConfiguration('connect_chassis')

    return LaunchDescription([
        DeclareLaunchArgument(
            'connect_chassis',
            default_value='false',
            choices=['false', 'true'],
            description=(
                'Connect CAN and enable commanded mode; requires explicit approval '
                'and onsite supervision. Default is false.'),
        ),
        LogInfo(
            msg='底盘未连接：connect_chassis=false。',
            condition=UnlessCondition(connect_chassis),
        ),
        LogInfo(
            msg=(
                '即将连接 can0 并切换到指令模式；'
                '速度输入固定为 /hz_nav/blocked_cmd_vel，须有现场接管条件。'),
            condition=IfCondition(connect_chassis),
        ),
        Node(
            package='hunter_base',
            executable='hunter_base_node',
            namespace='/hz_nav',
            name='hunter_base_node',
            output='screen',
            emulate_tty=True,
            cwd=str(log_dir),
            condition=IfCondition(connect_chassis),
            parameters=[{
                'use_sim_time': False,
                'port_name': 'can0',
                'odom_frame': 'odom',
                'base_frame': 'base_link',
                'odom_topic_name': '/hz_nav/odom',
                'robot_model': 'hunter2',
                'simulated_robot': False,
                'control_rate': 50,
                'publish_odom_tf': True,
            }],
            remappings=[
                ('/cmd_vel', '/hz_nav/blocked_cmd_vel'),
                ('/hunter_status', '/hz_nav/hunter_status'),
            ],
        ),
    ])
