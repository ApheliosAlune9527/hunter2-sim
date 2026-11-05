"""Private all-static fixture for actual mapping-frame sensor observations."""
import fcntl
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

ROOT = Path('/mnt/f/rob-memory')
sys.path.insert(0, str(ROOT / 'sim/tools'))
from check_ros_isolation import validate_environment
from check_hunter_full_scene import check_scene
from check_full_ros_interfaces import check_interfaces


def close_owned(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGINT)
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=6)


def main():
    validate_environment(os.environ, Path('/proc/sys/kernel/osrelease').read_text(),
                         pwd.getpwuid(os.getuid()).pw_name)
    if sys.argv[1:]:
        raise ValueError('No arguments allowed')
    check_scene()
    check_interfaces()
    lock_file = Path('/home/aphelios/hz_sim_ws/reports/.full_scene.lock').open('a')
    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    token = uuid.uuid4().hex[:12]
    directory = ROOT / 'outputs/hunter_sensor_parameters_20261030/runtime' / token
    directory.mkdir(parents=True)
    tree = ET.parse(ROOT / 'sim/scenes/hz_hunter_full.sdf')
    world = tree.find('world')
    world.set('name', 'hz_hunter_full_static_' + token)
    # A diagnostic gravity vector checks the horizontal IMU axes. The production
    # world is untouched and every model in this private fixture is static.
    world.find('gravity').text = '1.2 -0.7 -9.81'
    robot = world.find("model[@name='hz_hunter_full']")
    robot.find('static').text = 'true'
    for plugin in list(robot.findall('plugin')):
        robot.remove(plugin)
    assert all(model.findtext('static') == 'true' for model in world.findall('model'))
    assert not robot.findall('plugin')
    assert not any(element.text == '/hz_sim/full/cmd_vel' for element in tree.findall('.//topic'))
    fixture = directory / 'static_full.sdf'
    tree.write(fixture, encoding='utf-8', xml_declaration=True)
    environment = dict(os.environ, ROS_DOMAIN_ID='74', IGN_IP='127.0.0.1',
                       IGN_PARTITION='hz_sim_aphelios_74_full_static_' + token)
    report = {'ok': False, 'all_models_static': True, 'robot_control_plugins': [],
              'velocity_published': False, 'partition': environment['IGN_PARTITION'],
              'ros_domain': environment['ROS_DOMAIN_ID'], 'report_directory': str(directory),
              'diagnostic_gravity_m_s2': [1.2, -.7, -9.81],
              'hardware_driver_started': False}
    processes = []
    logs = []

    def start(name, command):
        log = (directory / (name + '.log')).open('wb')
        logs.append(log)
        process = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        processes.append(process)
        return process

    try:
        start('ros_launch', ['/opt/ros/humble/bin/ros2', 'launch',
                             str(ROOT / 'sim/launch/hunter_full_ros.launch.py')])
        start('server', ['/usr/bin/ign', 'gazebo', '-s', '-r', '-v', '3', str(fixture)])
        native = start('native_observer', ['/home/aphelios/hz_sim_ws/tools/full_sensor_observer',
                                            '/hz_sim/full'])
        ros = start('ros_observer', ['/usr/bin/python3', '-B',
                                     str(ROOT / 'outputs/hunter_sensor_parameters_20261030/observe_mapping_ros.py'),
                                     str(directory)])
        ros.wait(timeout=58)
        native.wait(timeout=3)
        report['native_exit_code'] = native.returncode
        report['ros_exit_code'] = ros.returncode
        native_data = (directory / 'native_observer.log').read_text(encoding='utf-8')
        report['native'] = json.loads(native_data.strip()) if native_data.strip() else {}
        ros_receipt = directory / 'ros_check.json'
        report['ros'] = json.loads(ros_receipt.read_text(encoding='utf-8')) if ros_receipt.is_file() else {}
        report['ok'] = native.returncode == ros.returncode == 0 and report['native'].get('ok') and report['ros'].get('ok')
    except Exception as error:
        report['error'] = repr(error)
    finally:
        for process in reversed(processes):
            close_owned(process)
        for log in logs:
            log.close()
        report['owned_processes_closed'] = all(process.poll() is not None for process in processes)
        lock_file.close()
    (directory / 'check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
