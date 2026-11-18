
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
marks = {(1.885,0.435):'L', (3.185,1.235):'O', (4.7,1.15):'N', (5.5,2.05):'F', (-0.21,-0.77):'S', (4.25,1.8):'D'}
xs = [round(1.2 + i*0.1, 2) for i in range(0, 46)]
print('      ' + ''.join(('%d' % (int(x*10) % 10)) for x in xs))
for y in [round(3.0 - j*0.1, 2) for j in range(0, 46)]:
    row = ''
    for x in xs:
        ch = None
        for (mx, my), m in marks.items():
            if abs(mx-x) < 0.05 and abs(my-y) < 0.05: ch = m
        if ch is None:
            v = val(x, y)
            ch = '#' if (v is not None and v < 250) else ('.' if v is not None else ' ')
        row += ch
    print('%+5.2f %s' % (y, row))
print('legend: # occupied/unknownish, . free(>=250), S spawn, L leg1, O old obs, N near box, F far box, D dock zone')
