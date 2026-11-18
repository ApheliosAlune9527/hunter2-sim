
import math
FX = FY = 606.7595825195312
CX, CY = 320.0, 240.0
CAM_Z, CAM_FWD = 0.640, 0.644
FRONT, BACKOFF = 0.834, 0.10
def make(obs):
    cam = (obs[0] + CAM_FWD*math.cos(obs[2]), obs[1] + CAM_FWD*math.sin(obs[2]))
    def uv(x, y, z):
        dx = x - cam[0]; dy = y - cam[1]
        fwd = math.cos(obs[2])*dx + math.sin(obs[2])*dy
        left = -math.sin(obs[2])*dx + math.cos(obs[2])*dy
        if fwd <= 0.2: return None
        return CX + FX*(-left)/fwd, CY + FY*(-(z-CAM_Z))/fwd, fwd
    return uv
def box_stats(uv, x, y, sx, sy, sz):
    us, vs, fs = [], [], []
    for dx in (-sx/2, sx/2):
        for dy in (-sy/2, sy/2):
            for z in (0.0, sz):
                p = uv(x+dx, y+dy, z)
                if p is None: return None
                us.append(p[0]); vs.append(p[1]); fs.append(p[2])
    return dict(u=(min(us), max(us)), v=(min(vs), max(vs)), area=(max(us)-min(us))*(max(vs)-min(vs)), d=min(fs))
def rect_pts(x, y, sx, sy):
    return [(x-sx/2, y-sy/2), (x+sx/2, y-sy/2), (x+sx/2, y+sy/2), (x-sx/2, y+sy/2)]
def foot_poly(x, y, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    return [(x + px*c - py*s, y + px*s + py*c) for px, py in ((-0.184,-0.393),(0.834,-0.393),(0.834,0.393),(-0.184,0.393))]
def seg_pt_dist(a, b, p):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx-ax, by-ay
    t = max(0.0, min(1.0, ((px-ax)*dx + (py-ay)*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-(ax+t*dx), py-(ay+t*dy))
def poly_rect_dist(poly, rect):
    best = 1e9
    for p in poly:
        for i in range(4):
            best = min(best, seg_pt_dist(rect[i], rect[(i+1) % 4], p))
    for p in rect:
        for i in range(4):
            best = min(best, seg_pt_dist(poly[i], poly[(i+1) % 4], p))
    return best
best, near_miss = [], []
for t in (2.0, 2.2, 2.4):
    obs = (-0.21 + t*math.cos(0.522), -0.77 + t*math.sin(0.522), 0.522)
    uv = make(obs)
    for nx in [3.2, 3.4, 3.6, 3.8, 4.0, 4.2]:
        for ny in [0.2, 0.4, 0.6, 0.8, 1.0]:
            for nsz in [(0.25,0.70), (0.30,0.80), (0.35,0.90)]:
                n = box_stats(uv, nx, ny, nsz[0], nsz[0], nsz[1])
                if not n: continue
                if n['u'][0] < 2 or n['u'][1] > 638 or n['v'][0] < 2 or n['v'][1] > 478: continue
                for fx in [4.2, 4.5, 4.8, 5.1, 5.4]:
                    for fy in [1.6, 1.9, 2.2, 2.5, 2.8]:
                        for fsz in [(0.8,1.4), (1.0,1.6), (1.2,1.9), (0.9,1.5)]:
                            f = box_stats(uv, fx, fy, fsz[0], fsz[0], fsz[1])
                            if not f: continue
                            if f['u'][0] < 2 or f['u'][1] > 638 or f['v'][0] < 2 or f['v'][1] > 478: continue
                            sep = f['u'][0]-n['u'][1] if f['u'][0] >= n['u'][1] else n['u'][0]-f['u'][1]
                            if sep < 25: continue
                            ratio = f['area']/n['area']
                            if ratio < 1.25: continue
                            face = (fx - fsz[0]/2, fy - fsz[0]/2)
                            bear = math.atan2(face[1]-obs[1], face[0]-obs[0])
                            dockx = face[0] - (FRONT+BACKOFF)*math.cos(bear)
                            docky = face[1] - (FRONT+BACKOFF)*math.sin(bear)
                            fp = foot_poly(dockx, docky, bear)
                            rn = rect_pts(nx, ny, nsz[0], nsz[0])
                            rf = rect_pts(fx, fy, fsz[0], fsz[0])
                            dn = poly_rect_dist(fp, rn); df = poly_rect_dist(fp, rf)
                            leg = min(seg_pt_dist((obs[0], obs[1]), (dockx, docky), p) for p in rn)
                            row = (round(ratio,2), round(sep,0), (round(obs[0],2), round(obs[1],2)),
                                   (nx,ny,nsz[0],nsz[1]), (fx,fy,fsz[0],fsz[1]),
                                   (round(dockx,2), round(docky,2), round(bear,3)),
                                   round(dn,2), round(df,2), round(leg,2))
                            if dn >= 0.55 and df >= 0.05 and leg >= 0.55:
                                best.append(row)
                            elif dn >= 0.40 and leg >= 0.40:
                                near_miss.append(row)
best.sort(key=lambda r: -r[0]); near_miss.sort(key=lambda r: -min(r[6], r[8]))
print('feasible', len(best))
for r in best[:8]: print(' OK', r)
print('near-miss', len(near_miss))
for r in near_miss[:6]: print(' NM', r)
