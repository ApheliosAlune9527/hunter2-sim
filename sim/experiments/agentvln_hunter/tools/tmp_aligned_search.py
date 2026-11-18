
import math
FX = FY = 606.7595825195312
CX, CY = 320.0, 240.0
CAM_Z, CAM_FWD = 0.640, 0.644
BOXES = {'near': (4.70, 1.15, 0.35, 0.35, 0.90), 'far': (5.50, 2.05, 0.35, 0.35, 0.90)}
def corners(b):
    x, y, sx, sy, sz = b
    for dx in (-sx/2, sx/2):
        for dy in (-sy/2, sy/2):
            for z in (0.0, sz):
                yield (x+dx, y+dy, z)
def project(cx, cy, yaw, p):
    dx = p[0]-cx; dy = p[1]-cy
    fwd = math.cos(yaw)*dx + math.sin(yaw)*dy
    left = -math.sin(yaw)*dx + math.cos(yaw)*dy
    return CX + FX*(-left)/fwd, CY + FY*(-(p[2]-CAM_Z))/fwd, fwd
def view(rx, ry, yaw):
    cx = rx + CAM_FWD*math.cos(yaw); cy = ry + CAM_FWD*math.sin(yaw)
    out = {}
    for name, b in BOXES.items():
        pts = [project(cx, cy, yaw, c) for c in corners(b)]
        us = [p[0] for p in pts]; vs = [p[1] for p in pts]; fs = [p[2] for p in pts]
        out[name] = (min(us), max(us), min(vs), max(vs), min(fs))
    return out
rows = []
x = 1.2
while x <= 3.6:
    y = -0.9
    while y <= 2.4:
        yaw = math.atan2(y + 0.77, x + 0.21)
        o = view(x, y, yaw)
        ok = all(o[n][0] >= 4 and o[n][1] <= 636 and o[n][2] >= 4 and o[n][3] <= 476 for n in o)
        gap = o['near'][0] - o['far'][1]
        dmin = o['near'][4]
        if ok and gap > 25 and dmin > 1.4:
            rows.append((round(x,2), round(y,2), round(yaw,3), round(gap,1), round(dmin,2)))
        y += 0.1
    x += 0.1
rows.sort(key=lambda r: -r[3])
print(len(rows), 'aligned poses with both boxes fully inside')
for r in rows[:12]:
    print(r)
