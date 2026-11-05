"""Inventory the recovered personal Linux environment without starting ROS/Gazebo."""
import configparser
import datetime
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess

ROOT = Path('/mnt/d/rob-memory')
REPORT = ROOT / 'outputs/hunter_desktop_restore_20261031'


def main():
    username = pwd.getpwuid(os.getuid()).pw_name
    if username != 'aphelios' or os.environ.get('WSL_DISTRO_NAME') != 'Ubuntu-22.04':
        raise RuntimeError('Only the recovered personal Ubuntu user may run this inventory.')
    queries = {}
    packages = ['ros-humble-ros-base', 'ros-humble-ament-cmake', 'ignition-fortress',
                'ignition-gazebo6', 'libignition-gazebo6', 'libignition-sensors6',
                'libignition-rendering6', 'ros-humble-rmw-cyclonedds-cpp',
                'ros-humble-ros-gz-bridge', 'ros-humble-robot-state-publisher',
                'ros-humble-pointcloud-to-laserscan', 'python3-colcon-common-extensions',
                'mesa-utils']
    for name in packages:
        p = subprocess.run(['dpkg-query', '-W', '-f=${db:Status-Abbrev} ${Version}', name],capture_output=True,text=True)
        queries[name] = {'exit_code':p.returncode,'status_version':p.stdout.strip()}
    workspace = Path('/home/aphelios/hz_sim_ws')
    wsl = configparser.ConfigParser()
    wsl.read('/etc/wsl.conf')
    result = {'checked_at':datetime.datetime.now().astimezone().isoformat(),
              'username':username,'uid':os.getuid(),'distribution':os.environ.get('WSL_DISTRO_NAME'),
              'os_release':Path('/etc/os-release').read_text(),
              'kernel':Path('/proc/sys/kernel/osrelease').read_text().strip(),
              'tools':{name:shutil.which(name) for name in ['python3','colcon','ign','glxinfo','cmake']},
              'packages':queries,'project_root_exists':ROOT.is_dir(),
              'workspace_exists':workspace.is_dir(),
              'source_packages':sorted(p.name for p in (workspace/'src').iterdir()) if (workspace/'src').is_dir() else [],
              'full_model_native_source_exists':(workspace/'src/hz_hunter_full_description').exists(),
              'full_model_install_exists':(workspace/'install/hz_hunter_full_description').exists(),
              'wsl_boot_command_configured':wsl.has_option('boot','command'),
              'wsl_default_user':wsl.get('user','default',fallback=None),
              'wslg_display_available':bool(os.environ.get('DISPLAY')),
              'started_ros_or_gazebo':False,'motion_commands_sent':False}
    (REPORT/'linux-environment.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))


if __name__ == '__main__': main()
