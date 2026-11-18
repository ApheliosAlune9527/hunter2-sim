"""Where is the wall along the line y=-0.77?  Reads the map, prints occupied x."""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path('/mnt/d/rob-memory')
MAP_YAML = ROOT / 'outputs/lab_nav_20261105/lab_nav_map.yaml'


def main():
    meta = {}
    for line in MAP_YAML.read_text().splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            meta[k.strip()] = v.strip()
    res = float(meta['resolution'])
    ox, oy, _ = [float(x) for x in meta['origin'].strip('[]').split(',')]
    img = np.array(Image.open(MAP_YAML.parent / meta['image']))
    rows, cols = img.shape

    y = -0.77
    row = int(round(rows - (y - oy) / res - 0.5))
    xs = [round(ox + (c + 0.5) * res, 3) for c in range(cols) if img[row, c] == 0]
    early = [x for x in xs if x > 4.0]
    print({'row': row, 'y_used': round(oy + (rows - row - 0.5) * res, 3),
           'first_occupied_beyond_4m': early[:4], 'count': len(early)})

    # also the value right where the vehicle stopped
    col = int(round((4.745 - ox) / res - 0.5))
    print({'at_vehicle': int(img[row, col]),
           'next_cm_values': [int(img[row, col + k]) for k in range(0, 12)]})


if __name__ == '__main__':
    main()
