"""Validate a generated scene: SDF syntax, headless load, model list, start pose."""
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import time
import uuid

ROOT = Path('/mnt/d/rob-memory')
sys.path.insert(0, str(ROOT / 'sim/tools'))
from check_ros_isolation import validate_environment
from full_scene_session import stop_owned_processes

SCENE = ROOT / 'outputs/lab_scene_odom06_20261105'
SDF = SCENE / 'lab_scene_2d.sdf'
MANIFEST = SCENE / 'scene_manifest.json'
WORLD = 'hz_lab_2d'
ROBOT = 'hz_hunter_full'


def read_pose(environment, model):
    result = subprocess.run(['/usr/bin/ign', 'model', '-m', model, '-p'],
                            env=environment, capture_output=True, text=True, timeout=10)
    text = result.stdout + result.stderr
    match = re.search(r'Pose \[ XYZ \(m\) \] \[ RPY \(rad\) \]:\s*'
                      r'\[([^\]]+)\]\s*\[([^\]]+)\]', text)
    if not match:
        return text, {}
    xyz = [float(v) for v in match.group(1).split()]
    rpy = [float(v) for v in match.group(2).split()]
    return text, {'x': xyz[0], 'y': xyz[1], 'z': xyz[2],
                  'roll': rpy[0], 'pitch': rpy[1], 'yaw': rpy[2]}


def main():
    validate_environment(os.environ, Path('/proc/sys/kernel/osrelease').read_text(),
                         pwd.getpwuid(os.getuid()).pw_name)
    if sys.argv[1:]:
        raise ValueError('No arguments allowed')
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    start = manifest['vehicle_start']
    check = subprocess.run(['/usr/bin/ign', 'sdf', '-k', str(SDF)],
                           capture_output=True, text=True, timeout=120)
    token = uuid.uuid4().hex[:12]
    environment = dict(os.environ, IGN_IP='127.0.0.1',
                       IGN_PARTITION='hz_sim_aphelios_73_lab2d_' + token)
    environment.pop('IGN_RELAY', None)
    control = '/world/%s/control' % WORLD
    receipt = {
        'ok': False, 'scene': str(SDF), 'world': WORLD, 'partition': environment['IGN_PARTITION'],
        'sdf_exit_code': check.returncode,
        'sdf_output': (check.stdout + check.stderr).strip()[:400],
        'requested_start': start, 'motion_published': False, 'physics_run_requested': False,
    }
    log = (SCENE / 'scene_load.log').open('wb')
    process = subprocess.Popen(['/usr/bin/ign', 'gazebo', '-s', '-v', '3', str(SDF)],
                               env=environment, stdout=log, stderr=subprocess.STDOUT,
                               start_new_session=True)
    receipt['created_pid'] = process.pid
    cleanup = {'children': [{}]}
    try:
        deadline = time.monotonic() + 60
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
        names = set()
        for raw in listing.stdout.splitlines():
            line = raw.strip()
            if line.startswith('- '):
                line = line[2:].strip()
            if not line or ':' in line or '[' in line or ' ' in line:
                continue
            names.add(line)
        receipt['models'] = sorted(names)
        receipt['robot_model_present'] = ROBOT in names
        text, pose = read_pose(environment, ROBOT)
        receipt['pose_raw'] = text.strip()
        receipt['pose'] = pose
        if pose:
            receipt['placement_error_m'] = {
                'x': round(abs(pose['x'] - start['x']), 6),
                'y': round(abs(pose['y'] - start['y']), 6),
                'z': round(abs(pose['z'] - start['z']), 6)}
            receipt['placement_matches'] = all(
                v <= 1e-3 for v in receipt['placement_error_m'].values())
    except Exception as error:
        receipt['error'] = repr(error)
    finally:
        stop_owned_processes([process], cleanup)
        log.close()
        receipt['owned_process_group_closed'] = cleanup['cleanup_complete']
        text = (SCENE / 'scene_load.log').read_text(encoding='utf-8', errors='replace')
        errors = [line for line in text.splitlines() if '[Err]' in line]
        receipt['gazebo_error_lines'] = errors[:20]
        receipt['gazebo_error_count'] = len(errors)
        receipt['ok'] = bool(receipt.get('sdf_exit_code') == 0
                             and receipt.get('robot_model_present')
                             and receipt.get('placement_matches')
                             and receipt.get('owned_process_group_closed')
                             and not errors)
        (SCENE / 'scene_load_check.json').write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: receipt.get(k) for k in (
        'ok', 'sdf_exit_code', 'models', 'pose', 'placement_error_m',
        'gazebo_error_count', 'owned_process_group_closed')}, ensure_ascii=True))
    return 0 if receipt['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
