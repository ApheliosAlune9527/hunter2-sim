
import math
FX = FY = 606.7595825195312
CX, CY = 320.0, 240.0
CAM_Z, CAM_FWD = 0.640, 0.644
OBS = (2.0, 0.5, 0.522)
CAM = (OBS[0] + CAM_FWD*math.cos(OBS[2]), OBS[1] + CAM_FWD*math.sin(OBS[2]))
NEAR = {'w': 0.30, 'h': 0.80, 'z': 0.40}
FAR = {'w': 0.80, 'h': 1.40, 'z': 0.70}
def corners(x, y, w, h, zc):
    for dx in (-w/2, w/2):
        for dy in (-w/2, w/2):
            yield (x+dx, y+dy, zc - h/2)
            yield (x+dx, y+dy, zc + h/2)
def uv(x, y, z):
    dx = x - CAM[0]; dy = y - CAM[1]
    fwd = math.cos(OBS[2])*dx + math.sin(OBS[2])*dy
    left = -math.sin(OBS[2])*dx + math.cos(OBS[2])*dy
    if fwd <= 0.2: return None
    return CX + FX*(-left)/fwd, CY + FY*(-(z-CAM_Z))/fwd, fwd
def box(x, y, w, h, zc):
    pts = [uv(*c) for c in corners(x, y, w, h, zc)]
    if any(p is None for p in pts): return None
    us = [p[0] for p in pts]; vs = [p[1] for p in pts]; fs = [p[2] for p in pts]
    area = (max(us)-min(us)) * (max(vs)-min(vs))
    return dict(u=(min(us), max(us)), v=(min(vs), max(vs)), d=min(fs), area=area)
best = []
for nx in [3.6, 3.9, 4.2, 4.5]:
    for ny in [0.6, 0.9, 1.2, 1.5]:
        n = box(nx, ny, NEAR['w'], NEAR['h'], NEAR['z'])
        if not n: continue
        for fx in [4.8, 5.1, 5.4, 5.7]:
            for fy in [1.4, 1.8, 2.2, 2.6]:
                f = box(fx, fy, FAR['w'], FAR['h'], FAR['z'])
                if not f: continue
                inside = lambda b: b['u'][0] >= 6 and b['u'][1] <= 634 and b['v'][0] >= 6 and b['v'][1] <= 474
                if not (inside(n) and inside(f)): continue
                sep = f['u'][0] - n['u'][1] if f['u'][0] >= n['u'][1] else n['u'][0] - f['u'][1]
                if sep < 20: continue
                ratio = f['area'] / n['area']
                if ratio < 1.2: continue
                best.append((round(ratio,2), round(sep,1), (nx,ny), (round(n['d'],2), round(n['area'])), (fx,fy), (round(f['d'],2), round(f['area']))))
best.sort(key=lambda r: -r[0])
print('candidates', len(best))
for b in best[:12]:
    print(b)
