"""Build a conservative collision candidate from the user-selected personal map.

This is an engineering extrusion of observed occupied cells, not a certified
3-D reconstruction. Unknown cells remain unknown in the navigation map.
"""
from collections import deque
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'outputs/hunter_pcd_to_2d_20261029'
OUT=ROOT/'outputs/hunter_research_platform_20261031/lab_scene_candidate'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def rectangles(mask):
    active={};complete=[]
    for y,row in enumerate(mask):
        starts=np.flatnonzero(np.diff(np.r_[False,row,False].astype(np.int8))==1)
        ends=np.flatnonzero(np.diff(np.r_[False,row,False].astype(np.int8))==-1)
        current={}
        for x0,x1 in zip(starts,ends):
            key=(int(x0),int(x1));current[key]=active.pop(key,[int(x0),int(x1),y,y+1]);current[key][3]=y+1
        complete.extend(active.values());active=current
    complete.extend(active.values());return complete

def safe_centres(free,radius):
    # Conservative disc encloses the full rear-axle-centred footprint at every yaw.
    h,w=free.shape;unsafe=~free;blocked=np.zeros_like(free)
    for dy in range(-radius,radius+1):
        for dx in range(-radius,radius+1):
            if dx*dx+dy*dy>radius*radius:continue
            yd=slice(max(0,dy),min(h,h+dy));ys=slice(max(0,-dy),min(h,h-dy))
            xd=slice(max(0,dx),min(w,w+dx));xs=slice(max(0,-dx),min(w,w-dx))
            blocked[yd,xd]|=unsafe[ys,xs]
    safe=free&~blocked
    safe[:radius]=False;safe[-radius:]=False;safe[:,:radius]=False;safe[:,-radius:]=False
    return safe

def largest_component(mask):
    seen=np.zeros_like(mask);best=[]
    h,w=mask.shape
    for y,x in zip(*np.nonzero(mask)):
        if seen[y,x]:continue
        queue=deque([(int(y),int(x))]);seen[y,x]=True;points=[]
        while queue:
            cy,cx=queue.popleft();points.append((cy,cx))
            for yy,xx in [(cy-1,cx),(cy+1,cx),(cy,cx-1),(cy,cx+1)]:
                if 0<=yy<h and 0<=xx<w and mask[yy,xx] and not seen[yy,xx]:
                    seen[yy,xx]=True;queue.append((yy,xx))
        if len(points)>len(best):best=points
    return best

def el(parent,tag,text=None,**kw):
    node=ET.SubElement(parent,tag,kw)
    if text is not None:node.text=str(text)
    return node

