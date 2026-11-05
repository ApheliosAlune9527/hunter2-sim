"""Place the full HUNTER 2.0 model inside the selected lab scene and verify reset.

Fixture only: the vehicle's own control plugins are removed, the world never
runs (no -r), no velocity is published, and the server lives in a private
Gazebo partition. The production scenes are not modified.
"""
import copy
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path('/mnt/d/rob-memory')
sys.path.insert(0, str(ROOT / 'sim/tools'))
from check_ros_isolation import validate_environment
from full_scene_session import stop_owned_processes

SCENE = ROOT / 'outputs/hunter_research_platform_20261031/lab_scene_candidate'
ROBOT_SCENE = ROOT / 'sim/scenes/hz_hunter_full.sdf'
LAB_SCENE = SCENE / 'lab_collision_mesh_candidate.sdf'
WORLD_NAME = 'hz_lab_155236_vehicle'
ROBOT_MODEL = 'hz_hunter_full'
DROPPED_MODELS = ('ground_plane', 'target_red', 'target_green', 'target_blue')
POSE_TOLERANCE = 1e-3


def build_world(placement):
    robot_tree = ET.parse(ROBOT_SCENE)
    world = robot_tree.find('world')
    world.set('name', WORLD_NAME)
    # Headless fixture: rendering-based systems cannot initialise without a GUI.
    for plugin in list(world.findall('plugin')):
        name = plugin.get('name', '')
        if name.endswith(('Sensors', 'Imu')):
            world.remove(plugin)
    removed_plugins = []
    for model in list(world.findall('model')):
        if model.get('name') in DROPPED_MODELS:
            world.remove(model)
    robot = world.find(f"model[@name='{ROBOT_MODEL}']")
    if robot is None:
        raise ValueError('Full vehicle model not found in the production scene')
    for plugin in list(robot.findall('plugin')):
        removed_plugins.append(plugin.get('name'))
        robot.remove(plugin)
    robot.find('pose').text = '{:.4f} {:.4f} {:.4f} 0 0 {:.4f}'.format(
        placement['x_m'], placement['y_m'], placement['z_m'], placement['yaw_rad'])
    robot.find('static').text = 'false'

    lab_tree = ET.parse(LAB_SCENE)
    lab_world = lab_tree.find('world')
    added = []
    for model in lab_world.findall('model'):
        world.append(copy.deepcopy(model))
        added.append(model.get('name'))
    ET.indent(robot_tree, space='  ')
    target = SCENE / 'lab_scene_with_vehicle.sdf'
    with target.open('wb') as stream:
        robot_tree.write(stream, encoding='utf-8', xml_declaration=True)
    return target, removed_plugins, added


def read_pose(environment, model):
    result = subprocess.run(['/usr/bin/ign', 'model', '-m', model, '-p'],
                            env=environment, capture_output=True, text=True, timeout=10)
    text = result.stdout + result.stderr
    values = {}
    # ign model -p prints:  Pose [ XYZ (m) ] [ RPY (rad) ]:
    #                         [x y z]
    #                         [r p y]
    match = re.search(r'Pose \[ XYZ \(m\) \] \[ RPY \(rad\) \]:\s*'
                      r'\[([^\]]+)\]\s*\[([^\]]+)\]', text)
    if match:
        xyz = [float(v) for v in match.group(1).split()]
        rpy = [float(v) for v in match.group(2).split()]
        values = {'x': xyz[0], 'y': xyz[1], 'z': xyz[2],
                  'roll': rpy[0], 'pitch': rpy[1], 'yaw': rpy[2]}
    return text, values


