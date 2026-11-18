#!/usr/bin/env python3
"""Start map_server + AMCL only, without the navigation stack.

Used for task 5: the localiser must be exercised on its own (static drift, then
a 2 m straight run) before any navigation goal is sent, and the navigation
stack must not be the thing that makes the map appear.

Parameters come from the same derived file the rest of the stack uses; the map
yaml is passed here because the senior's asset leaves `yaml_filename: ""` and
supplies it on the command line.
"""
import os

from launch import LaunchDescription
from launch_ros.actions import LifecycleNode, Node

PARAMS = '/mnt/d/rob-memory/sim/experiments/lab_nav/nav2_params.yaml'
MAP_YAML = os.environ.get(
    'MAP_YAML', '/mnt/d/rob-memory/outputs/lab_nav_20261105/lab_nav_map.yaml')
# When the navigation stack is also running it brings up its own map_server; two
# of them fight over the lifecycle transitions, so this one can be switched off.
WITH_MAP = os.environ.get('WITH_MAP', '1') == '1'


def generate_launch_description():
    actions = []
    if WITH_MAP:
        actions.append(LifecycleNode(
            package='nav2_map_server', executable='map_server', name='map_server',
            namespace='', output='screen',
            parameters=[PARAMS, {'yaml_filename': MAP_YAML, 'use_sim_time': True}],
        ))
    actions.append(LifecycleNode(
        package='nav2_amcl', executable='amcl', name='amcl',
        namespace='', output='screen',
        parameters=[PARAMS, {'use_sim_time': True}],
    ))
    names = ['map_server', 'amcl'] if WITH_MAP else ['amcl']
    actions.append(Node(
        package='nav2_lifecycle_manager', executable='lifecycle_manager',
        name='lifecycle_manager_localization', output='screen',
        parameters=[{'use_sim_time': True, 'autostart': True, 'node_names': names}],
    ))
    return LaunchDescription(actions)
