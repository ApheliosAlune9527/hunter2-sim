"""Build only the new personal data package and parse its URDF; no simulation."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path('/mnt/f/rob-memory')
sys.path.insert(0, str(ROOT / 'sim/tools'))
from check_ros_isolation import validate_environment


def main():
    validate_environment(os.environ, Path('/proc/sys/kernel/osrelease').read_text(),
                         pwd.getpwuid(os.getuid()).pw_name)
    if sys.argv[1:]:
        raise ValueError('No arguments accepted')
    source = ROOT / 'sim/hz_hunter_full_description'
    manifest = json.loads((source / 'source_manifest.json').read_text())
    for entry in manifest['outputs']:
        filename = source / entry['path']
        if not filename.resolve().is_relative_to(source.resolve()):
            raise ValueError('Output path escapes the new data package')
        if hashlib.sha256(filename.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('Source package hash mismatch: ' + str(filename))
    workspace = Path('/home/aphelios/hz_sim_ws')
    destination = workspace / 'src/hz_hunter_full_description'
    if destination.is_symlink() or destination.resolve() != destination:
        raise ValueError('Unexpected personal package path')
    if destination.exists() and not (destination / 'source_manifest.json').is_file():
        raise ValueError('Unknown existing package; refusing to replace it')
    shutil.copytree(source, destination, dirs_exist_ok=True)
    output = ROOT / 'outputs/hunter_model_upgrade_20261030/references/ament'
    output.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(['colcon', 'build', '--symlink-install', '--packages-select',
                             'hz_hunter_full_description'], cwd=workspace,
                            capture_output=True, text=True, timeout=90)
    (output / 'build.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    robot = ET.parse(source / 'urdf/hunter_full.urdf').getroot()
    # Preserve the original URDF/RSP frame tree. For physics, lump fixed links:
    # no almost-massless fixed sensor bodies need to be integrated separately.
    for extension in list(robot.findall('gazebo')):
        if extension.find('preserveFixedJoint') is not None:
            robot.remove(extension)
    flat_input = output / 'hunter_full_lump_input.urdf'
    ET.ElementTree(robot).write(flat_input, encoding='utf-8', xml_declaration=True)
    parsed = subprocess.run(['/usr/bin/ign', 'sdf', '-p', str(flat_input)],
                            capture_output=True, text=True, timeout=25)
    (output / 'sdf_convert.stderr.txt').write_text(parsed.stderr)
    if parsed.returncode:
        raise RuntimeError('URDF to SDF failed: ' + parsed.stderr)
    sdf = ET.fromstring(parsed.stdout)
    model = sdf.find('model')
    if model is None or len(model.findall('joint')) != 6 or len(model.findall('link')) != 7:
        raise ValueError('Fixed-joint lumping did not preserve the six active joints')
    (output / 'hunter_full.converted.sdf').write_text(parsed.stdout)
    check = subprocess.run(['/usr/bin/ign', 'sdf', '-k', str(output / 'hunter_full.converted.sdf')],
                           capture_output=True, text=True, timeout=25)
    report = {'ok': check.returncode == 0, 'build_exit_code': result.returncode,
              'sdf_check_exit_code': check.returncode, 'sdf_check_output': check.stdout + check.stderr,
              'physical_links': len(model.findall('link')), 'active_joints': len(model.findall('joint')),
              'simulator_started': False, 'hardware_driver_started': False,
              'velocity_published': False}
    (output / 'check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