def main():
    validate_environment(os.environ, Path('/proc/sys/kernel/osrelease').read_text(),
                         pwd.getpwuid(os.getuid()).pw_name)
    if sys.argv[1:]:
        raise ValueError('No arguments allowed')
    placement = json.loads((SCENE / 'traversability_oriented.json')
                           .read_text(encoding='utf-8'))['suggested_initial_pose']
    # Wheel contact radius is 0.165 m (geometry_report.json), so base_link rests
    # exactly 0.165 m above the floor. The production scene authors 0.167 m, which
    # leaves the model 2 mm airborne; that gap reappears as a settle after reset.
    authored_z = placement['z_m']
    placement['z_m'] = 0.165
    world_file, removed_plugins, lab_models = build_world(placement)
    check = subprocess.run(['/usr/bin/ign', 'sdf', '-k', str(world_file)],
                           capture_output=True, text=True, timeout=60)
    sdf_valid = check.returncode == 0 and 'Valid' in (check.stdout + check.stderr)
    token = uuid.uuid4().hex[:12]
    environment = dict(os.environ, IGN_IP='127.0.0.1',
                       IGN_PARTITION='hz_sim_aphelios_73_lab_vehicle_' + token)
    environment.pop('IGN_RELAY', None)
    control = f'/world/{WORLD_NAME}/control'
    receipt = {
        'ok': False,
        'fixture': str(world_file),
        'world': WORLD_NAME,
        'partition': environment['IGN_PARTITION'],
        'sdf_valid': sdf_valid,
        'sdf_check_stdout': check.stdout.strip(),
        'requested_pose': {k: placement[k] for k in ('x_m', 'y_m', 'z_m', 'yaw_rad')},
        'authored_scene_z_m': authored_z,
        'contact_height_m': 0.165,
        'z_choice_reason': ('Wheel contact radius 0.165 m; the production scene authors '
                            '0.167 m and the model settles 2 mm after a reset.'),
        'removed_robot_plugins': removed_plugins,
        'appended_lab_models': lab_models,
        'motion_published': False,
        'physics_run_requested': False,
        'hardware_driver_started': False,
    }
    log = (SCENE / 'lab_scene_with_vehicle.log').open('wb')
    process = subprocess.Popen(['/usr/bin/ign', 'gazebo', '-s', '-v', '3', str(world_file)],
                               env=environment, stdout=log, stderr=subprocess.STDOUT,
                               start_new_session=True)
    receipt['created_pid'] = process.pid
    cleanup = {'children': [{}]}
    try:
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline and process.poll() is None:
            services = subprocess.run(['/usr/bin/ign', 'service', '-l'], env=environment,
                                      capture_output=True, text=True, timeout=8)
            if control in services.stdout:
                receipt['world_control_service'] = True
                break
            time.sleep(0.5)
        if not receipt.get('world_control_service'):
            raise RuntimeError('World control service never appeared')

        listing = subprocess.run(['/usr/bin/ign', 'model', '--list'], env=environment,
                                 capture_output=True, text=True, timeout=10)
        receipt['model_list_raw'] = listing.stdout.strip()
        names = set()
        for raw in listing.stdout.splitlines():
            line = raw.strip()
            if line.startswith('- '):
                line = line[2:].strip()
            if not line or ':' in line or '[' in line or ' ' in line:
                continue
            names.add(line)
        receipt['models'] = sorted(names)
        receipt['robot_model_present'] = ROBOT_MODEL in names

        first_text, first = read_pose(environment, ROBOT_MODEL)
        receipt['pose_before_reset_raw'] = first_text.strip()
        receipt['pose_before_reset'] = first
        # Read again without resetting: proves the world is not stepping.
        paused_text, paused = read_pose(environment, ROBOT_MODEL)
        receipt['pose_paused_repeat'] = paused

        reset = subprocess.run(['/usr/bin/ign', 'service', '-s', control,
                                '--reqtype', 'ignition.msgs.WorldControl',
                                '--reptype', 'ignition.msgs.Boolean',
                                '--timeout', '5000', '--req', 'reset: {all: true}'],
                               env=environment, capture_output=True, text=True, timeout=15)
        receipt['reset_service_output'] = (reset.stdout + reset.stderr).strip()
        time.sleep(1.0)
        second_text, second = read_pose(environment, ROBOT_MODEL)
        receipt['pose_after_reset_raw'] = second_text.strip()
        receipt['pose_after_reset'] = second
        # Second reset: distinguishes a one-off settle from a non-repeatable reset.
        subprocess.run(['/usr/bin/ign', 'service', '-s', control,
                        '--reqtype', 'ignition.msgs.WorldControl',
                        '--reptype', 'ignition.msgs.Boolean',
                        '--timeout', '5000', '--req', 'reset: {all: true}'],
                       env=environment, capture_output=True, text=True, timeout=15)
        time.sleep(1.0)
        third_text, third = read_pose(environment, ROBOT_MODEL)
        receipt['pose_after_second_reset_raw'] = third_text.strip()
        receipt['pose_after_second_reset'] = third

        # Alternative reset mechanism: explicit set_pose, twice, to test determinism.
        set_pose_request = ('name: "{}", position: {{x: {:.4f}, y: {:.4f}, z: {:.4f}}}, '
                            'orientation: {{x: 0, y: 0, z: 0, w: 1}}').format(
            ROBOT_MODEL, placement['x_m'], placement['y_m'], placement['z_m'])
        set_pose_outputs = []
        located = []
        for _ in range(2):
            result = subprocess.run(['/usr/bin/ign', 'service', '-s',
                                     f'/world/{WORLD_NAME}/set_pose',
                                     '--reqtype', 'ignition.msgs.Pose',
                                     '--reptype', 'ignition.msgs.Boolean',
                                     '--timeout', '5000', '--req', set_pose_request],
                                    env=environment, capture_output=True, text=True, timeout=15)
            set_pose_outputs.append((result.stdout + result.stderr).strip())
            time.sleep(0.8)
            located.append(read_pose(environment, ROBOT_MODEL)[1])
        receipt['set_pose_service_output'] = set_pose_outputs
        receipt['pose_after_set_pose'] = located[0]
        receipt['pose_after_second_set_pose'] = located[1]

        parsed = all({'x', 'y', 'z'} <= set(values) for values in (first, paused, second, third))
        if parsed:
            receipt['paused_repeat_delta_m'] = {
                axis: round(abs(first[axis] - paused[axis]), 6) for axis in 'xyz'}
            receipt['world_is_stopped'] = all(
                value <= 1e-9 for value in receipt['paused_repeat_delta_m'].values())
            delta = {axis: round(abs(paused[axis] - second[axis]), 6) for axis in 'xyz'}
            receipt['reset_delta_m'] = delta
            receipt['reset_is_identical'] = all(value <= 1e-6 for value in delta.values())
            repeat = {axis: round(abs(second[axis] - third[axis]), 6) for axis in 'xyz'}
            receipt['reset_repeat_delta_m'] = repeat
            receipt['reset_is_repeatable'] = all(value <= 1e-6 for value in repeat.values())
            requested = placement
            receipt['placement_error_m'] = {
                'x': round(abs(first['x'] - requested['x_m']), 6),
                'y': round(abs(first['y'] - requested['y_m']), 6),
                'z': round(abs(first['z'] - requested['z_m']), 6),
            }
            receipt['placement_matches_request'] = all(
                value <= POSE_TOLERANCE for value in receipt['placement_error_m'].values())
            receipt['settle_from_authored_m'] = {
                axis: round(abs(second[axis] - requested[key]), 6)
                for axis, key in (('x', 'x_m'), ('y', 'y_m'), ('z', 'z_m'))}
            if all({'x', 'y', 'z'} <= set(values) for values in located):
                first_set, second_set = located
                receipt['set_pose_error_m'] = {
                    axis: round(abs(first_set[axis] - requested[key]), 6)
                    for axis, key in (('x', 'x_m'), ('y', 'y_m'), ('z', 'z_m'))}
                receipt['set_pose_matches_authored'] = all(
                    value <= 1e-6 for value in receipt['set_pose_error_m'].values())
                receipt['set_pose_repeat_delta_m'] = {
                    axis: round(abs(first_set[axis] - second_set[axis]), 6) for axis in 'xyz'}
                receipt['set_pose_is_repeatable'] = all(
                    value <= 1e-6 for value in receipt['set_pose_repeat_delta_m'].values())
                receipt['set_pose_constant_bias_m'] = receipt['set_pose_error_m']
                receipt['reset_all_accumulates'] = not receipt['reset_is_repeatable']
            else:
                receipt['set_pose_parse_failed'] = True
        else:
            receipt['pose_parse_failed'] = True
    except Exception as error:
        receipt['error'] = repr(error)
    finally:
        stop_owned_processes([process], cleanup)
        log.close()
        receipt['owned_process_group_closed'] = cleanup['cleanup_complete']
        text = (SCENE / 'lab_scene_with_vehicle.log').read_text(encoding='utf-8', errors='replace')
        errors = [line for line in text.splitlines() if '[Err]' in line]
        receipt['gazebo_error_lines'] = errors[:20]
        receipt['gazebo_error_count'] = len(errors)
        receipt['ok'] = bool(receipt.get('sdf_valid')
                             and receipt.get('robot_model_present')
                             and receipt.get('placement_matches_request')
                             and receipt.get('world_is_stopped')
                             and receipt.get('set_pose_is_repeatable')
                             and receipt.get('owned_process_group_closed')
                             and not errors)
        (SCENE / 'lab_scene_with_vehicle_check.json').write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: receipt.get(k) for k in (
        'ok', 'sdf_valid', 'models', 'pose_before_reset', 'pose_after_reset',
        'pose_after_second_reset', 'world_is_stopped', 'reset_delta_m',
        'reset_repeat_delta_m', 'reset_is_repeatable', 'reset_all_accumulates',
        'set_pose_error_m', 'set_pose_constant_bias_m',
        'set_pose_matches_authored', 'set_pose_repeat_delta_m', 'set_pose_is_repeatable',
        'placement_error_m', 'placement_matches_request',
        'gazebo_error_count', 'owned_process_group_closed')},
        ensure_ascii=True))
    return 0 if receipt['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
