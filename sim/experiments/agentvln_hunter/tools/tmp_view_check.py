
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
def report(rx, ry, yaw):
    cx = rx + CAM_FWD*math.cos(yaw); cy = ry + CAM_FWD*math.sin(yaw)
    print('robot (%.2f,%.2f,%.3f) camera (%.2f,%.2f)' % (rx, ry, yaw, cx, cy))
    out = {}
    for name, b in BOXES.items():
        pts = [project(cx, cy, yaw, c) for c in corners(b)]
        us = [p[0] for p in pts]; vs = [p[1] for p in pts]; fs = [p[2] for p in pts]
        u0,u1,v0,v1 = min(us),max(us),min(vs),max(vs)
        inside = (u0 >= 0 and u1 <= 640 and v0 >= 0 and v1 <= 480)
        print('  %-4s u %6.1f..%6.1f  v %6.1f..%6.1f  fwd %.2f..%.2f  inside=%s' % (name,u0,u1,v0,v1,min(fs),max(fs),inside))
        out[name] = (u0,u1,v0,v1)
    sep = out['far'][0] - out['near'][1]
    print('  separation px %.1f' % sep)
for p in [(2.4,1.0,0.273), (2.6,1.2,0.214), (2.0,0.6,0.363), (2.2,0.8,0.301), (2.2,0.6,0.387), (2.4,0.8,0.346)]:
    report(*p)
