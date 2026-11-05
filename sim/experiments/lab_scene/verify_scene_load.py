"""Load the compact static lab candidate paused in a fresh Gazebo partition."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT=Path('/mnt/d/rob-memory')
sys.path.insert(0,str(ROOT/'sim/tools'))
from full_scene_session import stop_owned_processes
from check_full_entry import validate_environment
import pwd

def main():
    validate_environment(os.environ,Path('/proc/sys/kernel/osrelease').read_text(),pwd.getpwuid(os.getuid()).pw_name)
    out=ROOT/'outputs/hunter_research_platform_20261031/lab_scene_candidate'
    env=dict(os.environ,IGN_PARTITION='hz_sim_aphelios_73_lab_load_'+uuid.uuid4().hex[:12],IGN_IP='127.0.0.1')
    env.pop('IGN_RELAY',None)
    log=(out/'mesh_world_load.log').open('wb')
    p=subprocess.Popen(['/usr/bin/ign','gazebo','-s','-v','3',str(out/'lab_collision_mesh_candidate.sdf')],env=env,
                       stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    record={'created_pid':p.pid,'partition':env['IGN_PARTITION'],'robot_present':False,'motion_published':False,'physics_play_requested':False,'ok':False}
    try:
        deadline=time.monotonic()+25
        while time.monotonic()<deadline and p.poll() is None:
            services=subprocess.run(['/usr/bin/ign','service','-l'],env=env,capture_output=True,text=True,timeout=5)
            if '/world/hz_lab_155236_mesh_candidate/control' in services.stdout:
                record['world_control_service_available']=True;record['ok']=True;break
            time.sleep(.5)
    except Exception as error:record['error']=repr(error)
    finally:
        cleanup={'children':[{}]};stop_owned_processes([p],cleanup);log.close()
        record['owned_process_group_closed']=cleanup['cleanup_complete']
        text=(out/'mesh_world_load.log').read_text(encoding='utf-8',errors='replace')
        record['gazebo_error_lines']=[line for line in text.splitlines() if '[Err]' in line]
        if record['gazebo_error_lines']:record['ok']=False
        (out/'mesh_world_load_check.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record))
    return 0 if record['ok'] and record['owned_process_group_closed'] else 1

if __name__=='__main__':raise SystemExit(main())
