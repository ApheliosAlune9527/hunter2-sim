
import math
FX = FY = 606.7595825195312
CX, CY = 320.0, 240.0
CAM_Z, CAM_FWD = 0.640, 0.644
OBS = (2.0, 0.5, 0.522)
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
for name, b in [('near', (4.10, 2.60, 0.35, 0.35, 0.90)), ('far', (4.90, 1.90, 0.35, 0.35, 0.90))]:
    pts = [project(cx, cy, OBS[2], c) for c in corners(b)]
    us=[p[0] for p in pts]; vs=[p[1] for p in pts]; fs=[p[2] for p in pts]
    print('%-4s u %6.1f..%6.1f v %6.1f..%6.1f fwd %.2f..%.2f inside=%s' % (name,min(us),max(us),min(vs),max(vs),min(fs),max(fs), min(us)>=0 and max(us)<=640 and min(vs)>=0 and max(vs)<=480))
# dock for far box: face corner (4.725, 1.725)
face = (4.725, 1.725)
app = math.atan2(face[1]-OBS[1], face[0]-OBS[0])
dx = face[0] - 0.934*math.cos(app); dy = face[1] - 0.934*math.sin(app)
print('dock', round(dx,3), round(dy,3), 'yaw', round(app,3))
# footprint check vs both boxes
def foot(x, y, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    out = []
    for px, py in ((-0.184,-0.393),(0.834,-0.393),(0.834,0.393),(-0.184,0.393)):
        out.append((x + px*c - py*s, y + px*s + py*c))
    return out
fp = foot(dx, dy, app)
print('footprint', [(round(a,2), round(b,2)) for a,b in fp])
