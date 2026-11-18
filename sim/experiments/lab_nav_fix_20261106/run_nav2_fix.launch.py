"""Launch the corrected navigation stack, with every path written out here.

The old launch hard-coded the previous experiment directory, so copying the YAML
elsewhere and starting the old launch would silently load the old parameters.  This
file names its own parameter file, map and behaviour trees, and
`verify_fix_config.py` then reads the values back from the running nodes -- a file
assertion alone would not prove that the launch loaded it.

MAP_YAML is passed explicitly because the senior's parameter file leaves
`yaml_filename: ""` for his command line to fill.
"""
import os

from launch import LaunchDescription
from launch_ros.actions import Node

HERE = '/mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106'
# Default is the car's own file (see make_nav2_params_carmatch.py); set PARAMS to
# nav2_params_fix.yaml to run the earlier corrected variant instead.
PARAMS = os.environ.get('PARAMS', f'{HERE}/nav2_params_carmatch.yaml')
# free_thresh in the 2026-11-01 YAML was 0.25, and the grey "unknown" pixels are
# value 205, i.e. p = (255-205)/255 = 0.196 < 0.25 -- so map_server loaded every
# unknown cell as FREE (measured 2026-11-07: /map held 106137 free and 5928 occupied,
# zero -1).  allow_unknown: false therefore protected nothing.  The corrected YAML
# keeps the same image and sets free_thresh 0.10, which leaves those cells unknown.
MAP_YAML = os.environ.get(
    'HZ_NAV2_MAP_YAML', '/mnt/d/rob-memory/outputs/lab_nav_fix_20261106/lab_nav_map_fix.yaml'
)

LOCALIZER = os.environ.get('LOCALIZER', 'truth')


def node(package, executable, name):
    return Node(package=package, executable=executable, name=name, output='screen',
                parameters=[PARAMS, {'use_sim_time': True}])


def generate_launch_description():
    names = ['map_server']
    actions = [
        Node(package='nav2_map_server', executable='map_server', name='map_server',
             output='screen',
             parameters=[PARAMS, {'yaml_filename': MAP_YAML, 'use_sim_time': True}]),
    ]
    if LOCALIZER == 'amcl':
        names.append('amcl')
        actions.append(node('nav2_amcl', 'amcl', 'amcl'))
    # velocity_smoother is a lifecycle node: without it in this list it stays
    # unconfigured and publishes nothing, which looks exactly like a controller
    # that never commands a velocity.
    names += ['velocity_smoother', 'planner_server', 'controller_server',
              'behavior_server', 'bt_navigator']
    actions += [
        node('nav2_planner', 'planner_server', 'planner_server'),
        # The car runs velocity_smoother between the controller and the base, so the
        # controller must not talk to /cmd_vel directly here either.
        Node(package='nav2_controller', executable='controller_server',
             name='controller_server', output='screen',
             parameters=[PARAMS, {'use_sim_time': True}],
             remappings=[('cmd_vel', 'cmd_vel_nav')]),
        # velocity_smoother reads 'cmd_vel' and writes 'cmd_vel_smoothed'; without
        # these remaps it listens to the topic it publishes and the robot never moves.
        Node(package='nav2_velocity_smoother', executable='velocity_smoother',
             name='velocity_smoother', output='screen',
             parameters=[PARAMS, {'use_sim_time': True}],
             remappings=[('cmd_vel', 'cmd_vel_nav'), ('cmd_vel_smoothed', 'cmd_vel')]),
        node('nav2_behaviors', 'behavior_server', 'behavior_server'),
        node('nav2_bt_navigator', 'bt_navigator', 'bt_navigator'),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
             name='lifecycle_manager_navigation', output='screen',
             parameters=[{'use_sim_time': True, 'autostart': True,
                          'bond_timeout': 0.0, 'node_names': names}]),
    ]
    return LaunchDescription(actions)
