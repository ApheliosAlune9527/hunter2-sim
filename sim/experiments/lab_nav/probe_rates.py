"""Measure per-topic delivery rates and the real-time factor of a running stack.

Subscriptions are created by explicit name and type rather than by graph
discovery: on this machine `get_topic_names_and_types()` stayed empty for the
whole measurement window even though `ros2 topic list` showed the topics, while
a subscription created by name matched immediately.  Guessing from the graph
would therefore report "nothing published" for a perfectly healthy stack.

Per topic: message count, receive rate, interval statistics.  Combined with
/clock, the gap between the receive rate and the nominal sensor rate is what
separates a slow producer from a slow transport.
"""
import argparse
import json
import time
from pathlib import Path

import rclpy
from rclpy.qos import qos_profile_sensor_data

PROFILES = {
    # lab navigation stack: one 2D scan and the odometry/truth plumbing
    'lean': [
        ('/clock', 'rosgraph_msgs/Clock'),
        ('/scan', 'sensor_msgs/LaserScan'),
        ('/odom', 'nav_msgs/Odometry'),
        ('/ground_truth', 'nav_msgs/Odometry'),
        ('/joint_states', 'sensor_msgs/JointState'),
        ('/contacts', 'ros_gz_interfaces/Contacts'),
    ],
    # full sensor set of the reference model
    'full': [
        ('/clock', 'rosgraph_msgs/Clock'),
        ('/hz_sim/full/lidar/points', 'sensor_msgs/PointCloud2'),
        ('/hz_sim/full/camera/image', 'sensor_msgs/Image'),
        ('/hz_sim/full/camera/depth_image', 'sensor_msgs/Image'),
        ('/hz_sim/full/imu', 'sensor_msgs/Imu'),
        ('/hz_sim/full/joint_states', 'sensor_msgs/JointState'),
        ('/hz_sim/full/odom', 'nav_msgs/Odometry'),
    ],
}


def resolve(spec):
    module, cls = spec.split('/')
    if module == 'rosgraph_msgs':
        from rosgraph_msgs.msg import Clock
        return Clock
    for pkg in ('sensor_msgs', 'nav_msgs', 'ros_gz_interfaces'):
        if module == pkg:
            mod = __import__(pkg + '.msg', fromlist=[cls])
            return getattr(mod, cls)
    raise ValueError(spec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--profile', choices=sorted(PROFILES), default='lean')
    ap.add_argument('--seconds', type=float, default=20.0)
    ap.add_argument('--label', default='run')
    ap.add_argument('--out', default='')
    args = ap.parse_args()

    rclpy.init(args=[])
    node = rclpy.create_node('rate_probe')
    stamps = {}
    sim = {'first': None, 'last': None}

    def cb(topic, msg):
        now = time.monotonic()
        stamps.setdefault(topic, []).append(now)
        if topic == '/clock':
            t = msg.clock.sec + msg.clock.nanosec * 1e-9
            if sim['first'] is None:
                sim['first'] = (now, t)
            sim['last'] = (now, t)

    keep = []
    for topic, spec in PROFILES[args.profile]:
        try:
            cls = resolve(spec)
        except Exception as exc:                      # a topic this image lacks
            print(f'[probe] cannot resolve {spec}: {exc}')
            continue
        keep.append(node.create_subscription(
            cls, topic, lambda m, t=topic: cb(t, m), qos_profile_sensor_data))

    armed = time.monotonic()
    deadline = armed + args.seconds
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
    wall = time.monotonic() - armed

    report = {'label': args.label, 'profile': args.profile, 'wall_seconds': wall,
              'topics': {}}
    if sim['first'] and sim['last']:
        (w0, t0), (w1, t1) = sim['first'], sim['last']
        report['sim_seconds'] = round(t1 - t0, 3)
        report['realtime_factor'] = round((t1 - t0) / (w1 - w0), 4) if w1 > w0 else None
        report['clock_rate_hz'] = round(len(stamps.get('/clock', [])) / (w1 - w0), 1) \
            if w1 > w0 else None

    for topic, times in stamps.items():
        if topic == '/clock':
            continue
        entry = {'count': len(times), 'hz': round(len(times) / wall, 2) if wall else 0.0}
        gaps = sorted(b - a for a, b in zip(times, times[1:]))
        if gaps:
            entry['interval_mean_ms'] = round(1000 * sum(gaps) / len(gaps), 1)
            entry['interval_p95_ms'] = round(1000 * gaps[int(0.95 * (len(gaps) - 1))], 1)
            entry['interval_max_ms'] = round(1000 * gaps[-1], 1)
        report['topics'][topic] = entry

    clock = stamps.get('/clock', [])
    report['topics']['/clock'] = {
        'count': len(clock),
        'hz': round(len(clock) / wall, 2) if wall else 0.0}

    node.destroy_node()
    rclpy.shutdown()
    text = json.dumps(report, indent=1, ensure_ascii=False)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main()
