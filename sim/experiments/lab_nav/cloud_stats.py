"""Inspect the bridged point cloud: geometry counts and the height band that
pointcloud_to_laserscan keeps (0.10-0.85 m above the sensor frame)."""
import sys

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2


class Probe(Node):
    def __init__(self, topic, count):
        super().__init__('cloud_stats')
        self.want = count
        self.got = 0
        self.create_subscription(PointCloud2, topic, self.on_cloud, qos_profile_sensor_data)

    def on_cloud(self, msg):
        self.got += 1
        if self.got < self.want:
            return
        fields = {f.name: f.offset for f in msg.fields}
        n = msg.width * msg.height
        print('frame=%s w=%d h=%d n=%d point_step=%d fields=%s'
              % (msg.header.frame_id, msg.width, msg.height, n,
                 msg.point_step, sorted(fields)), flush=True)
        if n == 0:
            raise SystemExit(0)
        raw = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(n, msg.point_step)
        xyz = {}
        for name in ('x', 'y', 'z'):
            if name not in fields:
                raise SystemExit(f'missing field {name}')
            off = fields[name]
            xyz[name] = raw[:, off:off + 4].copy().view(np.float32).reshape(-1)
        finite = np.isfinite(xyz['x']) & np.isfinite(xyz['y']) & np.isfinite(xyz['z'])
        band = finite & (xyz['z'] >= 0.10) & (xyz['z'] <= 0.85)
        rng = np.hypot(xyz['x'][band], xyz['y'][band]) if band.any() else np.array([])
        print('finite=%d in_band=%d z=[%.2f,%.2f]' % (
            int(finite.sum()), int(band.sum()),
            float(xyz['z'][finite].min()) if finite.any() else float('nan'),
            float(xyz['z'][finite].max()) if finite.any() else float('nan')), flush=True)
        if rng.size:
            print('band_range min=%.2f mean=%.2f max=%.2f' % (
                rng.min(), rng.mean(), rng.max()), flush=True)
        raise SystemExit(0)


def main():
    topic = sys.argv[1] if len(sys.argv) > 1 else '/lidar_points'
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    rclpy.init()
    node = Probe(topic, count)
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    finally:
        node.destroy_node()


if __name__ == '__main__':
    main()
