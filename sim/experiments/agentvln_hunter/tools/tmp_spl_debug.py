
import numpy as np, yaml, math
from pathlib import Path
from PIL import Image
P = Path('/mnt/d/rob-memory/sim/experiments/agentvln_hunter/config/straight_nav_map/lab_nav_map_fix.yaml')
meta = yaml.safe_load(P.read_text())
img = np.array(Image.open(P.parent / meta['image']))
h, w = img.shape
res = meta['resolution']; ox, oy = meta['origin'][0], meta['origin'][1]
free = img >= 250
print('shape', img.shape, 'free cells', int(free.sum()), 'of', h*w)
def mask(radius_m):
    r = int(math.ceil(radius_m / res))
    blocked = ~free
    for _ in range(r):
        b = blocked.copy()
        b[1:, :] |= blocked[:-1, :]; b[:-1, :] |= blocked[1:, :]
        b[:, 1:] |= blocked[:, :-1]; b[:, :-1] |= blocked[:, 1:]
        blocked = b
    return free & ~blocked
for rad in (0.0, 0.10, 0.20, 0.30, 0.393):
    m = mask(rad) if rad > 0 else free
    print('radius', rad, 'passable', int(m.sum()))
def cell(x, y):
    return h - 1 - int((y - oy)/res), int((x - ox)/res)
for pt in ((2.0,0.5), (3.539,1.385), (-0.21,-0.77), (1.938,0.519)):
    r, c = cell(*pt)
    print(pt, 'cell', (r,c), 'free', bool(free[r,c]), 'mask0.393', bool(mask(0.393)[r,c]), 'mask0.2', bool(mask(0.2)[r,c]))
