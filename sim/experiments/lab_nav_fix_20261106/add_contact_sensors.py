"""Add a contact sensor to the vehicle's chassis, and nothing else.

The previous round concluded "contact events are not supported" from a world that had
one Contact *system* plugin and zero contact *sensors*.  A system plugin publishes a
world-level contacts topic; it is not what reports a sensor's contacts.  This script
adds the sensor, attached to `base_link` and listening only to the eleven **chassis**
collisions -- the four tyre collisions are left out on purpose, so a wheel resting on
the floor is not reported as a collision and no filtering is needed afterwards.

Output world: outputs/lab_nav_fix_20261106/lab_nav_world_contact.sdf
Output bridge: sim/experiments/lab_nav_fix_20261106/lab_bridge_contact.yaml

Both are new files; the validated drive world is not modified.
"""
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path('/mnt/d/rob-memory')
HERE = ROOT / 'sim/experiments/lab_nav_fix_20261106'
OUT = ROOT / 'outputs/lab_nav_fix_20261106'
SRC_WORLD = ROOT / 'outputs/lab_nav_20261105/lab_nav_world_drive.sdf'
SRC_BRIDGE = HERE / 'lab_bridge_fix.yaml'
# Fortress ignores <topic> on a contact sensor and always publishes on the
# world-scoped path, so the bridge has to name that path exactly.  Verified with
# `ign topic -l` after the first attempt bridged a topic that never carried data.
TOPIC = '/world/hz_lab_2d/model/hz_hunter_full/link/base_link/sensor/chassis_contact/contact'


def main():
    tree = ET.parse(SRC_WORLD)
    root = tree.getroot()
    world = root.find('world')
    model = world.find("model[@name='hz_hunter_full']")
    if model is None:
        raise SystemExit('hz_hunter_full not found')
    link = model.find("link[@name='base_link']")
    if link is None:
        raise SystemExit('base_link not found')

    chassis = [c.get('name') for c in link.findall('collision')
               if 'wheel' not in c.get('name') and 'tire' not in c.get('name')]
    if len(chassis) < 5:
        raise SystemExit(f'expected the chassis collisions, found {len(chassis)}')

    sensor = ET.SubElement(link, 'sensor', {'name': 'chassis_contact', 'type': 'contact'})
    ET.SubElement(sensor, 'always_on').text = '1'
    ET.SubElement(sensor, 'update_rate').text = '50'
    # LIST_ALL=1 leaves the <contact> list out entirely, so the sensor watches every
    # collision on the link.  It exists to tell "the collision list is wrong" apart from
    # "this build never reports sensor contacts" -- two different fixes.
    import os
    if os.environ.get('LIST_ALL') == '1':
        print('[contact] LIST_ALL: the sensor watches every collision on base_link')
    else:
        contact = ET.SubElement(sensor, 'contact')
        for name in chassis:
            ET.SubElement(contact, 'collision').text = f'hz_hunter_full::base_link::{name}'

    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / 'lab_nav_world_contact.sdf'
    tree.write(dst, encoding='unicode', xml_declaration=True)

    # The bridge config is the same list plus one entry, so the two files cannot drift.
    bridge_text = SRC_BRIDGE.read_text(encoding='utf-8')
    entry = f'''  {{
    "ros_topic_name": "/chassis_contact",
    "gz_topic_name": "{TOPIC}",
    "ros_type_name": "ros_gz_interfaces/msg/Contacts",
    "gz_type_name": "ignition.msgs.Contacts",
    "direction": "GZ_TO_ROS",
    "lazy": false,
    "publisher_queue": 5,
    "subscriber_queue": 5
  }}
]'''
    if '"ros_topic_name": "/chassis_contact"' in bridge_text:
        raise SystemExit('bridge already has a contact entry')
    bridge_text = bridge_text.rstrip()
    if not bridge_text.endswith(']'):
        raise SystemExit('unexpected bridge file layout')
    bridge_text = bridge_text[:-1].rstrip().rstrip(',') + ',\n' + entry + '\n'
    (HERE / 'lab_bridge_contact.yaml').write_text(bridge_text, encoding='utf-8')

    doc = {'source_world': str(SRC_WORLD), 'output_world': str(dst),
           'topic': TOPIC, 'chassis_collisions': chassis,
           'excluded': 'front/rear tyre collisions, so normal wheel contact is not a hit',
           'sensor': {'name': 'chassis_contact', 'type': 'contact', 'update_rate': 50},
           'bridge': str(HERE / 'lab_bridge_contact.yaml')}
    (OUT / 'contact_sensor_setup.json').write_text(json.dumps(doc, indent=1), encoding='utf-8')
    print(json.dumps({'chassis_collisions': len(chassis), 'world': str(dst)}, indent=1))


if __name__ == '__main__':
    main()
