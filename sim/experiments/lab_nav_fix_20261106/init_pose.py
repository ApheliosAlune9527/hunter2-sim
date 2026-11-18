#!/usr/bin/env python3
"""Give AMCL its starting pose so the map frame exists.

AMCL only starts publishing map -> odom after it has an initial pose, and the
navigation stack's global costmap will not finish activating until that
transform exists.  Waiting for "managed nodes are active" before telling AMCL
where it is therefore deadlocks.  This node keeps re-sending /initialpose until
map -> base_link resolves, then exits.
"""
import math
import sys
import time

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from tf2_ros import Buffer, TransformListener

SPAWN = (-0.21, -0.77, 0.0)


def main():
    rclpy.init()
    node = Node('init_pose')
    pub = node.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
    buf = Buffer()
    TransformListener(buf, node, spin_thread=False)

    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = 'map'
    msg.pose.pose.position.x = SPAWN[0]
    msg.pose.pose.position.y = SPAWN[1]
    msg.pose.pose.orientation.z = math.sin(SPAWN[2] / 2)
    msg.pose.pose.orientation.w = math.cos(SPAWN[2] / 2)
    msg.pose.covariance[0] = 0.25
    msg.pose.covariance[7] = 0.25
    msg.pose.covariance[35] = 0.0685

    deadline = time.time() + 90.0
    while time.time() < deadline:
        msg.header.stamp = node.get_clock().now().to_msg()
        pub.publish(msg)
        for _ in range(4):
            rclpy.spin_once(node, timeout_sec=0.1)
            if buf.can_transform('map', 'base_link', rclpy.time.Time()):
                print('[init_pose] map -> base_link available')
                node.destroy_node()
                rclpy.try_shutdown()
                return 0
            time.sleep(0.15)
    print('[init_pose] FAILED: map -> base_link never appeared', file=sys.stderr)
    node.destroy_node()
    rclpy.try_shutdown()
    return 1


if __name__ == '__main__':
    sys.exit(main())
