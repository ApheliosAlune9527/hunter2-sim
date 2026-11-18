"""Print basic statistics for whatever is arriving on a LaserScan topic.

Used to prove that the pointcloud_to_laserscan stage produces real geometry
rather than the all-minimum-range pattern that a self-occluded beam gives.
"""
import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


class Probe(Node):
    def __init__(self, topic, count):
        super().__init__('scan_stats')
        self.want = count
        self.got = 0
        # pointcloud_to_laserscan publishes with SensorDataQoS (best effort), so a
        # reliable subscriber would see nothing at all.
        self.create_subscription(LaserScan, topic, self.on_scan, qos_profile_sensor_data)

    def on_scan(self, msg):
        finite = [r for r in msg.ranges if r == r and abs(r) != float('inf')]
        self.got += 1
        if self.got >= self.want:
            if finite:
                print('frame=%s beams=%d finite=%d min=%.2f mean=%.2f max=%.2f '
                      'angle_inc=%.6f range=%.2f..%.2f'
                      % (msg.header.frame_id, len(msg.ranges), len(finite),
                         min(finite), sum(finite) / len(finite), max(finite),
                         msg.angle_increment, msg.range_min, msg.range_max),
                      flush=True)
            else:
                print('frame=%s beams=%d finite=0 (all inf/NaN)'
                      % (msg.header.frame_id, len(msg.ranges)), flush=True)
            raise SystemExit(0)


def main():
    topic = sys.argv[1] if len(sys.argv) > 1 else '/scan'
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    rclpy.init()
    node = Probe(topic, count)
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
