"""Open an owned paused full-CAD preview and take a Gazebo screenshot only."""
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path('/mnt/f/rob-memory')
sys.path.insert(0, str(ROOT / 'sim/tools'))
from check_ros_isolation import validate_environment
from check_hunter_full_scene import check_scene


def main():
    validate_environment(os.environ, Path('/proc/sys/kernel/osrelease').read_text(),
                         pwd.getpwuid(os.getuid()).pw_name)
    if sys.argv[1:]:
        raise ValueError('No arguments allowed')
    validation = check_scene()
    token = uuid.uuid4().hex[:12]
    directory = ROOT / 'outputs/hunter_model_upgrade_20261030/references/full_preview' / token
    directory.mkdir(parents=True)
    pictures = Path('/home/aphelios/hz_sim_ws/reports') / ('full_preview_' + token)
    pictures.mkdir()
    environment = dict(os.environ, IGN_PARTITION='hz_sim_aphelios_73_full_preview_' + token,
                       QSG_INFO='1', QT_LOGGING_RULES='qt.qpa.gl=true', LIBGL_DEBUG='verbose')
    for key in ('IGN_GAZEBO_SYSTEM_PLUGIN_PATH', 'IGN_GAZEBO_RESOURCE_PATH',
                'IGN_GAZEBO_SERVER_CONFIG_PATH'):
        environment.pop(key, None)
    report = {'ok': False, 'world': 'hz_hunter_full', 'validation': validation,
              'physics_play_requested': False, 'velocity_published': False,
              'partition': environment['IGN_PARTITION'], 'report_directory': str(directory)}

    def query(name, arguments, timeout=8):
        result = subprocess.run(['/usr/bin/ign', *arguments], env=environment,
                                capture_output=True, text=True, timeout=timeout)
        (directory / (name + '.txt')).write_text(result.stdout + result.stderr, encoding='utf-8')
        return result

    def paused_zero(result):
        if result.returncode or not re.search(r'paused:\s*true', result.stdout):
            return False
        match = re.search(r'sim_time\s*\{([^}]*)\}', result.stdout)
        if not match:
            return False
        return all(int(value) == 0 for value in re.findall(r'(?:sec|nsec):\s*(-?\d+)', match[1]))

    sdf_check = query('sdf_check', ['sdf', '-k', str(ROOT / 'sim/scenes/hz_hunter_full.sdf')])
    if sdf_check.returncode:
        raise ValueError('Full world SDF validation failed')
    with (directory / 'startup.log').open('wb') as log:
        process = subprocess.Popen(['/usr/bin/ign', 'gazebo', '-v', '3', '--render-engine-gui', 'ogre',
                                    '--gui-config', str(ROOT / 'sim/scenes/hz_hunter_full_gui.config'),
                                    str(ROOT / 'sim/scenes/hz_hunter_full.sdf')],
                                   env=environment, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            deadline = time.monotonic() + 35
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Full-model GUI exited during startup')
                try:
                    stats = query('initial_stats', ['topic', '-e', '-t', '/world/hz_hunter_full/stats', '-n', '1'], 5)
                except subprocess.TimeoutExpired:
                    continue
                if paused_zero(stats):
                    break
            else:
                raise TimeoutError('No paused world at simulation time zero')
            time.sleep(4)
            if process.poll() is not None:
                raise RuntimeError('GUI exited before screenshot')
            query('command_topic_info', ['topic', '-i', '-t', '/hz_sim/full/cmd_vel'])
            response = query('screenshot', ['service', '-s', '/gui/screenshot',
                             '--reqtype', 'ignition.msgs.StringMsg', '--reptype', 'ignition.msgs.Boolean',
                             '--timeout', '5000', '--req', 'data: "' + str(pictures) + '"'])
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline and not list(pictures.glob('*.png')):
                time.sleep(.2)
            images = sorted(pictures.glob('*.png'))
            if not images:
                raise RuntimeError('Gazebo screenshot was not created')
            shutil.copyfile(images[0], directory / 'render.png')
            final = query('final_stats', ['topic', '-e', '-t', '/world/hz_hunter_full/stats', '-n', '1'])
            if not paused_zero(final):
                raise RuntimeError('Preview did not remain paused at time zero')
            report.update(ok=True, paused=True, sim_time_ns=0,
                          screenshot=str(directory / 'render.png'),
                          screenshot_request_exit_code=response.returncode,
                          alive_at_check_end=process.poll() is None)
        except Exception as error:
            report['error'] = repr(error)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=6)
            report['owned_test_process_closed'] = process.poll() is not None
    driver_log = Path('/home/aphelios/.ignition/rendering/ogre.log')
    if driver_log.is_file():
        shutil.copyfile(driver_log, directory / 'ogre.log')
    (directory / 'check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'validation'}, ensure_ascii=False))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