def build():
    OUT.mkdir(parents=True,exist_ok=True)
    conversion=json.loads((SOURCE/'conversion_report.json').read_text(encoding='utf-8'))
    source=SOURCE/'lab_155236_floor_evidence_candidate.pgm'
    expected={Path(x['path'].replace('\\','/')).name:x['sha256'] for x in conversion['artifacts']}
    if sha(source)!=expected[source.name]:raise ValueError('Original map candidate changed')
    raw=ROOT/'maps/lab_20261011/lab_20261011_155236_369289/merged/map_raw.pcd'
    if sha(raw)!=conversion['inputs'][0]['sha256']:raise ValueError('Personal point cloud does not match the recorded source')
    pixels=np.array(Image.open(source));occupied=pixels==0;free=pixels==254
    if not set(np.unique(pixels)).issubset({0,205,254}):raise ValueError('Unexpected occupancy classes')
    h,w=pixels.shape;res=.05;origin=(-18.8,-29.95);boxes=rectangles(occupied)
    rebuilt=np.zeros_like(occupied)
    for x0,x1,y0,y1 in boxes:rebuilt[y0:y1,x0:x1]=True
    if not np.array_equal(rebuilt,occupied):raise ValueError('Collision rectangles changed the occupied mask')
    sdf=ET.Element('sdf',version='1.9');world=el(sdf,'world',name='hz_lab_155236_candidate')
    physics=el(world,'physics',name='lab_physics',type='ignored');el(physics,'max_step_size',.001)
    el(world,'gravity','0 0 -9.81')
    for name,slug in [('Physics','physics'),('UserCommands','user-commands'),('SceneBroadcaster','scene-broadcaster')]:
        el(world,'plugin',filename='libignition-gazebo-'+slug+'-system.so',name='ignition::gazebo::systems::'+name)
    light=el(world,'light',name='sun',type='directional');el(light,'pose','0 0 10 0 0 0');el(light,'diffuse','.9 .9 .9 1');el(light,'direction','-.5 -.3 -1')
    floor=el(world,'model',name='floor');el(floor,'static','true');link=el(floor,'link',name='floor')
    for tag in ['collision','visual']:
        node=el(link,tag,name='floor_'+tag);plane=el(el(node,'geometry'),'plane');el(plane,'normal','0 0 1');el(plane,'size','200 200')
    for i,(x0,x1,y0,y1) in enumerate(boxes):
        model=el(world,'model',name=f'observed_obstacle_{i:05d}');el(model,'static','true')
        cx=origin[0]+(x0+x1)*.5*res;cy=origin[1]+(h-(y0+y1)*.5)*res
        el(model,'pose',f'{cx:.6f} {cy:.6f} .75 0 0 0');link=el(model,'link',name='body')
        size=f'{(x1-x0)*res:.6f} {(y1-y0)*res:.6f} 1.5'
        for tag in ['collision','visual']:
            node=el(link,tag,name=tag);el(el(el(node,'geometry'),'box'),'size',size)
            if tag=='visual':material=el(node,'material');el(material,'ambient','.55 .6 .65 1');el(material,'diffuse','.55 .6 .65 1')
    ET.indent(sdf,space='  ')
    with (OUT/'lab_collision_candidate.sdf').open('wb') as f:ET.ElementTree(sdf).write(f,encoding='utf-8',xml_declaration=True)
    # Store the same exact boxes in one static triangle mesh. Thousands of
    # separate SDF models make semantic validation and physics startup costly.
    faces=[(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),
           (1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]
    mesh=OUT/'observed_obstacles.stl'
    with mesh.open('wb') as f:
        f.write(b'Observed occupancy boxes; conservative 1.5m extrusion'.ljust(80,b'\0'))
        f.write(struct.pack('<I',len(boxes)*12))
        for x0,x1,y0,y1 in boxes:
            lo=origin[0]+x0*res;hi=origin[0]+x1*res
            bottom=origin[1]+(h-y1)*res;top=origin[1]+(h-y0)*res
            v=np.array([(lo,bottom,0),(hi,bottom,0),(hi,top,0),(lo,top,0),
                        (lo,bottom,1.5),(hi,bottom,1.5),(hi,top,1.5),(lo,top,1.5)])
            for face in faces:
                a,b,c=v[list(face)];n=np.cross(b-a,c-a);n/=np.linalg.norm(n)
                f.write(struct.pack('<12fH',*n,*a,*b,*c,0))
    compact=copy.deepcopy(sdf);cw=compact.find('world');cw.set('name','hz_lab_155236_mesh_candidate')
    for model in list(cw.findall('model')):
        if model.get('name','').startswith('observed_obstacle_'):cw.remove(model)
    model=el(cw,'model',name='observed_obstacles');el(model,'static','true');link=el(model,'link',name='body')
    uri='file:///mnt/d/rob-memory/outputs/hunter_research_platform_20261031/lab_scene_candidate/observed_obstacles.stl'
    for tag in ['collision','visual']:
        node=el(link,tag,name=tag);el(el(el(node,'geometry'),'mesh'),'uri',uri)
    ET.indent(compact,space='  ')
    with (OUT/'lab_collision_mesh_candidate.sdf').open('wb') as f:ET.ElementTree(compact).write(f,encoding='utf-8',xml_declaration=True)
    shutil.copyfile(source,OUT/'navigation_map.pgm')
    (OUT/'navigation_map.yaml').write_text('image: navigation_map.pgm\nmode: trinary\nresolution: 0.05\norigin: [-18.8, -29.95, 0.0]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n',encoding='utf-8')
    safe=safe_centres(free,19);largest=largest_component(safe)
    rgb=np.repeat(pixels[:,:,None],3,axis=2);rgb[safe]=[80,190,120]
    image=Image.fromarray(rgb).resize((1337,738),Image.Resampling.NEAREST)
    canvas=Image.new('RGB',(1397,880),'white');canvas.paste(image,(30,80));d=ImageDraw.Draw(canvas)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',24)
    small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
    d.text((30,20),'User-selected personal map: 2026-10-11 15:52 (155236)',fill='black',font=font)
    d.text((30,825),'Black: observed obstacles | Gray: unknown | White: floor evidence | Green: conservative vehicle centres',fill='black',font=small)
    canvas.save(OUT/'map_candidate_preview.png')
    result={'map_selection':'User confirmed 155236 on 2026-10-31','source_pcd':str(raw),'source_pcd_sha256':sha(raw),
            'source_occupancy_sha256':sha(source),'resolution_m':res,'origin_xy_m':origin,'occupied_cells':int(occupied.sum()),
            'free_floor_evidence_cells':int(free.sum()),'unknown_cells':int((pixels==205).sum()),'collision_boxes':len(boxes),
            'occupied_mask_reproduced_exactly':True,'unknown_changed_to_free':False,
            'geometry_assumption':'Every observed occupied XY cell conservatively extruded from z=0 to 1.5m; not measured wall/object heights.',
            'compact_mesh':{'path':str(mesh),'sha256':sha(mesh),'triangles':len(boxes)*12,'sdf':'lab_collision_mesh_candidate.sdf','same_box_geometry':True},
            'conservative_all_yaw_footprint_radius_m':.95,'safe_centre_cells':int(safe.sum()),'largest_safe_component_cells':len(largest),
            'largest_safe_component_area_m2':len(largest)*res*res,'navigation_validated':False,'localization_validated':False,
            'status':'collision_geometry_candidate_requires_review'}
    (OUT/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))

if __name__=='__main__':build()
