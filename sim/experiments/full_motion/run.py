"""Isolated, bounded virtual motion trials for the full CAD model."""
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import pwd
import re
import signal
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'sim/tools'))
from check_full_entry import validate_manifest,read_json,MANIFEST_REL,validate_environment
from check_hunter_full_scene import check_scene
from full_scene_session import stop_owned_processes
OUT=ROOT/'outputs/hunter_research_platform_20261031'

def check_identity():
    validate_environment(os.environ,Path('/proc/sys/kernel/osrelease').read_text(),pwd.getpwuid(os.getuid()).pw_name)
    if ROOT!=Path('/mnt/d/rob-memory'):raise ValueError('Only the reviewed desktop project is allowed')
    validate_manifest(read_json(ROOT/MANIFEST_REL),ROOT)
    return check_scene()

def make_world(token,target,profile='straight'):
    if re.fullmatch('[0-9a-f]{12}',token) is None or profile not in ('straight','left','right','collision','full_straight'):
        raise ValueError('Unapproved experiment identity or profile')
    tree=ET.parse(ROOT/'sim/scenes/hz_hunter_full.sdf')
    world=tree.getroot().find('world');world.set('name','hz_full_motion_'+token)
    # First verify mechanics without the cost of GPU sensor rendering. Geometry,
    # collision, inertia, wheel and steering joints and drive plugin stay intact.
    if profile!='full_straight':
        for plugin in list(world.findall('plugin')):
            if plugin.get('name') in ('ignition::gazebo::systems::Sensors','ignition::gazebo::systems::Imu'):
                world.remove(plugin)
        for link in world.findall('model/link'):
            for sensor in list(link.findall('sensor')):link.remove(sensor)
    for node in world.iter():
        if node.text and '/hz_sim/full' in node.text:node.text=node.text.replace('/hz_sim/full','/hz_sim/motion/'+token)
    if profile=='collision':
        obstacle=ET.SubElement(world,'model',name='motion_test_barrier')
        ET.SubElement(obstacle,'static').text='true'
        ET.SubElement(obstacle,'pose').text='1.4 0 0.6 0 0 0'
        link=ET.SubElement(obstacle,'link',name='barrier')
        for tag in ['collision','visual']:
            geometry=ET.SubElement(ET.SubElement(link,tag,name='barrier_'+tag),'geometry')
            ET.SubElement(ET.SubElement(geometry,'box'),'size').text='0.2 2 1.2'
    with target.open('wb') as f:tree.write(f,encoding='utf-8',xml_declaration=True)
    return tree

def yaw(p):
    q=p['orientation'];x,y,z,w=(q[k] for k in ['x','y','z','w'])
    return math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))

def assess(samples,profile):
    points={s['phase']:s for s in samples if 'phase'in s}
    a,b,c=(points[k] for k in ['settled','driven','stopped'])
    pa,pb=a['truth']['position'],b['truth']['position']
    dx,dy=pb['x']-pa['x'],pb['y']-pa['y']
    heading=yaw(a['truth']);forward=dx*math.cos(heading)+dy*math.sin(heading)
    lateral=-dx*math.sin(heading)+dy*math.cos(heading)
    angle=math.atan2(math.sin(yaw(b['truth'])-heading),math.cos(yaw(b['truth'])-heading))
    od=b['odom']['pose']['position'];oa=a['odom']['pose']['position']
    odom_distance=math.hypot(od['x']-oa['x'],od['y']-oa['y'])
    stop_speed=c['odom']['twist']['linear']['x']
    joints={j['name']:j['axis1'] for j in b['joints']['joint']}
    wheels=[joints[name+'_wheel_joint'] for name in ['front_left','front_right','rear_left','rear_right']]
    steer=[joints[name+'_steering_joint']['position'] for name in ['front_left','front_right']]
    odom_angle=yaw(b['odom']['pose'])-yaw(a['odom']['pose'])
    checks={'forward_displacement':forward>(.12 if profile=='full_straight' else .3),'finite_pose':all(math.isfinite(v) for v in [dx,dy,angle]),
            'upright_height':.10<c['truth']['position']['z']<.30,'brake':abs(stop_speed)<.015,
            'odom_distance_consistent':abs(odom_distance-math.hypot(dx,dy))<.10,
            'wheel_rotation':all(abs(w['position'])>1 and abs(w['velocity'])>.1 for w in wheels),
            'steering_limits':all(abs(s)<.58 for s in steer),
            'odom_yaw_consistent':abs(odom_angle-angle)<.04,
            'direction':abs(lateral)<.04 and abs(angle)<.05 if profile in ('straight','collision','full_straight') else angle*(1 if profile=='left' else -1)>.12}
    if profile in ('left','right'):
        checks['ackermann_inner_outer_order']=steer[0]>steer[1]>0 if profile=='left' else steer[1]<steer[0]<0
    if profile=='collision':
        checks.pop('odom_distance_consistent')
        # Contact may stop passive front wheels while driven rear wheels slip.
        # Wheel rotation is accepted separately by the unobstructed trials.
        checks.pop('wheel_rotation')
        checks['barrier_stops_body']=.40<forward<.535
        checks['no_barrier_penetration']=pb['x']+.815<1.35
    return {'checks':checks,'passed':all(checks.values()),'forward_m':forward,'lateral_m':lateral,
            'yaw_change_rad':angle,'odom_yaw_change_rad':odom_angle,'steering_angles_rad':steer,
            'odom_distance_m':odom_distance,'final_odom_speed_m_s':stop_speed,
            'wheel_angular_velocities_rad_s':[w['velocity'] for w in wheels],
            'odom_may_overestimate_when_wheels_slip':profile=='collision'}

