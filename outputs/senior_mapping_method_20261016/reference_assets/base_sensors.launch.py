import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command
from launch_ros.actions import Node


def generate_launch_description():
    hunter_description_dir = get_package_share_directory('hunter_description')
    robot_bringup_dir = get_package_share_directory('robot_bringup')

    robot_description = Command([
        'xacro ',
        os.path.join(
            hunter_description_dir,
            'urdf',
            'assembly.urdf.xacro'
        ),
    ])

    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(robot_bringup_dir, 'launch', 'hunter.launch.py')
            )
        ),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(robot_bringup_dir, 'launch', 'xt32.launch.py')
            )
        ),

        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='hunter_robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_description}],
        ),

        Node(
            package='pointcloud_to_laserscan',
            executable='pointcloud_to_laserscan_node',
            name='xt32_to_scan',
            output='screen',
            remappings=[
                ('cloud_in', '/lidar_points'),
                ('scan', '/scan'),
            ],
            parameters=[{
                'target_frame': 'base_link',
                'transform_tolerance': 0.05,
                'min_height': -0.30,
                'max_height': 0.30,
                'angle_min': -3.14159,
                'angle_max': 3.14159,
                'angle_increment': 0.00872665,
                'scan_time': 0.10,
                'range_min': 0.20,
                'range_max': 20.0,
                'use_inf': True,
                'inf_epsilon': 1.0,
            }],
        ),
    ])
