import os

from launch import LaunchDescription
from launch_ros.actions import Node

PARAMS = '/mnt/d/rob-memory/sim/experiments/lab_nav/nav2_params.yaml'
# The senior's nav2_params.yaml leaves yaml_filename empty because his command line
# passes map:=.../lab_odom_01.yaml to bringup_launch.py. This is that argument.
MAP_YAML = '/mnt/d/rob-memory/outputs/lab_nav_20261105/lab_nav_map.yaml'
# /cmd_vel needs no remap: the bridge already maps ROS /cmd_vel to the Gazebo
# topic, so the ROS side keeps the car's topic names.
CMD_VEL = []

# In AMCL mode the particle filter is managed by this same lifecycle manager and
# comes up after map_server, which is the only order that works: AMCL's configure
# step needs /map to already exist.  A second manager cannot be used for it.
LOCALIZER = os.environ.get('LOCALIZER', 'truth')


def node(package, executable, name, remappings=None):
    return Node(package=package, executable=executable, name=name, output='screen',
                parameters=[PARAMS], remappings=remappings or [])


def generate_launch_description():
    names = ['map_server']
    actions = [
        Node(package='nav2_map_server', executable='map_server', name='map_server',
             output='screen',
             parameters=[PARAMS, {'yaml_filename': MAP_YAML, 'use_sim_time': True}]),
    ]
    if LOCALIZER == 'amcl':
        names.append('amcl')
        actions.append(Node(package='nav2_amcl', executable='amcl', name='amcl',
                            output='screen',
                            parameters=[PARAMS, {'use_sim_time': True}]))
    names += ['planner_server', 'controller_server', 'behavior_server', 'bt_navigator']
    actions += [
        node('nav2_planner', 'planner_server', 'planner_server'),
        node('nav2_controller', 'controller_server', 'controller_server', CMD_VEL),
        node('nav2_behaviors', 'behavior_server', 'behavior_server', CMD_VEL),
        node('nav2_bt_navigator', 'bt_navigator', 'bt_navigator'),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
             name='lifecycle_manager_navigation', output='screen',
             parameters=[{'use_sim_time': True, 'autostart': True,
                          'bond_timeout': 0.0, 'node_names': names}]),
    ]
    return LaunchDescription(actions)
