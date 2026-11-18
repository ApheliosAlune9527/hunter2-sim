
import math
FX = FY = 606.7595825195312
CX, CY = 320.0, 240.0
CAM_Z, CAM_FWD = 0.640, 0.644
OBS = (2.0, 0.5, 0.522)
BOXES = {'near': (5.50, 2.05, 0.35, 0.35, 0.90), 'far': (4.10, 2.60, 0.35, 0.35, 0.90)}
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
cx = OBS[0] + CAM_FWD*math.cos(OBS[2]); cy = OBS[1] + CAM_FWD*math.sin(OBS[2])
print('camera', round(cx,2), round(cy,2))
out = {}
for n, b in BOXES.items():
    pts = [project(cx, cy, OBS[2], c) for c in corners(b)]
    us=[p[0] for p in pts]; vs=[p[1] for p in pts]; fs=[p[2] for p in pts]
    u0,u1,v0,v1 = min(us),max(us),min(vs),max(vs)
    print('%-4s u %6.1f..%6.1f v %6.1f..%6.1f fwd %.2f..%.2f inside=%s' % (n,u0,u1,v0,v1,min(fs),max(fs), u0>=0 and u1<=640 and v0>=0 and v1<=480))
    out[n]=(u0,u1)
print('gap %.1f px' % (out['far'][0]-out['near'][1] if out['far'][0] >= out['near'][1] else out['near'][0]-out['far'][1]))
