"""Truth localisation for the lab navigation baseline.

Publishes the map -> odom transform so that map -> odom -> base_link reproduces the
simulator ground-truth pose of the vehicle. The ground truth never touches the
controller: it only enters the transform chain that Nav2 consumes, exactly like a
localisation module would.

Also publishes the static base_link -> laser transform so the scan has a valid TF
parent (the scan comes straight from the simulator's 2-D lidar, bridged as /scan).
"""
import math

import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class TruthLocalisation(Node):
    def __init__(self):
        super().__init__('truth_localisation')
        self.truth = None
        self.odom = None
        self.stamp = None
        self.tf_pub = TransformBroadcaster(self)
        self.static_pub = StaticTransformBroadcaster(self)
        self.create_subscription(Odometry, '/ground_truth', self.on_truth, 10)
        self.create_subscription(Odometry, '/odom', self.on_odom, 10)
        self.timer = self.create_timer(0.01, self.tick)
        self.published = 0
        self.publish_static()

    def publish_static(self):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'base_link'
        t.child_frame_id = 'laser'
        t.transform.translation.x = 0.539
        t.transform.translation.z = 0.62
        # The gz sensor is mounted with a +90 deg yaw about z.
        t.transform.rotation.z = math.sin(math.pi / 4.0)
        t.transform.rotation.w = math.cos(math.pi / 4.0)
        self.static_pub.sendTransform(t)

    def on_truth(self, msg):
        self.truth = msg

    def on_odom(self, msg):
        self.odom = msg

    def tick(self):
        if self.truth is None or self.odom is None:
            return
        # T_map_base from ground truth, T_odom_base from wheel odometry.
        mx, my = self.truth.pose.pose.position.x, self.truth.pose.pose.position.y
        mq = self.truth.pose.pose.orientation
        myaw = yaw_of(mq)
        ox, oy = self.odom.pose.pose.position.x, self.odom.pose.pose.position.y
        oyaw = yaw_of(self.odom.pose.pose.orientation)
        # T_map_odom = T_map_base * inv(T_odom_base)
        c, s = math.cos(-oyaw), math.sin(-oyaw)
        rx, ry = -c * ox + s * oy, -s * ox - c * oy
        nx = mx + math.cos(myaw) * rx - math.sin(myaw) * ry
        ny = my + math.sin(myaw) * rx + math.cos(myaw) * ry
        nyaw = myaw - oyaw

        stamp = self.get_clock().now().to_msg()
        t = TransformStamped()
        t.header.stamp = stamp
        t.header.frame_id = 'map'
        t.child_frame_id = 'odom'
        t.transform.translation.x = nx
        t.transform.translation.y = ny
        t.transform.rotation.z = math.sin(nyaw / 2.0)
        t.transform.rotation.w = math.cos(nyaw / 2.0)
        self.tf_pub.sendTransform(t)

        # odom -> base_link comes from wheel odometry. Publishing it here (instead of
        # bridging the Gazebo tf topic) keeps one authority per frame and keeps the
        # stamp at the current simulation time, so a 10 Hz scan stamped slightly in
        # the past can always be transformed.
        o = TransformStamped()
        o.header.stamp = stamp
        o.header.frame_id = 'odom'
        o.child_frame_id = 'base_link'
        o.transform.translation.x = ox
        o.transform.translation.y = oy
        o.transform.rotation.z = math.sin(oyaw / 2.0)
        o.transform.rotation.w = math.cos(oyaw / 2.0)
        self.tf_pub.sendTransform(o)
        self.published += 1


def main():
    rclpy.init()
    node = TruthLocalisation()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