def main():
    if sys.argv[1:] not in [[],['straight'],['left'],['right'],['collision'],['full_straight']]:raise SystemExit('Only a fixed test profile is accepted')
    profile=sys.argv[1] if len(sys.argv)>1 else 'straight'
    scene=check_identity();token=uuid.uuid4().hex[:12]
    run=OUT/'motion_trials'/(datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+profile+'_'+token)
    run.mkdir(parents=True)
    binary=OUT/'bin/full_motion_transport'
    if not binary.is_file():raise RuntimeError('Compile the reviewed Gazebo-only transport helper first')
    sdf=run/'world.sdf';make_world(token,sdf,profile)
    env=dict(os.environ,IGN_PARTITION='hz_sim_aphelios_73_motion_'+token,IGN_IP='127.0.0.1')
    for key in ['IGN_RELAY','IGN_GAZEBO_SYSTEM_PLUGIN_PATH','IGN_GAZEBO_RESOURCE_PATH','IGN_GAZEBO_SERVER_CONFIG_PATH']:env.pop(key,None)
    record={'profile':profile,'token':token,'partition':env['IGN_PARTITION'],'speed_m_s':.1,
            'angular_velocity_rad_s':.08 if profile=='left' else (-.08 if profile=='right' else 0),
            'sensors_enabled':profile=='full_straight','ros_actuation_bridge':False,'uses_ros_api':False,
            'experiment_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'sim/experiments/full_motion/transport.cc',binary]},
            'source_scene':scene,'world_sha256':hashlib.sha256(sdf.read_bytes()).hexdigest(),'state':'starting'}
    log=(run/'gazebo.log').open('wb');server=None;observer=None;observer_log=None
    try:
        server=subprocess.Popen(['/usr/bin/ign','gazebo','-s','-v','3',str(sdf)],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        record['created_server_pid']=server.pid
        time.sleep(3)
        if server.poll() is not None:raise RuntimeError('New isolated server exited during startup')
        if profile=='full_straight':
            observer_log=(run/'native_sensors.json').open('wb')
            observer=subprocess.Popen([str(OUT/'bin/full_sensor_observer'),'/hz_sim/motion/'+token],env=env,stdout=observer_log,stderr=subprocess.STDOUT,start_new_session=True)
        test=subprocess.run([str(binary),token,profile],env=env,capture_output=True,text=True,timeout=135)
        (run/'transport.jsonl').write_text(test.stdout,encoding='utf-8');(run/'transport.stderr.log').write_text(test.stderr,encoding='utf-8')
        record['transport_exit_code']=test.returncode
        if test.returncode:raise RuntimeError(test.stderr.strip())
        samples=[json.loads(line) for line in test.stdout.splitlines() if line.strip()]
        record['result']=assess(samples,profile);record['state']='completed'
        if observer:
            observer.wait(timeout=65);observer_log.flush()
            record['native_sensors']=json.loads((run/'native_sensors.json').read_text())
            record['result']['checks']['native_sensors_during_motion']=observer.returncode==0 and record['native_sensors'].get('ok')
            record['result']['passed']=all(record['result']['checks'].values())
    except Exception as error:
        record.update(state='failed',error=repr(error))
    finally:
        processes=[p for p in [server,observer] if p is not None]
        cleanup={'children':[{} for _ in processes]}
        stop_owned_processes(processes,cleanup)
        record['owned_process_groups_closed']=cleanup['cleanup_complete']
        if observer_log:observer_log.close()
        if server:
            record['owned_server_stopped']=server.poll() is not None
        log.close();(run/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'report':str(run/'result.json'),'state':record['state'],'result':record.get('result'),'error':record.get('error')},ensure_ascii=True))
    return 0 if record['state']=='completed' and record.get('result',{}).get('passed') and record.get('owned_process_groups_closed') else 1

if __name__=='__main__':raise SystemExit(main())
