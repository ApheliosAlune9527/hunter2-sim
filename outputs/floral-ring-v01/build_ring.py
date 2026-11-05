"""Source-derived floral ring study. All construction dimensions are millimetres."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / 'tmp/floral-ring-tools/python'))
import numpy as np
import trimesh
import manifold3d
from scipy.interpolate import CubicSpline
from trimesh.visual.material import PBRMaterial

OUT = Path(__file__).parent
TAU = math.tau
PARAMS = {
    'version': 'v01-form-study',
    'units': 'mm',
    'inner_diameter_mm': 17.0,
    'sizing_status': 'provisional: user requested shape preview first',
    'minimum_petal_design_thickness_mm': 0.7,
    'band_bottom_radial_thickness_mm': 1.65,
    'band_bottom_width_mm': 2.8,
    'reference': 'codex-clipboard-90109d22-4b6e-480b-b525-5f916c4a3260.jpg',
}
R = PARAMS['inner_diameter_mm'] / 2
parts: list[tuple[str, str, trimesh.Trimesh]] = []


def unit(a):
    a = np.asarray(a, dtype=float)
    return a / np.linalg.norm(a)


def finish(vertices, faces):
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    mesh.fix_normals()
    if mesh.volume < 0:
        mesh.invert()
    if not mesh.is_watertight:
        raise ValueError('A generated construction part is not closed')
    return mesh


def add(name, category, mesh):
    parts.append((name, category, mesh))
    return mesh


def ball(name, category, center, radii, subdivisions=2):
    mesh = trimesh.creation.icosphere(subdivisions=subdivisions, radius=1)
    mesh.apply_scale(radii)
    mesh.apply_translation(center)
    return add(name, category, mesh)


def tube(name, category, control, radius, samples=44, sides=14):
    controls = np.asarray(control, dtype=float)
    tt = np.linspace(0, 1, len(controls))
    t = np.linspace(0, 1, samples)
    pts = CubicSpline(tt, controls, axis=0)(t)
    tangent = np.gradient(pts, axis=0)
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    frames = []
    prev = None
    for tang in tangent:
        if prev is None:
            ref = np.array([0., 1., 0.])
            if abs(np.dot(tang, ref)) > .9:
                ref = np.array([1., 0., 0.])
            n = unit(np.cross(tang, ref))
        else:
            n = unit(prev - np.dot(prev, tang) * tang)
        b = unit(np.cross(tang, n))
        frames.append((n, b))
        prev = n
    vertices = []
    for i, p in enumerate(pts):
        n, b = frames[i]
        rr = radius(float(t[i])) if callable(radius) else radius
        for a in np.linspace(0, TAU, sides, endpoint=False):
            vertices.append(p + rr * (math.cos(a) * n + math.sin(a) * b))
    vertices.extend([pts[0], pts[-1]])
    faces = []
    for i in range(samples - 1):
        for j in range(sides):
            k = (j + 1) % sides
            a, b, c, d = i*sides+j, i*sides+k, (i+1)*sides+j, (i+1)*sides+k
            faces.extend([(a,b,c), (b,d,c)])
    for j in range(sides):
        k = (j+1) % sides
        faces.extend([(samples*sides, k, j),
                      (samples*sides+1, (samples-1)*sides+j, (samples-1)*sides+k)])
    return add(name, category, finish(vertices, faces))


def band_thickness(theta):
    top = ((math.cos(theta)+1)/2)**3
    return 1.65 + .42*top


def band_width(theta):
    top = ((math.cos(theta)+1)/2)**3
    return 2.8 + 1.75*top


def ring_band():
    nt, ns = 256, 32
    vertices, faces = [], []
    for th in np.linspace(0, TAU, nt, endpoint=False):
        thick, width = band_thickness(th), band_width(th)
        for ph in np.linspace(0, TAU, ns, endpoint=False):
            co, si = math.cos(ph), math.sin(ph)
            radial = R + thick/2 + thick/2 * np.sign(co)*abs(co)**.48
            y = width/2*np.sign(si)*abs(si)**.48
            vertices.append((radial*math.sin(th), y, radial*math.cos(th)))
    for i in range(nt):
        for j in range(ns):
            a, b = i*ns+j, i*ns+(j+1)%ns
            c, d = ((i+1)%nt)*ns+j, ((i+1)%nt)*ns+(j+1)%ns
            faces.extend([(a,b,c),(b,d,c)])
    add('smooth_comfort_band', 'band', finish(vertices, faces))


def surface_solid(points, thickness_vectors):
    # A top and bottom sampled sheet, joined around its entire perimeter.
    pts = np.asarray(points)
    off = np.asarray(thickness_vectors)
    nu, nv = pts.shape[:2]
    size = nu*nv
    vertices = np.concatenate([(pts+off/2).reshape(-1,3), (pts-off/2).reshape(-1,3)])
    faces = []
    for i in range(nu-1):
        for j in range(nv-1):
            a,b,c,d = i*nv+j, (i+1)*nv+j, i*nv+j+1, (i+1)*nv+j+1
            faces.extend([(a,b,c),(b,d,c), (a+size,c+size,b+size),(b+size,c+size,d+size)])
    perimeter = (list(range(nv)) + [i*nv+nv-1 for i in range(1,nu)]
                 + [(nu-1)*nv+j for j in range(nv-2,-1,-1)]
                 + [i*nv for i in range(nu-2,0,-1)])
    for q, a in enumerate(perimeter):
        b = perimeter[(q+1)%len(perimeter)]
        faces.extend([(a,a+size,b),(b,a+size,b+size)])
    return finish(vertices, faces)


def basis(normal):
    n = unit(normal)
    u = unit(np.array([1.,0.,0.])-n[0]*n)
    v = unit(np.cross(n,u))
    return u,v,n


def petal(name, center, normal, angle, length, half_width, tip_lift=1.1,
          cup=.7, bend=0., thickness=.7, category='petal', phase=0., vein=False):
    u,v,n = basis(normal)
    d = math.cos(angle)*u + math.sin(angle)*v
    e = -math.sin(angle)*u + math.cos(angle)*v
    center = np.asarray(center)
    ts = np.linspace(0,1,36)
    ss = np.linspace(-1,1,21)
    points, offsets = [], []
    for t in ts:
        row, thick_row = [], []
        snt = max(0,math.sin(math.pi*t))
        # Broad, softly tapering petals, with slight asymmetric folds.
        w = .13 + (half_width-.13) * snt**.58 * (.83+.24*t)
        for s in ss:
            radial = .15 + length*t - .18*s*s*snt
            sideways = w*s + bend*snt + .09*math.sin(5*t+phase)*snt*s*s
            h = (.12*t + tip_lift*t**3 - .31*snt + cup*s*s*snt**.65
                 + .08*math.sin(5.2*t+phase+1.5*s)*snt
                 + .10*math.exp(-(s/.20)**2)*snt)
            row.append(center+radial*d+sideways*e+h*n)
            thick_row.append(thickness*n)
        points.append(row)
        offsets.append(thick_row)
    mesh = surface_solid(points, offsets)
    add(name, category, mesh)
    if vein:
        ctrl = []
        for t in np.linspace(.12,.85,5):
            snt = math.sin(math.pi*t)
            h = .12*t+tip_lift*t**3-.31*snt+.08*math.sin(5.2*t+phase)*snt+.10*snt
            ctrl.append(center+(.15+length*t)*d+bend*snt*e+(h+thickness*.43)*n)
        tube(name+'_fold',category,ctrl,.13,samples=28,sides=8)
    return mesh


def flower(name, center, normal, size=1., petals=5, rotation=0.):
    center = np.asarray(center)
    u,v,n = basis(normal)
    ball(name+'_receptacle','stem',center-n*.27,[.95*size,.95*size,.95*size])
    for j in range(petals):
        a = rotation + TAU*j/petals
        # Unequal petal dimensions and overlap give the reference's orchid-like silhouette.
        length = size * (5.1 + .36*math.sin(1.9*j+.3))
        width = size * (2.15 + .23*math.cos(1.5*j))
        petal(f'{name}_outer_{j+1}',center+n*(.06*j),normal,a,length,width,
              tip_lift=size*(1.05+.28*math.sin(j)), cup=.78*size,
              bend=.2*size*math.sin(2*j), thickness=max(.7,.78*size),phase=j*.9)
    # Three soft inner lobes and a central cluster, all anchored to the receptacle.
    for j in range(3):
        petal(f'{name}_inner_{j+1}',center+n*.62,normal,rotation+.5+TAU*j/3,
              1.55*size,.72*size,tip_lift=.9*size,cup=.38*size,
              thickness=.7,phase=j)
    ball(name+'_heart','petal',center+n*.95,[.56*size+.12]*3,subdivisions=2)
    for j in range(5):
        a=TAU*j/5
        end=center+n*(1.12*size)+.5*size*(math.cos(a)*u+math.sin(a)*v)
        tube(name+f'_stamen_{j}','petal',[center+n*.25,end],.22 if size>.8 else .18,
             samples=12,sides=10)
        ball(name+f'_anther_{j}','petal',end,[.29 if size>.8 else .23]*3)


def bud(name, base, axis, height=6., radius=2.1, phase=0.):
    base=np.asarray(base)
    u,v,n=basis(axis)
    ball(name+'_base','stem',base,[.8]*3)
    for j in range(3):
        ph=phase+TAU*j/3
        points,offsets=[],[]
        for t in np.linspace(0,1,40):
            # Keep the inner offset radius positive at both ends of the shell.
            rr=.55+radius*math.sin(math.pi*t)**.72
            row,off=[],[]
            for s in np.linspace(-1,1,22):
                a=ph+s*(1.12-.15*t)
                radial=math.cos(a)*u+math.sin(a)*v
                p=(base+n*(height*t)+rr*radial
                   +n*(.28*math.cos(2*s)*math.sin(math.pi*t)))
                row.append(p)
                off.append(.72*radial)
            points.append(row); offsets.append(off)
        add(f'{name}_petal_{j+1}','petal',surface_solid(points,offsets))
    # Internal core ensures the closed overlapping bud stays connected through its base.
    tube(name+'_core','stem',[base-n*.2,base+n*(height-.4)],.5,samples=24,sides=12)


def create():
    ring_band()
    # Branches lie on the outside of the band; the wearing surface stays smooth.
    for side in [-1,1]:
        for j, y0 in enumerate(np.linspace(-1.65,1.65,6)):
            control=[]
            for k,a in enumerate(np.linspace(18,126,7)):
                th=side*math.radians(a)
                rr=R+band_thickness(th)-.12-.30*(k/6)**4+.07*math.sin(a*.045+j)
                width=band_width(th)
                y=y0*(width/4.55)+.16*math.sin(a*.04+j*.8)
                control.append((rr*math.sin(th),y,rr*math.cos(th)))
            r0=.34 if j%2 else .39
            tube(f'branch_relief_{side}_{j}','band',control,lambda t,r0=r0:r0*(.20+.80*(1-t)**.25),
                 samples=72,sides=12)

    # Structural stems are part of the intended sculptural form.
    tube('main_flower_stem','stem',[(6.8,.45,7.6),(5.4,.6,10.3),(3.6,-.2,12.0),(2.0,-2.0,12.7)],
         lambda t:.85-.16*t,samples=55,sides=18)
    tube('main_flower_back_brace','stem',[(-2.8,1.,10.0),(-1.,.9,12.0),(2.0,-2.,12.7)],
         .72,samples=45,sides=16)
    tube('side_flower_stem','stem',[(-8.4,.2,5.7),(-7.6,-.4,7.8),(-6.65,-1.65,9.35)],
         .75,samples=40,sides=16)
    tube('rear_bud_stem','stem',[(-3.9,.8,9.5),(-3.3,1.2,12.0),(-2.2,1.5,14.0)],
         .76,samples=42,sides=16)
    tube('right_bud_stem','stem',[(4.8,1.2,9.0),(4.4,2.,12.1),(3.35,2.0,14.1)],
         .70,samples=42,sides=16)

    # Supporting leaves behind and beside the flower cluster.
    petal('left_back_leaf',[-4.1,1.25,11.4],[-.35,.2,.92],2.7,4.6,1.22,
          tip_lift=1.6,cup=.55,category='stem',vein=True)
    petal('right_back_leaf',[4.4,1.6,11.5],[.18,-.75,.64],.55,3.9,1.05,
          tip_lift=1.5,cup=.5,category='stem',vein=True)
    petal('left_shoulder_leaf',[-7.8,.0,7.4],[-.7,-.6,.38],1.6,3.4,.95,
          tip_lift=.7,cup=.4,category='stem',vein=True)
    bud('rear_tall_bud',[-2.2,1.5,14.0],[-.18,.12,.976],height=6.1,radius=1.4,phase=.4)
    bud('rear_right_bud',[3.35,2.0,14.1],[.40,.22,.89],height=4.9,radius=1.15,phase=1.1)
    flower('main_flower',[2.0,-2.0,12.7],[.08,-.81,.58],size=1.18,petals=5,rotation=.30)
    flower('side_flower',[-6.65,-1.65,9.35],[-.45,-.83,.33],size=.62,petals=6,rotation=.18)


def export():
    silver=PBRMaterial(name='Soft polished silver',baseColorFactor=[178,181,177,255],
                       metallicFactor=1.,roughnessFactor=.26)
    satin=PBRMaterial(name='Satin silver petals',baseColorFactor=[218,216,207,255],
                      metallicFactor=.88,roughnessFactor=.35)
    scene=trimesh.Scene()
    for name,category,mesh in parts:
        render_mesh=mesh.copy()
        render_mesh.apply_scale(.001)  # glTF uses metres; STL below uses millimetres.
        render_mesh.visual=trimesh.visual.TextureVisuals(material=satin if category=='petal' else silver)
        scene.add_geometry(render_mesh,geom_name=name,node_name=name)
    scene.export(OUT/'floral-ring-v01.glb',include_normals=True)
    print(f'Visual scene: {len(parts)} parts, {sum(len(m.faces) for _,_,m in parts)} triangles',flush=True)

    print('Fusing closed solids for the print mesh...',flush=True)
    merged=trimesh.boolean.union([m for _,_,m in parts],engine='manifold',check_volume=True)
    # A continuous cylindrical finger bore also removes any accidental ornamental intrusion.
    bore=trimesh.creation.cylinder(radius=R,height=70,sections=512)
    bore.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2,[1,0,0]))
    merged=trimesh.boolean.difference([merged,bore],engine='manifold',check_volume=True)
    # Collapse sub-micron boolean slivers before the topology-free STL export.
    native=manifold3d.Manifold(manifold3d.Mesh(
        vert_properties=np.asarray(merged.vertices,dtype=np.float32),
        tri_verts=np.asarray(merged.faces,dtype=np.uint32))).simplify(.003)
    if native.status()!=manifold3d.Error.NoError:
        raise ValueError(f'Manifold construction failed: {native.status()}')
    cleaned=native.to_mesh()
    merged=trimesh.Trimesh(vertices=cleaned.vert_properties[:,:3],faces=cleaned.tri_verts,process=False)
    components=sorted(merged.split(only_watertight=False),key=lambda c:abs(c.volume),reverse=True)
    filled_microvoids=0
    if len(components)>1:
        outer=components[0]
        tiny_internal_voids=all(
            c.is_watertight and -.001<float(c.volume)<0 and float(c.extents.max())<.35
            and bool(outer.contains([c.vertices.mean(axis=0)])[0])
            for c in components[1:])
        if tiny_internal_voids:
            # Fill enclosed microscopic bubbles; never discard a disconnected solid feature.
            filled_microvoids=len(components)-1
            merged=outer
            components=[outer]
            print(f'Filled {filled_microvoids} enclosed microvoids below 0.001 mm3.',flush=True)
    info=[]
    for i,c in enumerate(components):
        info.append({'index':i,'volume_mm3':round(float(c.volume),4),
                     'bounds_mm':np.round(c.bounds,3).tolist(),'faces':len(c.faces)})
    print('Connected components:',len(components),'largest:',json.dumps(info[:8],ensure_ascii=False),flush=True)
    if len(components)!=1:
        merged.export(OUT/'diagnostic-disconnected.stl')
        raise ValueError(f'Model has {len(components)} disconnected components; add proper structural connections')
    merged.export(OUT/'floral-ring-v01-id17mm.stl')
    report={
        'status':'shape-study; not a casting production approval',
        'units_for_stl':'mm',
        'nominal_inner_diameter_mm':2*R,
        'watertight':bool(merged.is_watertight),
        'consistent_winding':bool(merged.is_winding_consistent),
        'positive_volume':bool(merged.volume>0),
        'connected_components':len(components),
        'filled_enclosed_microvoids':filled_microvoids,
        'vertices':len(merged.vertices),
        'triangles':len(merged.faces),
        'volume_mm3':round(float(merged.volume),3),
        'approximate_silver_weight_g_at_10_3_g_cm3':round(float(merged.volume)*.0103,2),
        'bounds_mm':np.round(merged.bounds,3).tolist(),
        'overall_dimensions_mm':np.round(merged.extents,3).tolist(),
        'minimum_surface_vertex_radial_distance_mm':round(float(np.linalg.norm(merged.vertices[:,[0,2]],axis=1).min()),5),
        'manufacturing_checks_pending':['final wearer size','casting-house wall/clearance review',
                                        'support placement','shrinkage allowance','finishing allowance',
                                        'physical comfort and snagging review'],
    }
    (OUT/'mesh-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'design-parameters.json').write_text(json.dumps(PARAMS,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    create()
    export()
