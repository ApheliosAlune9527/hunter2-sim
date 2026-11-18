
import numpy as np, yaml
from pathlib import Path
from PIL import Image
YAML = Path('/mnt/d/rob-memory/outputs/lab_nav_fix_20261106/lab_nav_map_fix.yaml')
meta = yaml.safe_load(YAML.read_text())
img = np.array(Image.open(YAML.parent / meta['image']))
h, w = img.shape
res = meta['resolution']; ox, oy = meta['origin'][0], meta['origin'][1]
def val(x, y):
    c = int((x-ox)/res); r = h-1-int((y-oy)/res)
    return int(img[r, c]) if 0 <= r < h and 0 <= c < w else None
def los(x0, y0, x1, y1, n=600):
    ts = []
    for i in range(n+1):
        t = i/n
        if val(x0 + (x1-x0)*t, y0 + (y1-y0)*t) == 0: ts.append(round(t,3))
    return ts[:8]
cam = (0.434, -0.77)   # camera optical origin at spawn
for cand in [(2.10,-0.35), (2.10,-0.45), (2.3,-0.5)]:
    print(cand, 'map_value', val(*cand), 'blocked_t', los(*cam, *cand))
