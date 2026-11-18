
import math
FX = FY = 606.7595825195312
CX, CY = 320.0, 240.0
CAM_Z, CAM_FWD = 0.640, 0.644
OBS = (2.0, 0.5, 0.522)
FAR = (5.50, 2.05, 0.35, 0.35, 0.90)
OBS_CAM = (OBS[0] + CAM_FWD*math.cos(OBS[2]), OBS[1] + CAM_FWD*math.sin(OBS[2]))
RAY_O = (OBS[0], OBS[1])
RAY_T = (FAR[0]-0.175, FAR[1])
def rect_corners(b):
    x, y, sx, sy = b[0], b[1], b[2], b[3]
    return [(x-sx/2, y-sy/2), (x+sx/2, y-sy/2), (x+sx/2, y+sy/2), (x-sx/2, y+sy/2)]
def point_seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx-ax, by-ay
    t = max(0.0, min(1.0, ((px-ax)*dx + (py-ay)*dy) / (dx*dx+dy*dy)))
    cx, cy = ax + t*dx, ay + t*dy
    return math.hypot(px-cx, py-cy)
def ray_clear(near_box):
    return min(point_seg_dist(c, RAY_O, RAY_T) for c in rect_corners(near_box))
def project(p):
    dx = p[0]-OBS_CAM[0]; dy = p[1]-OBS_CAM[1]
    fwd = math.cos(OBS[2])*dx + math.sin(OBS[2])*dy
    left = -math.sin(OBS[2])*dx + math.cos(OBS[2])*dy
    return CX + FX*(-left)/fwd, CY + FY*(-(p[2]-CAM_Z))/fwd, fwd
def box_uv(b):
    pts = []
    for c in rect_corners(b):
        for z in (0.0, b[4]):
            pts.append(project((c[0], c[1], z)))
    us = [p[0] for p in pts]; vs = [p[1] for p in pts]; fs = [p[2] for p in pts]
    return min(us), max(us), min(vs), max(vs), min(fs)
rows = []
x = 3.6
while x <= 5.3:
    y = 0.2
    while y <= 2.75:
        nb = (x, y, 0.35, 0.35, 0.90)
        clear = ray_clear(nb)
        if clear >= 0.55:
            nu0,nu1,nv0,nv1,nd = box_uv(nb)
            fu0,fu1,fv0,fv1,fd = box_uv(FAR)
            inside = nu0 >= 8 and nu1 <= 632 and nv0 >= 8 and nv1 <= 472 and fu0 >= 8 and fu1 <= 632
            gap = nu0 - fu1 if nu0 >= fu1 else fu0 - nu1
            if inside and gap >= 40 and nd < fd - 0.5 and abs(nb[0]-FAR[0]) + abs(nb[1]-FAR[1]) > 0.6:
                rows.append((round(x,2), round(y,2), round(clear,2), round(gap,1), round(nd,2), round(fd,2)))
        y += 0.05
    x += 0.05
print('candidates', len(rows))
rows.sort(key=lambda r: -r[3])
for r in rows[:20]:
    print(r)
