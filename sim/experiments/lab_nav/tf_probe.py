"""Diagnose why the local costmap drops laser scans."""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener


class Probe(Node):
    def __init__(self):
        super().__init__('tf_probe')
        self.buf = Buffer()
        self.listener = TransformListener(self.buf, self)
        self.create_subscription(LaserScan, '/hz_sim/lab/scan', self.on_scan, 10)
        self.n = 0

    def on_scan(self, msg):
        self.n += 1
        if self.n % 10:
            return
        now = self.get_clock().now().to_msg()
        stamp = msg.header.stamp
        lag = (now.sec + now.nanosec * 1e-9) - (stamp.sec + stamp.nanosec * 1e-9)
        for target in ('odom', 'base_link'):
            try:
                self.buf.lookup_transform(target, msg.header.frame_id, stamp, rclpy.time.Duration(seconds=0.2))
                ok = 'ok'
            except Exception as exc:  # noqa: BLE001
                ok = type(exc).__name__ + ': ' + str(exc)[:90]
            print(f'scan#{self.n} lag={lag:+.3f}s {target}<-laser: {ok}', flush=True)


def main():
    rclpy.init()
    node = Probe()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    rclpy.shutdown()


if __name__ == '__main__':
    main()
