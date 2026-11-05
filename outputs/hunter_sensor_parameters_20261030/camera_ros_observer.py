"""Read CameraInfo on a private local ROS domain; publish nothing."""
import json
import time

import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo


def main():
    rclpy.init(args=[])
    node = rclpy.create_node('hz_camera_info_probe', enable_rosout=False)
    received = []
    subscription = node.create_subscription(CameraInfo, '/hz_camera_probe/camera/camera_info',
                                             received.append, qos_profile_sensor_data)
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline and not received:
        rclpy.spin_once(node, timeout_sec=.2)
    if not received:
        raise TimeoutError('No CameraInfo on private ROS domain')
    msg = received[-1]
    fx = 606.7595825195312
    expected_k = [fx, 0, 320, 0, fx, 240, 0, 0, 1]
    expected_p = [fx, 0, 320, 0, 0, fx, 240, 0, 0, 0, 1, 0]
    if (msg.width, msg.height, msg.header.frame_id) != (640, 480, 'hz_camera_probe/camera_optical_frame'):
        raise ValueError('CameraInfo dimensions or frame mismatch')
    if any(abs(a - b) > 1e-6 for a, b in zip(msg.k, expected_k)):
        raise ValueError('ROS intrinsic matrix mismatch')
    if any(abs(a - b) > 1e-6 for a, b in zip(msg.p, expected_p)):
        raise ValueError('ROS projection matrix mismatch')
    print(json.dumps({'ok': True, 'frame': msg.header.frame_id,
                      'k': list(msg.k), 'p': list(msg.p)}), flush=True)
    node.destroy_subscription(subscription)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
