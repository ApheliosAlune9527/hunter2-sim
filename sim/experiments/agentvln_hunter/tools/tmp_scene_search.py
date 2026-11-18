
import math
FX = FY = 606.7595825195312
CX, CY = 320.0, 240.0
CAM_Z, CAM_FWD = 0.640, 0.644
OBS = (2.0, 0.5, 0.522)
FRONT = 0.834
BACKOFF = 0.10
def uv(px, py, yaw, x, y, z):
    dx = x - px; dy = y - py
    fwd = math.cos(yaw)*dx + math.sin(yaw)*dy
    left = -math.sin(yaw)*dx + math.cos(yaw)*dy
    if fwd <= 0.2: return None
    return CX + FX*(-left)/fwd, CY + FY*(-(z-CAM_Z))/fwd, fwd
def box_stats(x, y, sx, sy, sz):
    cam = (OBS[0] + CAM_FWD*math.cos(OBS[2]), OBS[1] + CAM_FWD*math.sin(OBS[2]))
    us, vs, fs = [], [], []
    for dx in (-sx/2, sx/2):
        for dy in (-sy/2, sy/2):
            for z in (0.0, sz):
                p = uv(cam[0], cam[1], OBS[2], x+dx, y+dy, z)
                if p is None: return None
                us.append(p[0]); vs.append(p[1]); fs.append(p[2])
    return dict(u=(min(us), max(us)), v=(min(vs), max(vs)), area=(max(us)-min(us))*(max(vs)-min(vs)), d=min(fs))
def rect_pts(x, y, sx, sy):
    return [(x-sx/2, y-sy/2), (x+sx/2, y-sy/2), (x+sx/2, y+sy/2), (x-sx/2, y+sy/2)]
def foot_poly(x, y, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    out = []
    for px, py in ((-0.184,-0.393),(0.834,-0.393),(0.834,0.393),(-0.184,0.393)):
        out.append((x + px*c - py*s, y + px*s + py*c))
    return out
def seg_pt_dist(a, b, p):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx-ax, by-ay
    t = max(0.0, min(1.0, ((px-ax)*dx + (py-ay)*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-(ax+t*dx), py-(ay+t*dy))
def poly_rect_dist(poly, rect):
    # crude: min over vertex-to-edge both ways
    best = 1e9
    for p in poly:
        for i in range(4):
            best = min(best, seg_pt_dist(rect[i], rect[(i+1) % 4], p))
    for p in rect:
        for i in range(4):
            best = min(best, seg_pt_dist(poly[i], poly[(i+1) % 4], p))
    return best
rows = []
for nx in [3.4, 3.6, 3.8, 4.0, 4.2, 4.4]:
    for ny in [0.4, 0.6, 0.8, 1.0, 1.2]:
        for ns in [(0.30, 0.80), (0.35, 0.90)]:
            n = box_stats(nx, ny, ns[0], ns[0], ns[1])
            if not n: continue
            if n['u'][0] < 6 or n['u'][1] > 634 or n['v'][0] < 6 or n['v'][1] > 474: continue
            for fx in [4.4, 4.6, 4.8, 5.0, 5.2, 5.4]:
                for fy in [1.8, 2.0, 2.2, 2.4, 2.6, 2.8]:
                    for fs in [(0.80, 1.40), (1.00, 1.60), (0.70, 1.20)]:
                        f = box_stats(fx, fy, fs[0], fs[0], fs[1])
                        if not f: continue
                        if f['u'][0] < 6 or f['u'][1] > 634 or f['v'][0] < 6 or f['v'][1] > 474: continue
                        sep = f['u'][0]-n['u'][1] if f['u'][0] >= n['u'][1] else n['u'][0]-f['u'][1]
                        if sep < 40: continue
                        ratio = f['area']/n['area']
                        if ratio < 1.5: continue
                        face = (fx - fs[0]/2, fy - fs[0]/2)
                        bear = math.atan2(face[1]-OBS[1], face[0]-OBS[0])
                        dockx = face[0] - (FRONT+BACKOFF)*math.cos(bear)
                        docky = face[1] - (FRONT+BACKOFF)*math.sin(bear)
                        fp = foot_poly(dockx, docky, bear)
                        rect_n = rect_pts(nx, ny, ns[0], ns[0])
                        rect_f = rect_pts(fx, fy, fs[0], fs[0])
                        dn = poly_rect_dist(fp, rect_n)
                        df = poly_rect_dist(fp, rect_f)
                        if dn < 0.55 or df < 0.05: continue
                        # straight leg from the observation pose to the dock must clear the near box too
                        leg = min(seg_pt_dist((OBS[0], OBS[1]), (dockx, docky), p) for p in rect_n)
                        if leg < 0.55: continue
                        rows.append((round(ratio,2), round(sep,0), (nx,ny,ns[0],ns[1]), (fx,fy,fs[0],fs[1]),
                                     round(n['d'],2), round(f['d'],2), (round(dockx,2), round(docky,2), round(bear,3)),
                                     round(dn,2), round(df,2), round(leg,2)))
rows.sort(key=lambda r: -r[0])
print('solutions', len(rows))
for r in rows[:10]:
    print(r)
