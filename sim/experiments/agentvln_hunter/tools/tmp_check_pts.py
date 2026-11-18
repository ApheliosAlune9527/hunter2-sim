
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
    if not (0 <= r < h and 0 <= c < w): return None
    return int(img[r, c])
for p in [(4.5,1.2), (5.1,2.6), (5.1,2.5), (5.2,2.7), (4.4,1.1)]:
    print(p, val(*p))
