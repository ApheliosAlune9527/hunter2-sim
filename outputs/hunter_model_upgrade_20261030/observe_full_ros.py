"""Subscribe to full-model observations and check payloads/TF. No control API."""
import json
import math
import os
from pathlib import Path
import pwd
import struct
import sys
import time
import uuid
import zlib

ROOT = Path('/mnt/f/rob-memory')
sys.path.insert(0, str(ROOT / 'sim/tools'))
from check_ros_isolation import validate_environment


def png(filename, width, height, rows, colour_type):
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    payload = b''.join(b'\0' + row for row in rows)
    filename.write_bytes(b'\x89PNG\r\n\x1a\n' +
                         chunk(b'IHDR', struct.pack('!IIBBBBB', width, height, 8, colour_type, 0, 0, 0)) +
                         chunk(b'IDAT', zlib.compress(payload)) + chunk(b'IEND', b''))


def main():
    validate_environment(os.environ, Path('/proc/sys/kernel/osrelease').read_text(),
                         pwd.getpwuid(os.getuid()).pw_name)
    if len(sys.argv) != 2:
        raise ValueError('Exactly one local report directory is required')
    directory = Path(sys.argv[1]).resolve()
    allowed = ROOT / 'outputs/hunter_model_upgrade_20261030/references/full_sensors'
    if not directory.is_relative_to(allowed.resolve()) or not directory.is_dir():
        raise ValueError('Unexpected report directory')
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from rclpy.time import Time
    from sensor_msgs.msg import CameraInfo, Image, Imu, LaserScan, PointCloud2
    from rosgraph_msgs.msg import Clock
    from tf2_ros import Buffer, TransformListener

    rclpy.init(args=[])
    node = rclpy.create_node('sensor_observer_' + uuid.uuid4().hex[:8], namespace='/hz_sim/full',
                            cli_args=['--ros-args', '-r', '/tf:=/hz_sim/full/tf',
                                      '-r', '/tf_static:=/hz_sim/full/tf_static'],
                            use_global_arguments=False, enable_rosout=False)
    buffer = Buffer()
    listener = TransformListener(buffer, node)
    samples = {}
    messages = {}

    def receive(name, message):
        messages[name] = message
        if name == 'clock':
            stamp = message.clock
            frame = None
        else:
            stamp, frame = message.header.stamp, message.header.frame_id
        sample = samples.setdefault(name, {'count': 0, 'first_stamp_ns': None})
        sample['count'] += 1
        sample['stamp_ns'] = stamp.sec * 1000000000 + stamp.nanosec
        if sample['first_stamp_ns'] is None:
            sample['first_stamp_ns'] = sample['stamp_ns']
        if frame is not None:
            sample['frame'] = frame

    subscriptions = []
    interfaces = [('clock', Clock, '/clock'),
                  ('points', PointCloud2, '/hz_sim/full/lidar/points'),
                  ('rgb', Image, '/hz_sim/full/camera/image'),
                  ('depth', Image, '/hz_sim/full/camera/depth_image'),
                  ('camera_info', CameraInfo, '/hz_sim/full/camera/camera_info'),
                  ('imu', Imu, '/hz_sim/full/imu'),
                  ('scan', LaserScan, '/hz_sim/full/scan')]
    for name, message_type, topic in interfaces:
        subscriptions.append(node.create_subscription(
            message_type, topic, lambda message, name=name: receive(name, message), qos_profile_sensor_data))

    report = {'ok': False, 'motion_published': False, 'samples': samples}
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.15)
            if all(samples.get(name, {}).get('count', 0) >= 2 for name, _, _ in interfaces):
                break
        for name, _, _ in interfaces:
            sample = samples.get(name, {})
            if sample.get('count', 0) < 2 or sample.get('stamp_ns', 0) <= sample.get('first_stamp_ns', 0):
                raise ValueError('Missing/non-progressing ROS stream: ' + name)
        expected_frames = {'points': 'hesai_lidar', 'rgb': 'camera_optical_frame',
                           'depth': 'camera_optical_frame', 'camera_info': 'camera_optical_frame',
                           'imu': 'imu_link', 'scan': 'base_link'}
        for name, frame in expected_frames.items():
            if samples[name]['frame'] != 'hz_sim/full/' + frame:
                raise ValueError('Wrong ROS frame: ' + name + ' ' + samples[name]['frame'])

        points = messages['points']
        offsets = {field.name: field.offset for field in points.fields if field.datatype == 7}
        if not {'x', 'y', 'z'} <= offsets.keys() or len(points.data) != points.row_step * points.height:
            raise ValueError('Malformed XYZ point cloud')
        endian = '>' if points.is_bigendian else '<'
        finite = 0
        for row in range(points.height):
            for column in range(points.width):
                index = row * points.row_step + column * points.point_step
                xyz = [struct.unpack_from(endian + 'f', points.data, index + offsets[key])[0]
                       for key in ('x', 'y', 'z')]
                if all(math.isfinite(value) for value in xyz):
                    finite += 1
        if points.width != 720 or points.height != 32 or finite < 10:
            raise ValueError('Incomplete 32-channel cloud')
        samples['points'].update(width=points.width, height=points.height,
                                 finite_points=finite, bytes=len(points.data))

        rgb = messages['rgb']
        if (rgb.width, rgb.height, rgb.encoding) != (640, 480, 'rgb8'):
            raise ValueError('Unexpected RGB image shape/encoding')
        rows = [bytes(rgb.data[row * rgb.step:row * rgb.step + rgb.width * 3]) for row in range(rgb.height)]
        if len(set(b''.join(rows))) < 8:
            raise ValueError('RGB image is empty or uniform')
        png(directory / 'rgb.png', rgb.width, rgb.height, rows, 2)
        samples['rgb'].update(width=rgb.width, height=rgb.height, encoding=rgb.encoding, bytes=len(rgb.data))

        depth = messages['depth']
        if (depth.width, depth.height, depth.encoding) != (640, 480, '32FC1'):
            raise ValueError('Unexpected depth image shape/encoding')
        finite_depth = 0
        gray_rows = []
        endian = '>' if depth.is_bigendian else '<'
        for row in range(depth.height):
            values = struct.unpack_from(endian + 'f' * depth.width, depth.data, row * depth.step)
            finite_depth += sum(math.isfinite(value) and .1 <= value <= 20 for value in values)
            gray_rows.append(bytes(round(255 * (1 - min(value, 8) / 8))
                                   if math.isfinite(value) and value >= 0 else 0 for value in values))
        if finite_depth < depth.width:
            raise ValueError('Depth image has no useful ranges')
        png(directory / 'depth_preview.png', depth.width, depth.height, gray_rows, 0)
        samples['depth'].update(width=depth.width, height=depth.height, encoding=depth.encoding,
                                finite_ranges=finite_depth, bytes=len(depth.data))

        info = messages['camera_info']
        if (info.width, info.height) != (640, 480) or info.k[0] <= 0 or info.k[4] <= 0:
            raise ValueError('Camera intrinsics missing')
        samples['camera_info'].update(fx=info.k[0], fy=info.k[4])
        imu = messages['imu']
        acceleration = [imu.linear_acceleration.x, imu.linear_acceleration.y, imu.linear_acceleration.z]
        angular = [imu.angular_velocity.x, imu.angular_velocity.y, imu.angular_velocity.z]
        if not all(math.isfinite(v) for v in acceleration + angular) or abs(acceleration[2] - 9.81) > .05:
            raise ValueError('Static IMU does not report finite nominal gravity')
        samples['imu'].update(acceleration_m_s2=acceleration, angular_velocity_rad_s=angular)
        scan = messages['scan']
        finite_scan = sum(math.isfinite(value) and scan.range_min <= value <= scan.range_max
                          for value in scan.ranges)
        if finite_scan < 3:
            raise ValueError('No usable 2D scan from pointcloud/TF')
        samples['scan'].update(bins=len(scan.ranges), finite_ranges=finite_scan)

        transforms = {}
        expected_xyz = {'hesai_lidar': (.539, 0, .525),
                        'camera_optical_frame': (.65765, .0175, .481),
                        'imu_link': (.64591, .01198, .4861)}
        for frame, expected in expected_xyz.items():
            transform = buffer.lookup_transform('hz_sim/full/base_link', 'hz_sim/full/' + frame, Time())
            xyz = [getattr(transform.transform.translation, key) for key in 'xyz']
            quaternion = [getattr(transform.transform.rotation, key) for key in 'xyzw']
            if any(abs(actual - nominal) > 1e-7 for actual, nominal in zip(xyz, expected)):
                raise ValueError('ROS sensor TF translation disagrees with model: ' + frame)
            transforms[frame] = {'xyz_m': xyz, 'quaternion_xyzw': quaternion}
        report['transforms_from_base_link'] = transforms
        report['ros_command_publishers'] = len(node.get_publishers_info_by_topic('/hz_sim/full/cmd_vel'))
        if report['ros_command_publishers']:
            raise ValueError('Unexpected ROS command publisher')
        report['ok'] = True
    except Exception as error:
        report['error'] = repr(error)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    (directory / 'ros_check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
