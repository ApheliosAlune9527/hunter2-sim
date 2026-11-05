"""Check existing RGB intrinsics in a private, all-static Gazebo scene.

This probe starts an isolated observation-only ROS bridge, publishes no control
messages, and terminates only subprocesses it creates itself.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

import yaml


ROOT = Path('/mnt/f/rob-memory')
SOURCE = ROOT / 'robot_assets/car_sensor_config_20261030/camera_d435i_640x480.yaml'
EXPECTED_SHA256 = '790333f3aa749400429f27d0fa0838662dc8c65e5ad6e64b96dfa9de8d183daf'


def main():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != EXPECTED_SHA256:
        raise ValueError('Camera source changed after transfer')
    data = yaml.safe_load(SOURCE.read_text(encoding='utf-8'))['/**']['ros__parameters']['camera']
    if (data['width'], data['height'], data['model']) != (640, 480, 'Pinhole'):
        raise ValueError('Unexpected source camera model')
    token = uuid.uuid4().hex[:12]
    directory = ROOT / 'outputs/hunter_sensor_parameters_20261030/probes' / token
    directory.mkdir(parents=True)
    tree = ET.parse(ROOT / 'sim/scenes/hz_hunter_full.sdf')
    world = tree.find('world')
    world.set('name', 'hz_camera_intrinsics_probe_' + token)
    robot = world.find("model[@name='hz_hunter_full']")
    robot.find('static').text = 'true'
    for plugin in list(robot.findall('plugin')):
        robot.remove(plugin)
    base = robot.find("link[@name='base_link']")
    for sensor in list(base.findall('sensor')):
        if sensor.get('name') != 'camera':
            base.remove(sensor)
    sensor = base.find("sensor[@name='camera']")
    diagnostic_hidden = os.environ.get('HZ_DIAGNOSTIC_HIDE_VISUAL', '')
    if diagnostic_hidden:
        names = set(diagnostic_hidden.split(','))
        available = {v.get('name'): v for v in base.findall('visual')}
        if not names <= set(available):
            raise ValueError('Unknown private diagnostic visual')
        for name in names:
            base.remove(available[name])
    diagnostic_shift = os.environ.get('HZ_DIAGNOSTIC_SHIFT_CAMERA_VISUAL', '')
    if diagnostic_shift:
        delta = [float(v) for v in diagnostic_shift.split()]
        if len(delta) != 3 or not all(math.isfinite(v) for v in delta):
            raise ValueError('Invalid private diagnostic visual shift')
        visual = base.find("visual[@name='base_link_fixed_joint_lump__camera_link_visual_5']")
        pose = [float(v) for v in visual.findtext('pose').split()]
        visual.find('pose').text = ' '.join(str(pose[i] + (delta[i] if i < 3 else 0))
                                            for i in range(6))
    model_pose = [float(v) for v in robot.findtext('pose').split()]
    camera_pose = [float(v) for v in sensor.findtext('pose').split()]
    diagnostic_pose = os.environ.get('HZ_DIAGNOSTIC_CAMERA_POSE')
    if diagnostic_pose:
        camera_pose = [float(v) for v in diagnostic_pose.split()]
        if len(camera_pose) != 6 or not all(math.isfinite(v) for v in camera_pose):
            raise ValueError('Invalid private diagnostic camera pose')
        sensor.find('pose').text = ' '.join(str(v) for v in camera_pose)
    target = world.find("model[@name='target_red']")
    target_pose = [float(v) for v in target.findtext('pose').split()]
    target_size = [float(v) for v in target.findtext('.//visual/geometry/box/size').split()]
    if any(abs(v) > 1e-8 for v in model_pose[3:] + camera_pose[3:] + target_pose[3:]):
        raise ValueError('Projection test assumes axis-aligned target and camera')
    camera_world = [model_pose[i] + camera_pose[i] for i in range(3)]
    sensor.find('topic').text = '/hz_camera_probe/camera'
    sensor.find('ignition_frame_id').text = 'hz_camera_probe/camera_optical_frame'
    camera = sensor.find('camera')
    diagnostic_masked = os.environ.get('HZ_DIAGNOSTIC_MASK_VISUAL', '')
    if diagnostic_masked:
        visual = base.find("visual[@name='" + diagnostic_masked + "']")
        if visual is None:
            raise ValueError('Unknown private diagnostic masked visual')
        ET.SubElement(visual, 'visibility_flags').text = '2'
        ET.SubElement(camera, 'visibility_mask').text = '1'
    expected_fov = 2 * math.atan(data['width'] / (2 * data['fx']))
    if abs(float(camera.findtext('horizontal_fov')) - expected_fov) > 1e-12:
        raise ValueError('Production scene does not contain the verified horizontal field of view')
    if camera.find('lens') is not None:
        raise ValueError('Unexpected unsupported custom projection in production scene')
    assert all(model.findtext('static') == 'true' for model in world.findall('model'))
    assert not robot.findall('plugin')
    assert not any(node.text and 'cmd_vel' in node.text for node in tree.findall('.//topic'))
    scene = directory / 'static_probe.sdf'
    tree.write(scene, encoding='utf-8', xml_declaration=True)
    partition = 'hz_camera_probe_' + token
    env = dict(os.environ, IGN_PARTITION=partition, ROS_DOMAIN_ID='74', ROS_LOCALHOST_ONLY='1')
    result = {
        'ok': False, 'source_sha256': EXPECTED_SHA256,
        'requested': {key: data[key] for key in ('fx', 'fy', 'cx', 'cy')},
        'world_all_static': True, 'robot_control_plugins': [],
        'ros_domain': 74, 'ros_bridge_direction': 'GZ_TO_ROS',
        'hardware_driver_started': False, 'motion_published': False,
        'ign_partition': partition,
        'diagnostic_pose_override': diagnostic_pose,
        'diagnostic_hidden_visuals': diagnostic_hidden,
        'diagnostic_masked_visual': diagnostic_masked,
        'diagnostic_camera_visual_shift_m': diagnostic_shift,
    }
    log = (directory / 'server.log').open('wb')
    server = None
    observer = None
    bridge = None
    ros_observer = None
    bridge_log = (directory / 'ros_bridge.log').open('wb')
    try:
        check = subprocess.run(['/usr/bin/ign', 'sdf', '-k', str(scene)],
                               env=env, capture_output=True, text=True, timeout=20)
        result['sdf_valid'] = check.returncode == 0 and 'Valid' in check.stdout
        if not result['sdf_valid']:
            raise ValueError('SDF invalid: ' + check.stdout[-1000:] + check.stderr[-1000:])
        server = subprocess.Popen(['/usr/bin/ign', 'gazebo', '-s', '-r', '-v', '3', str(scene)],
                                  env=env, stdout=log, stderr=subprocess.STDOUT,
                                  start_new_session=True)
        bridge_config = directory / 'private_bridge.json'
        bridge_config.write_text(json.dumps([{
            'ros_topic_name': '/hz_camera_probe/camera/camera_info',
            'gz_topic_name': '/hz_camera_probe/camera/camera_info',
            'ros_type_name': 'sensor_msgs/msg/CameraInfo',
            'gz_type_name': 'ignition.msgs.CameraInfo', 'direction': 'GZ_TO_ROS',
            'lazy': False, 'publisher_queue': 2, 'subscriber_queue': 2,
        }]), encoding='utf-8')
        bridge = subprocess.Popen(['/opt/ros/humble/bin/ros2', 'run', 'ros_gz_bridge',
                                   'parameter_bridge', '--ros-args', '-p',
                                   'config_file:=' + str(bridge_config)], env=env,
                                  stdout=bridge_log, stderr=subprocess.STDOUT,
                                  start_new_session=True)
        ros_observer = subprocess.Popen(['/usr/bin/python3', '-B',
                            str(ROOT / 'outputs/hunter_sensor_parameters_20261030/camera_ros_observer.py')],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
        observer = subprocess.Popen([str(ROOT / 'outputs/hunter_sensor_parameters_20261030/camera_projection_observer')],
                                    env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, start_new_session=True)
        deadline = time.monotonic() + 40
        sample = ''
        while time.monotonic() < deadline and server.poll() is None:
            try:
                observation = subprocess.run(['/usr/bin/ign', 'topic', '-e', '-n', '1', '-t',
                                              '/hz_camera_probe/camera/camera_info'],
                                             env=env, capture_output=True, text=True, timeout=4)
                if observation.returncode == 0 and 'intrinsics' in observation.stdout:
                    sample = observation.stdout
                    break
            except subprocess.TimeoutExpired:
                pass
        if not sample:
            raise TimeoutError('No camera info arrived')
        (directory / 'camera_info.txt').write_text(sample, encoding='utf-8')
        result['camera_info_received'] = True
        blocks = {}
        for name, field in (('intrinsics', 'k'), ('projection', 'p')):
            match = re.search(r'\b' + name + r'\s*\{(.*?)\}', sample, re.S)
            if not match:
                raise ValueError('Missing camera matrix: ' + name)
            blocks[name] = [float(value) for value in re.findall(r'\b' + field + r':\s*([-+\deE.]+)', match.group(1))]
        # Ogre1 uses a centered, square-pixel projection for this RGBD camera.
        # Fit the source horizontal focal length and report the actual model.
        fx, fy, cx, cy = data['fx'], data['fx'], data['width'] / 2, data['height'] / 2
        expected_k = [fx, 0, cx, 0, fy, cy, 0, 0, 1]
        expected_p = [fx, 0, cx, 0, 0, fy, cy, 0, 0, 0, 1, 0]
        if len(blocks['intrinsics']) != 9 or len(blocks['projection']) != 12:
            raise ValueError('Unexpected camera matrix size')
        if any(abs(x - y) > 1e-6 for x, y in zip(blocks['intrinsics'], expected_k)):
            raise ValueError('Camera intrinsic matrix does not match the fitted model')
        if any(abs(x - y) > 1e-6 for x, y in zip(blocks['projection'], expected_p)):
            raise ValueError('Camera projection matrix does not match the fitted model')
        result['camera_matrices'] = blocks
        stdout, stderr = observer.communicate(timeout=30)
        if observer.returncode != 0:
            raise ValueError('Camera image observer failed: ' + stderr[-1000:])
        observed = json.loads(stdout)
        # The center of the near face of the known red target in this fixture.
        distance = target_pose[0] - target_size[0] / 2 - camera_world[0]
        if distance <= 0:
            raise ValueError('Projection target is not in front of the camera')
        expected_xy = [cx - fx * ((target_pose[1] - camera_world[1]) / distance),
                       cy - fy * ((target_pose[2] - camera_world[2]) / distance)]
        actual_xy = [observed['centroid_x'], observed['centroid_y']]
        result['image_red_target'] = {'observed_pixel': actual_xy,
                                      'expected_pixel': expected_xy,
                                      'red_pixels': observed['red_pixels']}
        if any(abs(a - b) > 2 for a, b in zip(actual_xy, expected_xy)):
            raise ValueError('Rendered image does not match the fitted model')
        result['approximation'] = {'fx': fx, 'fy': fy, 'cx': cx, 'cy': cy,
                                   'depth_uses_same_approximation': True}
        stdout, stderr = ros_observer.communicate(timeout=40)
        if ros_observer.returncode != 0:
            raise ValueError('Private ROS camera observer failed: ' + stderr[-1500:])
        result['ros_camera_info'] = json.loads(stdout)
        result['ok'] = True
    except Exception as error:
        result['error'] = repr(error)
    finally:
        for owned in (ros_observer, bridge):
            if owned is not None and owned.poll() is None:
                os.killpg(owned.pid, signal.SIGTERM)
                owned.wait(timeout=6)
        if observer is not None and observer.poll() is None:
            os.killpg(observer.pid, signal.SIGTERM)
            observer.wait(timeout=6)
        if server is not None and server.poll() is None:
            os.killpg(server.pid, signal.SIGINT)
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(server.pid, signal.SIGTERM)
                server.wait(timeout=6)
        log.close()
        bridge_log.close()
        result['owned_server_closed'] = server is None or server.poll() is not None
        result['owned_processes_closed'] = all(p is None or p.poll() is not None
                                               for p in (server, observer, bridge, ros_observer))
    (directory / 'check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
