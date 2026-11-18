"""Print the model pose (x, y, z, yaw) so a floating vehicle can be told from a stuck one."""
import math
import subprocess
import sys


def read_pose(model='hz_hunter_full', world='hz_lab_2d'):
    p = subprocess.run(['timeout', '3', 'ign', 'topic', '-e', '-t',
                        f'/world/{world}/pose/info'], capture_output=True, text=True)
    text = p.stdout
    idx = text.find(f'name: "{model}"')
    while idx != -1:
        block = text[idx:idx + 500]
        if 'position {' in block:
            vals = {}
            for axis in ('x', 'y', 'z'):
                try:
                    vals[axis] = float(block.split(f'{axis}: ')[1].split()[0])
                except (IndexError, ValueError):
                    vals[axis] = float('nan')
            return vals
        idx = text.find(f'name: "{model}"', idx + 1)
    return None


if __name__ == '__main__':
    print(read_pose(*(sys.argv[1:3] or [])))
