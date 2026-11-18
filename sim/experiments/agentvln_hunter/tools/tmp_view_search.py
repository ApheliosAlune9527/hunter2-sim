
import math
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
def free(x, y):
    v = val(x, y)
    return v is not None and v >= 250
def clear(x, y, rad=0.45, n=12):
    if not free(x, y): return False
    for k in range(n):
        a = 2*math.pi*k/n
        for rr in (rad*0.6, rad):
            if not free(x + rr*math.cos(a), y + rr*math.sin(a)): return False
    return True
def los(x0, y0, x1, y1, n=120):
    for i in range(1, n):
        t = i/n
        v = val(x0 + (x1-x0)*t, y0 + (y1-y0)*t)
        if v is not None and v < 250: return False
    return True
FX = FY = 606.7595825195312
CX, CY = 320.0, 240.0
CAM_Z = 0.640
CAM_FWD = 0.644
BOXES = {'near': (4.70, 1.15, 0.35, 0.35, 0.90), 'far': (5.50, 2.05, 0.35, 0.35, 0.90)}
def corners(b):
    x, y, sx, sy, sz = b
    for dx in (-sx/2, sx/2):
        for dy in (-sy/2, sy/2):
            yield (x+dx, y+dy, 0.45)
def project(cx, cy, yaw, p):
    dx = p[0]-cx; dy = p[1]-cy
    fwd = math.cos(yaw)*dx + math.sin(yaw)*dy
    left = -math.sin(yaw)*dx + math.cos(yaw)*dy
    if fwd <= 0.1: return None
    return CX + FX*(-left)/fwd, CY + FY*(-(p[2]-CAM_Z))/fwd, fwd
def view(rx, ry, yaw):
    cx = rx + CAM_FWD*math.cos(yaw); cy = ry + CAM_FWD*math.sin(yaw)
    out = {}
    for name, b in BOXES.items():
        pts = []
        for c in corners(b):
            p = project(cx, cy, yaw, c)
            if p is None: return None
            pts.append(p)
        us = [p[0] for p in pts]; vs = [p[1] for p in pts]
        out[name] = (min(us), max(us), min(vs), max(vs), min(p[2] for p in pts))
    return out
def score(rx, ry, yaw):
    cx = rx + CAM_FWD*math.cos(yaw); cy = ry + CAM_FWD*math.sin(yaw)
    o = view(rx, ry, yaw)
    if not o: return None
    for n, (u0,u1,v0,v1,d) in o.items():
        if u0 < 8 or u1 > 632 or v0 < 8 or v1 > 472: return None
        b = BOXES[n]
        if not los(cx, cy, b[0], b[1]): return None
    nu0,nu1 = o['near'][0], o['near'][1]
    fu0,fu1 = o['far'][0], o['far'][1]
    sep = fu0 - nu1 if fu0 >= nu1 else nu0 - fu1
    return dict(near=(round(nu0),round(nu1)), far=(round(fu0),round(fu1)), sep=round(sep,1),
                near_d=round(o['near'][4],2), far_d=round(o['far'][4],2))
mid = (4.9, 1.7)
rows = []
x = 1.2
while x <= 4.2:
    y = -1.4
    while y <= 2.6:
        if clear(x, y, 0.40):
            yaw = math.atan2(mid[1]-y, mid[0]-x)
            s = score(x, y, yaw)
            if s and s['sep'] > 40:
                rows.append((round(x,2), round(y,2), round(yaw,3), round(math.hypot(x-1.885, y-0.435),2), s))
        y += 0.1
    x += 0.1
rows.sort(key=lambda r: (-r[4]['sep'], r[3]))
print('candidates', len(rows))
for r in rows[:15]:
    print(r)
