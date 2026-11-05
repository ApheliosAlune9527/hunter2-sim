"""Compare IMU-only throughput in a private, stationary Gazebo fixture.

Only the checked personal WSL environment is accepted. The original scene is
read but never changed. The vehicle and every other model are made static, all
vehicle plugins and non-IMU sensors are removed, and no command is published.
"""
import fcntl
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path('/mnt/d/rob-memory')
sys.path.insert(0, str(ROOT / 'sim/tools'))
from check_hunter_full_scene import check_scene
from check_ros_isolation import validate_environment
from full_scene_session import stop_owned_processes


def main():
    if sys.argv[1:]:
        raise ValueError('This benchmark takes no arguments')
    validate_environment(os.environ, Path('/proc/sys/kernel/osrelease').read_text(),
                         pwd.getpwuid(os.getuid()).pw_name)
    check_scene()
    lock = Path('/home/aphelios/hz_sim_ws/reports/.full_scene.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    token = uuid.uuid4().hex[:12]
    out = ROOT / 'outputs/hunter_imu_frequency_20261105/imu_only_trials' / token
    out.mkdir(parents=True)
    topic = '/hz_sim/imu_bench/t' + token + '/imu'
    tree = ET.parse(ROOT / 'sim/scenes/hz_hunter_full.sdf')
    world = tree.find('world')
    world.set('name', 'hz_imu_bench_' + token)
    for plugin in list(world.findall('plugin')):
        if plugin.get('name', '').endswith('::Sensors'):
            world.remove(plugin)
    for model in world.findall('model'):
        model.find('static').text = 'true'
        for plugin in list(model.findall('plugin')):
            model.remove(plugin)
        for link in model.findall('link'):
            for sensor in list(link.findall('sensor')):
                if sensor.get('name') != 'imu':
                    link.remove(sensor)
    imu = world.find("model[@name='hz_hunter_full']/link[@name='base_link']/sensor[@name='imu']")
    imu.find('topic').text = topic
    assert imu.findtext('update_rate') == '100'
    assert all(model.findtext('static') == 'true' and not model.findall('plugin')
               for model in world.findall('model'))
    assert len(world.findall('.//sensor')) == 1
    fixture = out / 'imu_only.sdf'
    tree.write(fixture, encoding='utf-8', xml_declaration=True)

    env = dict(os.environ, ROS_DOMAIN_ID='74', IGN_IP='127.0.0.1',
               IGN_PARTITION='hz_imu_bench_' + token)
    env.pop('IGN_RELAY', None)
    os.environ.update(env)
    processes, logs = [], []
    report = {'ok': False, 'all_models_static': True, 'robot_control_plugins': [],
              'hardware_driver_started': False, 'motion_published': False,
              'ros_domain': 74, 'partition': env['IGN_PARTITION'], 'topic': topic,
              'children': []}
    node = None

    def start(name, command):
        stream = (out / (name + '.log')).open('wb')
        logs.append(stream)
        process = subprocess.Popen(command, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        processes.append(process)
        report['children'].append({'name': name, 'pid': process.pid})

    try:
        import rclpy
        from rclpy.qos import qos_profile_sensor_data
        from sensor_msgs.msg import Imu
        rclpy.init(args=[])
        node = rclpy.create_node('imu_benchmark_' + token, use_global_arguments=False,
                                 enable_rosout=False, start_parameter_services=False)
        samples = []

        def receive(message):
            stamp = message.header.stamp
            samples.append((stamp.sec * 1000000000 + stamp.nanosec, time.monotonic_ns()))

        subscription = node.create_subscription(Imu, topic, receive, qos_profile_sensor_data)
        start('server', ['/usr/bin/ign', 'gazebo', '-s', '-r', '-v', '3', str(fixture)])
        start('bridge', ['/opt/ros/humble/lib/ros_gz_bridge/parameter_bridge',
                         topic + '@sensor_msgs/msg/Imu[ignition.msgs.IMU'])
        deadline = time.monotonic() + 35
        while len(samples) < 301 and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.1)
        if len(samples) < 301:
            raise ValueError('Fewer than 301 IMU messages received before deadline')
        sim_ns = samples[-1][0] - samples[0][0]
        wall_ns = samples[-1][1] - samples[0][1]
        intervals = [b[0] - a[0] for a, b in zip(samples, samples[1:])]
        if sim_ns <= 0 or wall_ns <= 0 or any(value <= 0 for value in intervals):
            raise ValueError('IMU timestamps did not increase')
        report.update(samples=len(samples), rate_sim_hz=(len(samples)-1)*1e9/sim_ns,
                      rate_wall_hz=(len(samples)-1)*1e9/wall_ns,
                      sim_duration_s=sim_ns/1e9, wall_duration_s=wall_ns/1e9,
                      realtime_factor=sim_ns/wall_ns,
                      min_interval_sim_ns=min(intervals), max_interval_sim_ns=max(intervals),
                      ros_command_publishers=len(node.get_publishers_info_by_topic('/hz_sim/full/cmd_vel')))
        if report['ros_command_publishers']:
            raise ValueError('Unexpected ROS command publisher')
        report['ok'] = 95 <= report['rate_sim_hz'] <= 105
    except Exception as error:
        report['error'] = repr(error)
    finally:
        if node is not None:
            node.destroy_node()
            import rclpy
            rclpy.shutdown()
        stop_owned_processes(processes, report)
        for stream in logs:
            stream.close()
        lock.close()
        (out / 'check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                                       encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['ok'] and report['cleanup_complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
