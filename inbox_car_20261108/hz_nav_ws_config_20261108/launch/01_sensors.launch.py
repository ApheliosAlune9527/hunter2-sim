"""个人感知入口：车体安装 TF、XT32 点云、二维扫描。"""

from pathlib import Path

from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    workspace = Path(__file__).resolve().parent.parent
    model_file = workspace / 'config' / 'hunter_nav.urdf'
    lidar_config = workspace / 'config' / 'hesai_xt32.yaml'
    log_dir = workspace / 'logs'

    for required_file in (model_file, lidar_config):
        if not required_file.is_file():
            raise FileNotFoundError(f'缺少个人配置文件：{required_file}')
    if not log_dir.is_dir():
        raise FileNotFoundError(f'缺少个人日志目录：{log_dir}')

    robot_description = ParameterValue(
        model_file.read_text(encoding='utf-8'), value_type=str)

    # 复用历史点云转扫描命令的高度和范围；实际过滤效果仍需验收。
    scan_parameters = {
        'use_sim_time': False,
        'target_frame': 'base_link',
        'transform_tolerance': 0.1,
        'min_height': 0.10,
        'max_height': 0.85,
        'angle_min': -3.14159,
        'angle_max': 3.14159,
        'angle_increment': 0.00872665,
        'scan_time': 0.10,
        'range_min': 0.50,
        'range_max': 20.0,
        'use_inf': True,
        'inf_epsilon': 1.0,
    }

    return LaunchDescription([
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            namespace='/hz_nav',
            name='robot_state_publisher',
            output='screen',
            cwd=str(log_dir),
            parameters=[{
                'robot_description': robot_description,
                'use_sim_time': False,
            }],
        ),
        Node(
            package='hesai_ros_driver',
            executable='hesai_ros_driver_node',
            namespace='/hz_nav',
            name='hesai_ros_driver_node',
            output='screen',
            cwd=str(log_dir),
            parameters=[{
                'config_path': str(lidar_config),
                'use_sim_time': False,
            }],
        ),
        Node(
            package='pointcloud_to_laserscan',
            executable='pointcloud_to_laserscan_node',
            namespace='/hz_nav',
            name='xt32_to_scan',
            output='screen',
            cwd=str(log_dir),
            parameters=[scan_parameters],
            remappings=[
                ('cloud_in', '/hz_nav/lidar_points'),
                ('scan', '/hz_nav/scan'),
            ],
        ),
    ])
