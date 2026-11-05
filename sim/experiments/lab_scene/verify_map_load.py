"""Load the selected candidate in a private lifecycle map server; no control topics."""
from collections import Counter
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import time
import uuid

ROOT=Path('/mnt/d/rob-memory')
OUT=ROOT/'outputs/hunter_research_platform_20261031/lab_scene_candidate'

def main():
    expected={'WSL_DISTRO_NAME':'Ubuntu-22.04','ROS_DOMAIN_ID':'74','ROS_LOCALHOST_ONLY':'1','RMW_IMPLEMENTATION':'rmw_cyclonedds_cpp'}
    if pwd.getpwuid(os.getuid()).pw_name!='aphelios' or any(os.environ.get(k)!=v for k,v in expected.items()) or os.environ.get('CYCLONEDDS_URI'):
        raise RuntimeError('Private local ROS map-check environment is required')
    import rclpy
    from lifecycle_msgs.srv import ChangeState
    from lifecycle_msgs.msg import Transition
    from nav_msgs.msg import OccupancyGrid
    from rclpy.qos import QoSProfile,DurabilityPolicy,ReliabilityPolicy
    token=uuid.uuid4().hex[:12];ns='/hz_sim/research/map_check_'+token
    log=(OUT/'map_server.log').open('wb')
    server=subprocess.Popen(['/opt/ros/humble/lib/nav2_map_server/map_server','--ros-args','-r','__ns:='+ns,
                             '-p','yaml_filename:='+str(OUT/'navigation_map.yaml')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    result={'namespace':ns,'created_pid':server.pid,'motion_published':False,'navigation_goal_sent':False,'ok':False}
    rclpy.init();node=rclpy.create_node('map_verifier_'+token,namespace=ns,enable_rosout=False)
    maps=[]
    qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL,reliability=ReliabilityPolicy.RELIABLE)
    sub=node.create_subscription(OccupancyGrid,ns+'/map',lambda m:maps.append(m),qos)
    try:
        client=node.create_client(ChangeState,ns+'/map_server/change_state')
        if not client.wait_for_service(timeout_sec=12):raise RuntimeError('Private map lifecycle service missing')
        for transition in [Transition.TRANSITION_CONFIGURE,Transition.TRANSITION_ACTIVATE]:
            req=ChangeState.Request();req.transition.id=transition
            future=client.call_async(req);rclpy.spin_until_future_complete(node,future,timeout_sec=12)
            if not future.done() or not future.result().success:raise RuntimeError('Map lifecycle transition failed')
        deadline=time.monotonic()+12
        while not maps and time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.1)
        if not maps:raise RuntimeError('No occupancy grid received')
        m=maps[-1];counts=Counter(m.data)
        result.update(width=m.info.width,height=m.info.height,resolution=m.info.resolution,
                      origin_xy=[m.info.origin.position.x,m.info.origin.position.y],
                      counts={str(k):v for k,v in counts.items()},frame_id=m.header.frame_id)
        result['ok']=(m.info.width==1337 and m.info.height==738 and abs(m.info.resolution-.05)<1e-7
                      and counts==Counter({-1:924944,0:37031,100:24731}))
    except Exception as e:result['error']=repr(e)
    finally:
        node.destroy_node();rclpy.shutdown()
        if server.poll() is None:
            os.killpg(server.pid,signal.SIGINT)
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:os.killpg(server.pid,signal.SIGTERM);server.wait(timeout=5)
        log.close();result['owned_server_stopped']=server.poll() is not None
        (OUT/'ros_map_load_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))
    return 0 if result['ok'] else 1

if __name__=='__main__':raise SystemExit(main())
