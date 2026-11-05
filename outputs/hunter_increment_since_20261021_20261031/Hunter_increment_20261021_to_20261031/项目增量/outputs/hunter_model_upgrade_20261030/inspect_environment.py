"""Inspect installed personal simulation support. No simulator is started."""
import json
import os
from pathlib import Path
import platform
import pwd
import subprocess


def query(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        return {'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return {'error': str(error)}


def main():
    if os.environ.get('WSL_DISTRO_NAME') != 'Ubuntu-22.04' or pwd.getpwuid(os.getuid()).pw_name != 'aphelios':
        raise SystemExit('Personal WSL environment not confirmed')
    directory = Path('/usr/lib/x86_64-linux-gnu/ign-gazebo-6/plugins')
    report = {'distro': os.environ['WSL_DISTRO_NAME'], 'user': pwd.getpwuid(os.getuid()).pw_name,
              'kernel': platform.release(), 'os_release': Path('/etc/os-release').read_text(),
              'versions': query(['pkg-config', '--modversion', 'ignition-gazebo6', 'ignition-sensors6',
                                 'ignition-rendering6', 'ignition-transport11']),
              'graphics': query(['glxinfo', '-B']),
              'plugins': {keyword: [p.name for p in directory.glob('*' + keyword + '*.so*')]
                          for keyword in ['sensors', 'imu', 'pose-publisher', 'joint-state', 'ackermann']},
              'ros_gz_bridge': Path('/opt/ros/humble/lib/ros_gz_bridge/parameter_bridge').is_file(),
              'ros_ign_bridge': Path('/opt/ros/humble/lib/ros_ign_bridge/parameter_bridge').is_file(),
              'processes': query(['ps', '-u', 'aphelios', '-o', 'pid=,ppid=,comm=,args=']),
              'vehicle_started': False, 'motion_commands_sent': False}
    target = Path('/mnt/f/rob-memory/outputs/hunter_model_upgrade_20261030/references/environment.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    short = {key: value for key, value in report.items() if key != 'processes'}
    print(json.dumps(short, ensure_ascii=False))


if __name__ == '__main__':
    main()
