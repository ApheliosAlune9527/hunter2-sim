"""Synchronize the already verified personal model package, without starting it."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path('/mnt/f/rob-memory')
sys.path.insert(0, str(ROOT / 'sim/tools'))
from check_ros_isolation import validate_environment
from hunter_sensor_profile import validate_sources


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            stream.write(data)
        except Exception:
            temp.unlink(missing_ok=True)
            raise
    os.replace(temp, path)


def main():
    validate_environment(os.environ, Path('/proc/sys/kernel/osrelease').read_text(),
                         pwd.getpwuid(os.getuid()).pw_name)
    validate_sources(ROOT)
    source = ROOT / 'sim/hz_hunter_full_description'
    backup = ROOT / ('outputs/hunter_sensor_parameters_20261030/'
                     'before_camera_visual_alignment/sim/hz_hunter_full_description')
    destination = Path('/home/aphelios/hz_sim_ws/src/hz_hunter_full_description')
    if not destination.is_dir() or destination.is_symlink() or destination.resolve() != destination:
        raise ValueError('Unexpected personal package path')
    old = json.loads((backup / 'source_manifest.json').read_text())
    new = json.loads((source / 'source_manifest.json').read_text())
    old_hashes = {entry['path']: entry['sha256'] for entry in old['outputs']}
    new_hashes = {entry['path']: entry['sha256'] for entry in new['outputs']}
    if old_hashes.keys() != new_hashes.keys():
        raise ValueError('The package resource list changed unexpectedly')
    old_hashes['source_manifest.json'] = sha(backup / 'source_manifest.json')
    new_hashes['source_manifest.json'] = sha(source / 'source_manifest.json')
    actual = {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
    if actual != set(new_hashes):
        raise ValueError('The generated package contains unexpected resources')
    for relative, expected in new_hashes.items():
        current_source = source / relative
        target = destination / relative
        if (not current_source.resolve().is_relative_to(source.resolve()) or
                not target.is_file() or target.resolve() != target):
            raise ValueError('Unsafe package file: ' + relative)
        if sha(current_source) != expected:
            raise ValueError('Generated package hash mismatch: ' + relative)
        if sha(target) not in (old_hashes[relative], expected):
            raise ValueError('Personal package has unrecognized edits: ' + relative)
    changed = [p for p in new_hashes if sha(destination / p) != new_hashes[p]]
    for relative in changed:
        atomic_write(destination / relative, (source / relative).read_bytes())

    output = ROOT / 'outputs/hunter_sensor_parameters_20261030'
    converted = ROOT / 'outputs/hunter_model_upgrade_20261030/references/ament'
    result = subprocess.run(['colcon', 'build', '--symlink-install', '--packages-select',
                             'hz_hunter_full_description'],
                            cwd='/home/aphelios/hz_sim_ws', capture_output=True, text=True,
                            timeout=120)
    (output / 'model_build.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError('Personal package build failed: ' + result.stdout + result.stderr)
    robot = ET.parse(source / 'urdf/hunter_full.urdf').getroot()
    for extension in list(robot.findall('gazebo')):
        if extension.find('preserveFixedJoint') is not None:
            robot.remove(extension)
    flat_input = converted / 'hunter_full_lump_input.urdf'
    with tempfile.NamedTemporaryFile(dir=converted, delete=False) as stream:
        temporary = Path(stream.name)
        ET.ElementTree(robot).write(stream, encoding='utf-8', xml_declaration=True)
    parsed = subprocess.run(['/usr/bin/ign', 'sdf', '-p', str(temporary)],
                            capture_output=True, text=True, timeout=30)
    (output / 'sdf_convert.stderr.txt').write_text(parsed.stderr)
    if parsed.returncode:
        temporary.unlink(missing_ok=True)
        raise RuntimeError('URDF conversion failed: ' + parsed.stderr)
    sdf = ET.fromstring(parsed.stdout)
    model = sdf.find('model')
    if model is None or len(model.findall('joint')) != 6 or len(model.findall('link')) != 7:
        temporary.unlink(missing_ok=True)
        raise ValueError('Conversion did not preserve the six moving joints')
    with tempfile.NamedTemporaryFile(dir=converted, suffix='.sdf', delete=False) as stream:
        temporary_sdf = Path(stream.name)
        stream.write(parsed.stdout.encode())
    check = subprocess.run(['/usr/bin/ign', 'sdf', '-k', str(temporary_sdf)],
                           capture_output=True, text=True, timeout=30)
    if check.returncode:
        temporary.unlink(missing_ok=True)
        temporary_sdf.unlink(missing_ok=True)
        raise RuntimeError('Converted SDF check failed: ' + check.stdout + check.stderr)
    os.replace(temporary, flat_input)
    os.replace(temporary_sdf, converted / 'hunter_full.converted.sdf')
    report = {'ok': True, 'updated_package_files': changed, 'build_exit_code': 0,
              'sdf_check_output': check.stdout.strip(), 'physical_links': 7,
              'active_joints': 6, 'simulator_started': False,
              'hardware_driver_started': False, 'velocity_published': False}
    (output / 'model_build_check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
