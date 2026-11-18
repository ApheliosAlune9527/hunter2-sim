"""Does the new chassis contact sensor report a real hit and stay quiet otherwise?

Two phases, no teleporting.  A teleport of this model turns out to leave it immobile
until it is driven from the pose it woke up in, so both phases start from the spawn
pose and differ only in how far the vehicle is asked to go:

  A. short run: 2 s of forward motion in open floor.  The wheels touch the floor the
     whole time, so a sensor listening to the tyres would report constantly here.
     Expected: zero messages.
  B. long run: the same command until the vehicle reaches the wall about 4.9 m ahead.
     Expected: at least one message, naming chassis collisions.

Both halves have to pass: a sensor that never fires and one that always fires both fail.

Writes outputs/lab_nav_fix_20261106/contact_probe.json.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from ros_gz_interfaces.msg import Contacts

ROOT = Path('/mnt/d/rob-memory')
OUT = ROOT / 'outputs/lab_nav_fix_20261106'
WORLD = 'hz_lab_2d'
MODEL = 'hz_hunter_full'
SPEED = 0.15


def read_xy():
    p = subprocess.run(['timeout', '3', 'ign', 'topic', '-e', '-t',
                        f'/world/{WORLD}/pose/info'], capture_output=True, text=True)
    text = p.stdout
    idx = text.find(f'name: "{MODEL}"')
    while idx != -1:
        block = text[idx:idx + 500]
        if 'position {' in block:
            return (float(block.split('x: ')[1].split()[0]),
                    float(block.split('y: ')[1].split()[0]))
        idx = text.find(f'name: "{MODEL}"', idx + 1)
    return None


def main():
    rclpy.init()
    node = Node('contact_probe')
    node.set_parameters([rclpy.parameter.Parameter('use_sim_time', value=True)])
    pub = node.create_publisher(Twist, '/cmd_vel', 10)
    hits = []

    def on_contact(msg):
        names = sorted({c.collision1.name for c in msg.contacts} |
                       {c.collision2.name for c in msg.contacts})
        hits.append({'count': len(msg.contacts), 'collisions': [n for n in names if n]})

    node.create_subscription(Contacts, '/chassis_contact', on_contact, 10)

    def drive(seconds, speed=SPEED):
        cmd = Twist()
        cmd.linear.x = speed
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            pub.publish(cmd)
            rclpy.spin_once(node, timeout_sec=0.02)
        pub.publish(Twist())

    def idle(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.05)

    results = {}
    idle(1.0)

    start = read_xy()
    hits.clear()
    drive(2.0)
    idle(1.0)
    short = read_xy()
    results['short_run'] = {'from': start, 'to': short, 'messages': len(hits)}

    # Phase B continues from wherever phase A ended: run until the wall stops us.
    hits.clear()
    before = read_xy()
    end_time = time.monotonic() + 60
    cmd = Twist()
    cmd.linear.x = SPEED
    last = before
    still = 0
    while time.monotonic() < end_time:
        pub.publish(cmd)
        rclpy.spin_once(node, timeout_sec=0.02)
        pose = read_xy()
        if pose and last:
            moved = ((pose[0] - last[0]) ** 2 + (pose[1] - last[1]) ** 2) ** 0.5
            still = still + 1 if moved < 0.005 else 0
            last = pose
        if still >= 3:
            break
    pub.publish(Twist())
    idle(1.5)
    after = read_xy()
    results['wall_run'] = {'from': before, 'to': after, 'messages': len(hits),
                           'first': hits[:3]}

    ok = results['short_run']['messages'] == 0 and results['wall_run']['messages'] > 0
    doc = {'topic': '/chassis_contact',
           'world': str(OUT / 'lab_nav_world_contact.sdf'),
           'phases': results, 'ok': bool(ok),
           'teleport_note': 'no set_pose is used: a teleported vehicle stayed immobile, '
                            'which produced a false negative in the first attempt',
           'interpretation': ('silent on the open floor and loud at the wall is the only '
                              'combination that shows the sensor measures collisions '
                              'rather than ordinary wheel contact')}
    (OUT / 'contact_probe.json').write_text(json.dumps(doc, indent=1), encoding='utf-8')
    print(json.dumps({'short_run': results['short_run']['messages'],
                      'wall_run': results['wall_run']['messages'], 'ok': doc['ok']}, indent=1))
    node.destroy_node()
    rclpy.shutdown()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
