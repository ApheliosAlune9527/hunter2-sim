"""Run an all-static sensor compatibility fixture; it has no vehicle/control."""
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

sys.path.insert(0, '/mnt/f/rob-memory/sim/tools')
from check_ros_isolation import validate_environment


WORLD = '''<sdf version="1.9"><world name="hz_sensor_probe">
<physics name="physics" type="ignored"><max_step_size>0.001</max_step_size><real_time_factor>1</real_time_factor></physics>
<gravity>0 0 -9.81</gravity>
<plugin filename="ignition-gazebo-physics-system" name="ignition::gazebo::systems::Physics"/>
<plugin filename="ignition-gazebo-user-commands-system" name="ignition::gazebo::systems::UserCommands"/>
<plugin filename="ignition-gazebo-scene-broadcaster-system" name="ignition::gazebo::systems::SceneBroadcaster"/>
<plugin filename="ignition-gazebo-sensors-system" name="ignition::gazebo::systems::Sensors"><render_engine>{engine}</render_engine></plugin>
<plugin filename="ignition-gazebo-imu-system" name="ignition::gazebo::systems::Imu"/>
<scene><ambient>0.7 0.7 0.7 1</ambient><background>0.2 0.3 0.4 1</background></scene>
<light type="directional" name="sun"><pose>0 0 10 0 0 0</pose><diffuse>1 1 1 1</diffuse><direction>-0.5 0.2 -1</direction></light>
<model name="rig"><static>true</static><pose>0 0 1 0 0 0</pose><link name="rig_link">
<sensor name="lidar" type="gpu_lidar"><topic>/hz_probe/lidar</topic><ignition_frame_id>hz_sim/full/hesai_lidar</ignition_frame_id><always_on>true</always_on><update_rate>10</update_rate>
<lidar><scan><horizontal><samples>360</samples><resolution>1</resolution><min_angle>-3.14159265359</min_angle><max_angle>3.14159265359</max_angle></horizontal>
<vertical><samples>4</samples><resolution>1</resolution><min_angle>-0.2</min_angle><max_angle>0.2</max_angle></vertical></scan>
<range><min>0.1</min><max>20</max><resolution>0.01</resolution></range></lidar></sensor>
<sensor name="camera" type="rgbd_camera"><topic>/hz_probe/camera</topic><ignition_frame_id>hz_sim/full/camera_optical_frame</ignition_frame_id><always_on>true</always_on><update_rate>5</update_rate>
<camera><horizontal_fov>1.2</horizontal_fov><image><width>160</width><height>120</height><format>R8G8B8</format></image><clip><near>0.1</near><far>20</far></clip></camera></sensor>
<sensor name="imu" type="imu"><topic>/hz_probe/imu</topic><ignition_frame_id>hz_sim/full/imu_link</ignition_frame_id><always_on>true</always_on><update_rate>50</update_rate></sensor>
</link></model>
<model name="obstacle"><static>true</static><pose>2 0 1 0 0 0</pose><link name="body"><collision name="collision"><geometry><box><size>0.5 1 1</size></box></geometry></collision><visual name="visual"><geometry><box><size>0.5 1 1</size></box></geometry><material><ambient>0.8 0.1 0.1 1</ambient><diffuse>0.8 0.1 0.1 1</diffuse></material></visual></link></model>
<model name="ground"><static>true</static><link name="ground"><collision name="collision"><geometry><plane><normal>0 0 1</normal><size>20 20</size></plane></geometry></collision><visual name="visual"><geometry><plane><normal>0 0 1</normal><size>20 20</size></plane></geometry></visual></link></model>
</world></sdf>'''


def main():
    validate_environment(os.environ, Path('/proc/sys/kernel/osrelease').read_text(),
                         pwd.getpwuid(os.getuid()).pw_name)
    if sys.argv[1:] not in [['ogre'], ['ogre2']]:
        raise SystemExit('Choose one installed render engine')
    engine = sys.argv[1]
    token = uuid.uuid4().hex[:12]
    output = Path('/mnt/f/rob-memory/outputs/hunter_model_upgrade_20261030/references/sensor_probe') / token
    output.mkdir(parents=True)
    xml = WORLD.format(engine=engine)
    root = ET.fromstring(xml)
    assert all(m.findtext('static') == 'true' for m in root.findall('world/model'))
    assert not root.findall('.//joint') and 'Ackermann' not in xml and 'cmd_vel' not in xml
    world = output / 'probe.sdf'
    world.write_text(xml)
    environment = dict(os.environ, IGN_PARTITION='hz_sim_aphelios_73_test_' + token)
    report = {'engine': engine, 'all_models_static': True, 'vehicle_loaded': False,
              'velocity_published': False, 'partition': environment['IGN_PARTITION'],
              'report_directory': str(output)}
    with (output / 'server.log').open('wb') as log:
        process = subprocess.Popen(['/usr/bin/ign', 'gazebo', '-s', '-r', '-v', '3', str(world)],
                                   env=environment, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            result = subprocess.run(['/home/aphelios/hz_sim_ws/tools/full_sensor_observer', '/hz_probe'],
                                    env=environment, capture_output=True, text=True, timeout=28)
            (output / 'observer.stdout.txt').write_text(result.stdout)
            (output / 'observer.stderr.txt').write_text(result.stderr)
            report['observer_exit_code'] = result.returncode
            report['sensors'] = json.loads(result.stdout) if result.stdout.strip() else {}
            report['ok'] = result.returncode == 0 and report['sensors'].get('ok') is True
            topics = subprocess.run(['/usr/bin/ign', 'topic', '-l'], env=environment,
                                    capture_output=True, text=True, timeout=5)
            (output / 'topics.txt').write_text(topics.stdout + topics.stderr)
        except Exception as error:
            report['ok'] = False
            report['error'] = str(error)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
            report['owned_launcher_closed'] = process.poll() is not None
    (output / 'check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
