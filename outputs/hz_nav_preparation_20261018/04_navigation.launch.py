"""个人 Nav2 入口：复用地图、定位与感知，默认不自动激活。

控制速度仅进入个人导航话题；本文件不启动底盘或连接底盘速度输入。
TF 继续使用现有的全局 /tf、/tf_static。
"""

from pathlib import Path
import xml.etree.ElementTree as ET

import yaml

from ament_index_python.packages import get_package_prefix
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


SERVER_SPECS = (
    ('nav2_controller', 'controller_server', (
        ('cmd_vel', '/hz_nav/nav_cmd_vel_raw'),
        ('/cmd_vel', '/hz_nav/nav_cmd_vel_raw'),
    )),
    ('nav2_smoother', 'smoother_server', ()),
    ('nav2_planner', 'planner_server', ()),
    ('nav2_behaviors', 'behavior_server', (
        ('cmd_vel', '/hz_nav/nav_cmd_vel'),
        ('/cmd_vel', '/hz_nav/nav_cmd_vel'),
        ('cmd_vel_teleop', '/hz_nav/nav_cmd_vel_teleop'),
        ('/cmd_vel_teleop', '/hz_nav/nav_cmd_vel_teleop'),
    )),
    ('nav2_bt_navigator', 'bt_navigator', (
        ('goal_pose', '/hz_nav/goal_pose'),
        ('/goal_pose', '/hz_nav/goal_pose'),
    )),
    ('nav2_waypoint_follower', 'waypoint_follower', ()),
    ('nav2_velocity_smoother', 'velocity_smoother', (
        ('cmd_vel', '/hz_nav/nav_cmd_vel_raw'),
        ('/cmd_vel', '/hz_nav/nav_cmd_vel_raw'),
        ('cmd_vel_smoothed', '/hz_nav/nav_cmd_vel'),
        ('/cmd_vel_smoothed', '/hz_nav/nav_cmd_vel'),
    )),
)


def generate_launch_description():
    workspace = Path(__file__).resolve().parent.parent
    config_dir = workspace / 'config'
    params_file = config_dir / 'nav2.yaml'
    log_dir = workspace / 'logs'
    bt_files = (
        config_dir / 'navigate_no_spin.xml',
        config_dir / 'navigate_through_poses_no_spin.xml',
    )
    for required_file in (params_file, *bt_files):
        if not required_file.is_file():
            raise FileNotFoundError(f'缺少个人导航配置：{required_file}')
    if not log_dir.is_dir():
        raise FileNotFoundError(f'缺少个人日志目录：{log_dir}')
    for bt_file in bt_files:
        ET.parse(bt_file)

    config = yaml.safe_load(params_file.read_text(encoding='utf-8'))
    server_names = [executable for _, executable, _ in SERVER_SPECS]
    expected_selectors = {f'/hz_nav/{name}' for name in server_names} | {
        '/hz_nav/local_costmap/local_costmap',
        '/hz_nav/global_costmap/global_costmap',
        '/hz_nav/bt_navigator_navigate_to_pose_rclcpp_node',
        '/hz_nav/bt_navigator_navigate_through_poses_rclcpp_node',
    }
    if not isinstance(config, dict) or set(config) != expected_selectors:
        raise ValueError('nav2.yaml 节点选择器与个人导航入口不匹配')
    for node_name, block in config.items():
        if not isinstance(block, dict):
            raise ValueError(f'节点配置必须为字典：{node_name}')
        parameters = block.get('ros__parameters')
        if not isinstance(parameters, dict) or parameters.get('use_sim_time') is not False:
            raise ValueError(f'节点必须使用实车时钟：{node_name}')

    def require_parameter(node_name, path, expected):
        value = config[node_name]['ros__parameters']
        for key in path:
            if not isinstance(value, dict) or key not in value:
                raise ValueError(f'缺少个人导航参数：{node_name} {path}')
            value = value[key]
        if type(value) is not type(expected) or value != expected:
            raise ValueError(f'个人导航参数不匹配：{node_name} {path}={value!r}')

    require_parameter('/hz_nav/bt_navigator', ('odom_topic',), '/hz_nav/odom')
    require_parameter('/hz_nav/bt_navigator', ('global_frame',), 'map')
    require_parameter('/hz_nav/bt_navigator', ('robot_base_frame',), 'base_link')
    require_parameter('/hz_nav/velocity_smoother', ('odom_topic',), '/hz_nav/odom')
    for name, frame, obstacle_layer in (
        ('local_costmap', 'odom', 'voxel_layer'),
        ('global_costmap', 'map', 'obstacle_layer'),
    ):
        selector = f'/hz_nav/{name}/{name}'
        require_parameter(selector, ('global_frame',), frame)
        require_parameter(selector, ('robot_base_frame',), 'base_link')
        require_parameter(selector, ('static_layer', 'map_topic'), '/hz_nav/map')
        require_parameter(selector, (obstacle_layer, 'scan', 'topic'), '/hz_nav/scan')
    for selector in expected_selectors:
        if selector.startswith('/hz_nav/bt_navigator'):
            require_parameter(selector, ('default_nav_to_pose_bt_xml',), str(bt_files[0]))
            require_parameter(selector, ('default_nav_through_poses_bt_xml',), str(bt_files[1]))

    # 仅使用已核对接口的系统 Humble 包；解析时只检查文件，不运行程序。
    packages = {package for package, _, _ in SERVER_SPECS} | {
        'nav2_lifecycle_manager',
        'nav2_costmap_2d',
        'nav2_smac_planner',
        'nav2_regulated_pure_pursuit_controller',
    }
    system_prefix = Path('/opt/ros/humble').resolve()
    prefixes = {}
    for package in sorted(packages):
        prefix = Path(get_package_prefix(package)).resolve()
        if prefix != system_prefix:
            raise RuntimeError(f'需要核对 Nav2 包来源：{package} 位于 {prefix}')
        prefixes[package] = prefix
    for package, executable in (
        *((package, executable) for package, executable, _ in SERVER_SPECS),
        ('nav2_lifecycle_manager', 'lifecycle_manager'),
    ):
        executable_path = prefixes[package] / 'lib' / package / executable
        if not executable_path.is_file():
            raise FileNotFoundError(f'缺少导航程序：{executable_path}')

    autostart = ParameterValue(LaunchConfiguration('autostart'), value_type=bool)
    actions = [DeclareLaunchArgument(
        'autostart',
        default_value='false',
        choices=['false', 'true'],
        description='Automatically configure and activate private Nav2 nodes; default is false.',
    )]
    odom_remappings = [('odom', '/hz_nav/odom'), ('/odom', '/hz_nav/odom')]
    for package, executable, topic_remappings in SERVER_SPECS:
        actions.append(Node(
            package=package,
            executable=executable,
            namespace='/hz_nav',
            name=executable,
            output='screen',
            cwd=str(log_dir),
            parameters=[str(params_file)],
            remappings=odom_remappings + list(topic_remappings),
        ))
    actions.append(Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        namespace='/hz_nav',
        name='lifecycle_manager_navigation',
        output='screen',
        cwd=str(log_dir),
        parameters=[{
            'use_sim_time': False,
            'autostart': autostart,
            'node_names': server_names,
        }],
    ))
    return LaunchDescription(actions)
