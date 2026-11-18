"""Is the scan sensor what makes each physics step cost 46 ms?

Copies the drive world with the lidar removed, starts a bare server on it, and reports
the real time factor from Gazebo's own stats topic.  A big jump here means the cost is
rendering, not physics.
"""
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path('/mnt/d/rob-memory')
SRC = ROOT / 'outputs/lab_nav_20261105/lab_nav_world_drive.sdf'
DST = ROOT / 'outputs/lab_nav_fix_20261106/lab_nav_world_nosensor.sdf'
WORLD = 'hz_lab_2d'


def strip_sensor(text: str) -> str:
    start = text.find('<sensor name="scan"')
    if start == -1:
        raise SystemExit('scan sensor not found')
    end = text.find('</sensor>', start) + len('</sensor>')
    return text[:start] + text[end:]


def stats(sample_seconds=6.0):
    p = subprocess.run(['timeout', str(sample_seconds), 'ign', 'topic', '-e', '-t',
                        f'/world/{WORLD}/stats'], capture_output=True, text=True)
    factors = re.findall(r'real_time_factor: ([0-9.]+)', p.stdout)
    iters = re.findall(r'iterations: (\d+)', p.stdout)
    return {'factor_last': float(factors[-1]) if factors else None,
            'iterations_first': int(iters[0]) if iters else None,
            'iterations_last': int(iters[-1]) if iters else None,
            'samples': len(factors)}


def main():
    text = SRC.read_text(encoding='utf-8')
    DST.write_text(strip_sensor(text), encoding='utf-8')
    proc = subprocess.Popen(['ign', 'gazebo', '-s', '-r', '-v', '2', '--headless-rendering',
                             str(DST)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)
    time.sleep(8)
    result = stats()
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    print(json.dumps(result))


if __name__ == '__main__':
    main()
