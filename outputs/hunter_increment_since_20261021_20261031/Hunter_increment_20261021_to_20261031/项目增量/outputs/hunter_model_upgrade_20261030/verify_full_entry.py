"""Exercise the normal entry, capture its paused GUI, close only this launch."""
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


def main():
    validate_environment(os.environ, Path('/proc/sys/kernel/osrelease').read_text(),
                         pwd.getpwuid(os.getuid()).pw_name)
    if sys.argv[1:]:
        raise ValueError('No arguments allowed')
    token = uuid.uuid4().hex[:12]
    directory = ROOT / 'outputs/hunter_model_upgrade_20261030/references/entry_runtime' / token
    directory.mkdir(parents=True)
    pictures = Path('/home/aphelios/hz_sim_ws/reports') / ('full_entry_preview_' + token)
    pictures.mkdir()
    report = {'ok': False, 'physics_play_requested': False, 'velocity_published': False,
              'report_directory': str(directory)}

    def query(name, arguments, timeout=8):
        result = subprocess.run(['/usr/bin/ign', *arguments], capture_output=True, text=True, timeout=timeout)
        (directory / (name + '.txt')).write_text(result.stdout + result.stderr, encoding='utf-8')
        return result

    def paused_zero(result):
        match = re.search(r'sim_time\s*\{([^}]*)\}', result.stdout)
        return (result.returncode == 0 and re.search(r'paused:\s*true', result.stdout) and match and
                all(int(value) == 0 for value in re.findall(r'(?:sec|nsec):\s*(-?\d+)', match[1])))

    with (directory / 'entry.log').open('wb') as log:
        process = subprocess.Popen(['/bin/bash', str(ROOT / 'sim/tools/start_hunter_full_scene.bash')],
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        report['owned_entry_pid'] = process.pid
        try:
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Normal entry exited before a paused scene appeared')
                try:
                    stats = query('initial_stats', ['topic', '-e', '-t', '/world/hz_hunter_full/stats', '-n', '1'], 5)
                except subprocess.TimeoutExpired:
                    continue
                if paused_zero(stats):
                    break
            else:
                raise TimeoutError('Normal entry did not produce a paused world at time zero')
            graph = subprocess.run(['/usr/bin/python3', '-B',
                                    str(ROOT / 'outputs/hunter_model_upgrade_20261030/observe_entry_graph.py')],
                                   capture_output=True, text=True, timeout=18)
            (directory / 'ros_graph.stdout.txt').write_text(graph.stdout, encoding='utf-8')
            (directory / 'ros_graph.stderr.txt').write_text(graph.stderr, encoding='utf-8')
            report['ros_graph'] = json.loads(graph.stdout)
            if graph.returncode or not report['ros_graph'].get('ok'):
                raise RuntimeError('Normal entry observation nodes/interfaces are incomplete')
            info = query('command_topic_info', ['topic', '-i', '-t', '/hz_sim/full/cmd_vel'])
            if 'No publishers on topic' not in info.stdout + info.stderr:
                raise RuntimeError('Unexpected native command publisher or discovery result')
            time.sleep(3)
            query('screenshot', ['service', '-s', '/gui/screenshot', '--reqtype', 'ignition.msgs.StringMsg',
                               '--reptype', 'ignition.msgs.Boolean', '--timeout', '5000',
                               '--req', 'data: "' + str(pictures) + '"'])
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline and not list(pictures.glob('*.png')):
                time.sleep(.2)
            images = sorted(pictures.glob('*.png'))
            if not images:
                raise RuntimeError('Normal entry screenshot was not created')
            shutil.copyfile(images[0], directory / 'render.png')
            final = query('final_stats', ['topic', '-e', '-t', '/world/hz_hunter_full/stats', '-n', '1'])
            if not paused_zero(final):
                raise RuntimeError('Normal entry did not remain paused at time zero')
            report.update(ok=True, paused=True, sim_time_ns=0,
                          screenshot=str(directory / 'render.png'), alive_at_check_end=process.poll() is None)
        except Exception as error:
            report['error'] = repr(error)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=25)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=8)
            report['owned_entry_closed'] = process.poll() is not None
            report['owned_entry_exit_code'] = process.returncode
    (directory / 'check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
