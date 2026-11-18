"""Are the wheels turning?  Publish a forward speed and print the joint velocities.

If the wheels spin but the body does not move, the problem is contact/friction; if the
wheels stay still while /hz_sim/lab/cmd_vel receives commands, the plugin is not
actuating.
"""
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import JointState

latest = {}


def main():
    rclpy.init()
    node = Node('wheel_probe')
    node.set_parameters([rclpy.parameter.Parameter('use_sim_time', value=True)])
    pub = node.create_publisher(Twist, '/cmd_vel', 10)

    def on_joint(msg):
        for name, vel in zip(msg.name, msg.velocity):
            latest[name] = vel

    node.create_subscription(JointState, '/joint_states', on_joint, 10)

    # settle subscriptions
    end = time.monotonic() + 2
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.05)

    print('idle velocities:', {k: round(v, 3) for k, v in list(latest.items())[:6]})

    cmd = Twist()
    cmd.linear.x = 0.15
    end = time.monotonic() + 4
    while time.monotonic() < end:
        pub.publish(cmd)
        rclpy.spin_once(node, timeout_sec=0.02)
    pub.publish(Twist())
    print('driving velocities:', {k: round(v, 3) for k, v in list(latest.items())[:6]})
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
