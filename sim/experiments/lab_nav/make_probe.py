"""Build probe worlds that remove one cost source at a time.

Usage: make_probe.py [--drop-sensors] [--drop-walls] [--box-walls]
Writes outputs/lab_nav_20261105/probe_<flags>.sdf and prints the path.
"""
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path('/mnt/d/rob-memory')
SRC = ROOT / 'outputs/lab_nav_20261105/lab_nav_world_drive.sdf'

ap = argparse.ArgumentParser()
ap.add_argument('--drop-sensors', action='store_true')
ap.add_argument('--drop-walls', action='store_true')
ap.add_argument('--box-walls', action='store_true')
ap.add_argument('--step-size', type=float)
ap.add_argument('--scan-hz', type=float)
args = ap.parse_args()

tree = ET.parse(SRC)
world = tree.getroot().find('world')

if args.drop_sensors:
    for plugin in list(world.findall('plugin')):
        if 'sensors-system' in plugin.get('filename', ''):
            world.remove(plugin)
    link = world.find("model[@name='hz_hunter_full']").find("link[@name='base_link']")
    for sensor in link.findall('sensor'):
        link.remove(sensor)

if args.drop_walls:
    walls = world.find("model[@name='walls']")
    if walls is not None:
        world.remove(walls)

if args.box_walls:
    # Replace the single triangle-mesh collision with one thin bounding wall so the
    # physics cost of "mesh vs boxes" can be compared directly.
    walls = world.find("model[@name='walls']")
    link = walls.find("link[@name='walls_link']")
    for name in ('walls_collision',):
        old = link.find(f"collision[@name='{name}']")
        if old is not None:
            link.remove(old)
    coll = ET.SubElement(link, 'collision', {'name': 'walls_collision'})
    geom = ET.SubElement(coll, 'geometry')
    # Rough stand-in: one long thin slab along the room's long axis.
    box = ET.SubElement(geom, 'box')
    ET.SubElement(box, 'size').text = '0.2 23.0 2.4'
    ET.SubElement(coll, 'pose').text = '-1.0 6.5 1.2 0 0 0'

if args.step_size:
    step = world.find("physics[@name='lab_physics']").find('max_step_size')
    step.text = str(args.step_size)

if args.scan_hz:
    link = world.find("model[@name='hz_hunter_full']").find("link[@name='base_link']")
    for sensor in link.findall("sensor[@name='scan']"):
        sensor.find('update_rate').text = str(args.scan_hz)

tags = ''.join(t for t, on in (('_no_sensor', args.drop_sensors),
                               ('_no_walls', args.drop_walls),
                               ('_box_walls', args.box_walls)) if on)
if args.step_size:
    tags += f'_step{args.step_size}'
if args.scan_hz:
    tags += f'_scan{args.scan_hz}'
tags = tags or '_full'
dst = ROOT / f'outputs/lab_nav_20261105/probe{tags}.sdf'
tree.write(dst, encoding='utf-8', xml_declaration=True)
print(dst)
