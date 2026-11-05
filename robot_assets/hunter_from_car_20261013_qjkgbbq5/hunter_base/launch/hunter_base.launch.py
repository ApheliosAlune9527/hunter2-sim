import launch
import launch_ros

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false'
    )

    port_name_arg = DeclareLaunchArgument(
        'port_name',
        default_value='can0'
    )

    odom_frame_arg = DeclareLaunchArgument(
        'odom_frame',
        default_value='odom'
    )

    base_frame_arg = DeclareLaunchArgument(
        'base_frame',
        default_value='base_link'
    )

    odom_topic_arg = DeclareLaunchArgument(
        'odom_topic_name',
        default_value='odom'
    )

    robot_model_arg = DeclareLaunchArgument(
        'robot_model',
        default_value='hunter2'
    )

    simulated_robot_arg = DeclareLaunchArgument(
        'simulated_robot',
        default_value='false'
    )

    control_rate_arg = DeclareLaunchArgument(
        'control_rate',
        default_value='50'
    )

    publish_odom_tf_arg = DeclareLaunchArgument(
        'publish_odom_tf',
        default_value='true',
        description='Publish odom to base_link TF'
    )

    hunter_base_node = launch_ros.actions.Node(
        package='hunter_base',
        executable='hunter_base_node',
        name='hunter_base_node',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'use_sim_time': ParameterValue(
                LaunchConfiguration('use_sim_time'),
                value_type=bool
            ),
            'port_name': LaunchConfiguration('port_name'),
            'odom_frame': LaunchConfiguration('odom_frame'),
            'base_frame': LaunchConfiguration('base_frame'),
            'odom_topic_name': LaunchConfiguration('odom_topic_name'),
            'robot_model': LaunchConfiguration('robot_model'),
            'simulated_robot': ParameterValue(
                LaunchConfiguration('simulated_robot'),
                value_type=bool
            ),
            'control_rate': ParameterValue(
                LaunchConfiguration('control_rate'),
                value_type=int
            ),
            'publish_odom_tf': ParameterValue(
                LaunchConfiguration('publish_odom_tf'),
                value_type=bool
            ),
        }],
    )

    return LaunchDescription([
        use_sim_time_arg,
        port_name_arg,
        odom_frame_arg,
        base_frame_arg,
        odom_topic_arg,
        robot_model_arg,
        simulated_robot_arg,
        control_rate_arg,
        publish_odom_tf_arg,
        hunter_base_node,
    ])
