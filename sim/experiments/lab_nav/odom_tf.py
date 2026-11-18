#!/usr/bin/env python3
"""Publish odom -> base_link from the bridged wheel odometry.

In truth mode `truth_localisation.py` owns this edge together with map -> odom.
With AMCL the localiser must own map -> odom alone, so the odometry edge is
pulled out into this small node: it copies the pose that the Ackermann plugin
already integrates and never looks at ground truth.
"""
import math

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster


class OdomTf(Node):
    def __init__(self):
        super().__init__('odom_tf')
        self.br = TransformBroadcaster(self)
        self.static = StaticTransformBroadcaster(self)
        self.create_subscription(Odometry, '/odom', self.on_odom, qos_profile_sensor_data)
        # AMCL needs the scan frame to exist.  In truth mode truth_localisation
        # publishes this edge; here it is the only publisher, so no duplicate.
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'base_link'
        t.child_frame_id = 'laser'
        t.transform.translation.x = 0.539
        t.transform.translation.z = 0.62
        t.transform.rotation.z = math.sin(math.pi / 4.0)
        t.transform.rotation.w = math.cos(math.pi / 4.0)
        self.static.sendTransform(t)

    def on_odom(self, msg):
        t = TransformStamped()
        t.header.stamp = msg.header.stamp           # never "now": that would
        t.header.frame_id = msg.header.frame_id     # reintroduce the extrapolation
        t.child_frame_id = msg.child_frame_id       # errors seen in task 3
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        t.transform.translation.x = p.x
        t.transform.translation.y = p.y
        t.transform.translation.z = p.z
        t.transform.rotation = q
        self.br.sendTransform(t)


def main():
    rclpy.init()
    node = OdomTf()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
