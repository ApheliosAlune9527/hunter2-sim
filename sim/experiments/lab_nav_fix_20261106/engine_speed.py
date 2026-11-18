"""Compare render engines for the scan sensor: ogre (current) versus ogre2.

The world runs at 1.0x with the lidar removed and 0.08x with it, so the cost is the
rendering path, not the ray count (720x3 rays is trivial).  This starts one server per
engine and reports Gazebo's own real time factor.
"""
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path('/mnt/d/rob-memory')
SRC = ROOT / 'outputs/lab_nav_20261105/lab_nav_world_drive.sdf'
OUT = ROOT / 'outputs/lab_nav_fix_20261106'
WORLD = 'hz_lab_2d'


def variant(engine):
    text = SRC.read_text(encoding='utf-8')
    text = text.replace('<render_engine>ogre</render_engine>',
                        f'<render_engine>{engine}</render_engine>')
    if f'<render_engine>{engine}</render_engine>' not in text:
        raise SystemExit(f'could not set engine {engine}')
    path = OUT / f'lab_nav_world_{engine}.sdf'
    path.write_text(text, encoding='utf-8')
    return path


def measure(path, seconds=8.0):
    proc = subprocess.Popen(['ign', 'gazebo', '-s', '-r', '-v', '2', '--headless-rendering',
                             str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)
    time.sleep(6)
    p = subprocess.run(['timeout', str(seconds), 'ign', 'topic', '-e', '-t',
                        f'/world/{WORLD}/stats'], capture_output=True, text=True)
    factors = re.findall(r'real_time_factor: ([0-9.]+)', p.stdout)
    iters = re.findall(r'iterations: (\d+)', p.stdout)
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    time.sleep(1)
    first = int(iters[0]) if iters else None
    last = int(iters[-1]) if iters else None
    rate = (last - first) / seconds if (first and last) else None
    return {'factor_last': float(factors[-1]) if factors else None,
            'iterations_per_s': round(rate, 1) if rate else None}


if __name__ == '__main__':
    results = {}
    for engine in ('ogre2', 'ogre'):
        results[engine] = measure(variant(engine))
    (OUT / 'engine_speed.json').write_text(json.dumps(results, indent=1), encoding='utf-8')
    print(json.dumps(results))
