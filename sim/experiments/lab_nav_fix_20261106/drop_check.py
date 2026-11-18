"""Is the physics stepping at all?  Drop the model from z=1.0 and watch z for 6 s.

A vehicle that keeps z=1.0 is in a world that is not stepping; one that lands is in a
live world, and a stationary landing is then a drive problem rather than a physics one.
"""
import math
import subprocess
import time

WORLD = 'hz_lab_2d'
MODEL = 'hz_hunter_full'


def set_pose(x, y, z, yaw=0.0):
    req = (f'name: "{MODEL}", position: {{x: {x}, y: {y}, z: {z}}}, '
           f'orientation: {{x: 0, y: 0, z: {math.sin(yaw / 2)}, w: {math.cos(yaw / 2)}}}')
    return subprocess.run(['ign', 'service', '-s', f'/world/{WORLD}/set_pose',
                           '--reqtype', 'ignition.msgs.Pose',
                           '--reptype', 'ignition.msgs.Boolean', '--timeout', '5000',
                           '--req', req], capture_output=True, text=True).stdout.strip()


def read_z():
    p = subprocess.run(['timeout', '3', 'ign', 'topic', '-e', '-t',
                        f'/world/{WORLD}/pose/info'], capture_output=True, text=True)
    text = p.stdout
    idx = text.find(f'name: "{MODEL}"')
    while idx != -1:
        block = text[idx:idx + 500]
        if 'position {' in block:
            return float(block.split('z: ')[1].split()[0])
        idx = text.find(f'name: "{MODEL}"', idx + 1)
    return None


print('set_pose reply:', set_pose(2.535, 12.885, 1.0))
for i in range(6):
    time.sleep(1)
    print(f'  t={i + 1}s z={read_z()}')
