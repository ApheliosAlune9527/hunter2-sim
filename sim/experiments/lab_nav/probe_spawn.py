"""Drop the vehicle at the spawn pose from a height and watch what physics does.

A vehicle that settles at z ~= 0.165 is resting on the floor.  If it hangs at the
release height instead, something static is holding it up.
"""
import re
import subprocess
import sys
import time

WORLD = 'hz_lab_2d'
MODEL = 'hz_hunter_full'
SPAWN = (-0.21, -0.77, 0.0)


def ign(*args, timeout=30):
    return subprocess.run(['ign', *args], capture_output=True, text=True, timeout=timeout)


def set_pose(x, y, z, yaw):
    req = (f'name: "{MODEL}", position: {{x: {x}, y: {y}, z: {z}}}, '
           f'orientation: {{x: 0, y: 0, z: {yaw}, w: 1}}')
    out = ign('service', '-s', f'/world/{WORLD}/set_pose',
              '--reqtype', 'ignition.msgs.Pose',
              '--reptype', 'ignition.msgs.Boolean',
              '--timeout', '5000', '--req', req)
    return out.stdout.strip()


def model_pose():
    """Read the named model's pose out of the pose/info stream."""
    proc = subprocess.Popen(['ign', 'topic', '-e', '-t', f'/world/{WORLD}/pose/info'],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    text, deadline = '', time.time() + 12
    try:
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                continue
            text += line
            if f'name: "{MODEL}"' in text and text.count('position') > 0:
                chunk = text[text.index(f'name: "{MODEL}"'):]
                match = re.search(r'position\s*\{\s*x:\s*([-\d.e+]+)\s*y:\s*([-\d.e+]+)\s*z:\s*([-\d.e+]+)', chunk)
                if match:
                    return tuple(float(v) for v in match.groups())
    finally:
        proc.kill()
    return None


def main():
    x, y, yaw = SPAWN
    for release in (1.20, 0.40, 0.165):
        result = set_pose(x, y, release, yaw)
        print(f'set_pose z={release}: {result or "(no reply)"}')
        time.sleep(4.0)
        pose = model_pose()
        if pose is None:
            print('  pose read failed')
            continue
        print(f'  after 4 s -> x={pose[0]:.4f} y={pose[1]:.4f} z={pose[2]:.4f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
