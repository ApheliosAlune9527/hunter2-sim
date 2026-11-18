"""Build a 3-D lab scene from a 2-D occupancy map by extruding thin walls.

Walls are the exact occupied cells merged into row runs, extruded to WALL_HEIGHT;
unknown cells produce no geometry; the floor is a plane for physics. The vehicle
is copied from the production scene with its control plugins removed and placed
at the requested start pose.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import struct

import numpy as np
from PIL import Image
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'outputs/lab_map_compare_20261105'
OUT = ROOT / 'outputs/lab_scene_odom06_20261105'
MAP = SRC / 'lab_odom_06_new.pgm'
YAML = SRC / 'lab_odom_06_new.yaml'
ROBOT_SCENE = ROOT / 'sim/scenes/hz_hunter_full.sdf'
WALL_HEIGHT = 2.4
RES = 0.05
WORLD = 'hz_lab_2d'
ROBOT = 'hz_hunter_full'
START = {'x': -0.21, 'y': -0.77, 'z': 0.165, 'yaw': 0.0, 'source': 'T1.0 chosen by user'}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_map():
    pixels = np.array(Image.open(MAP).convert('L'))
    origin = [float(v) for v in re.search(r'origin:\s*\[([^\]]+)\]',
                                          YAML.read_text(encoding='utf-8')).group(1).split(',')]
    return pixels, origin


def rectangles(mask):
    """Merge occupied cells into maximal horizontal runs."""
    boxes = []
    for y, row in enumerate(mask):
        edges = np.diff(np.r_[False, row, False].astype(np.int8))
        starts = np.flatnonzero(edges == 1)
        ends = np.flatnonzero(edges == -1)
        for x0, x1 in zip(starts, ends):
            boxes.append((int(x0), int(x1), int(y), int(y) + 1))
    return boxes


def write_stl(boxes, origin, height, path, rows):
    """Extrude occupied runs into a mesh.

    ROS map images store row 0 at the *highest* world y, so world y for image row
    ``r`` is ``origin.y + (rows - r) * RES``.  An earlier version used
    ``origin.y + r * RES``, which mirrored every wall about the map's horizontal
    centre line (fixed 2026-11-05: the robot spawned inside a phantom wall).
    """
    faces = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
             (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    with path.open('wb') as stream:
        stream.write(b'2D occupancy walls; extruded from lab_odom_06_filled'.ljust(80, b'\0'))
        stream.write(struct.pack('<I', len(boxes) * 12))
        for x0, x1, y0, y1 in boxes:
            lo = origin[0] + x0 * RES
            hi = origin[0] + x1 * RES
            bottom = origin[1] + (rows - y1) * RES
            top = origin[1] + (rows - y0) * RES
            vertices = np.array([(lo, bottom, 0), (hi, bottom, 0), (hi, top, 0), (lo, top, 0),
                                 (lo, bottom, height), (hi, bottom, height),
                                 (hi, top, height), (lo, top, height)])
            for face in faces:
                a, b, c = vertices[list(face)]
                normal = np.cross(b - a, c - a)
                length = np.linalg.norm(normal)
                normal = normal / length if length else normal
                stream.write(struct.pack('<12fH', *normal, *a, *b, *c, 0))


def element(parent, tag, text=None, **kwargs):
    node = ET.SubElement(parent, tag, **kwargs)
    if text is not None:
        node.text = str(text)
    return node


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    pixels, origin = load_map()
    occupied = pixels == 0
    height, width = pixels.shape
    boxes = rectangles(occupied)
    mesh = OUT / 'walls.stl'
    write_stl(boxes, origin, WALL_HEIGHT, mesh, height)

    sdf = ET.Element('sdf', version='1.9')
    world = element(sdf, 'world', name=WORLD)
    physics = element(world, 'physics', name='lab_physics', type='ignored')
    element(physics, 'max_step_size', 0.001)
    element(world, 'gravity', '0 0 -9.81')
    for name, slug in (('Physics', 'physics'), ('UserCommands', 'user-commands'),
                       ('SceneBroadcaster', 'scene-broadcaster')):
        element(world, 'plugin', filename='libignition-gazebo-' + slug + '-system.so',
                name='ignition::gazebo::systems::' + name)
    scene = element(world, 'scene')
    element(scene, 'ambient', '0.70 0.70 0.72 1')
    element(scene, 'background', '0.62 0.70 0.78 1')
    light = element(world, 'light', name='sun', type='directional')
    element(light, 'pose', '0 0 12 0 0 0')
    element(light, 'cast_shadows', 'false')
    element(light, 'diffuse', '0.40 0.40 0.40 1')
    element(light, 'specular', '0.05 0.05 0.05 1')
    element(light, 'direction', '-0.4 -0.3 -1')
    floor = element(world, 'model', name='floor')
    element(floor, 'static', 'true')
    link = element(floor, 'link', name='floor_link')
    for tag in ('collision', 'visual'):
        node = element(link, tag, name='floor_' + tag)
        plane = element(element(node, 'geometry'), 'plane')
        element(plane, 'normal', '0 0 1')
        element(plane, 'size', '200 200')

    walls = element(world, 'model', name='walls')
    element(walls, 'static', 'true')
    link = element(walls, 'link', name='walls_link')
    # Gazebo runs inside WSL, so the mesh URI must be the /mnt/d path, not D:\.
    wsl_relative = mesh.relative_to(ROOT).as_posix()
    uri = 'file:///mnt/d/rob-memory/' + wsl_relative
    for tag in ('collision', 'visual'):
        node = element(link, tag, name='walls_' + tag)
        element(element(element(node, 'geometry'), 'mesh'), 'uri', uri)
        if tag == 'visual':
            material = element(node, 'material')
            element(material, 'ambient', '0.80 0.81 0.83 1')
            element(material, 'diffuse', '0.85 0.86 0.88 1')
            element(material, 'emissive', '0.25 0.25 0.25 1')

    robot_tree = ET.parse(ROBOT_SCENE)
    robot = copy.deepcopy(robot_tree.find('world').find("model[@name='%s']" % ROBOT))
    for plugin in list(robot.findall('plugin')):
        robot.remove(plugin)
    robot.find('pose').text = '{:.4f} {:.4f} {:.4f} 0 0 {:.4f}'.format(
        START['x'], START['y'], START['z'], START['yaw'])
    robot.find('static').text = 'false'
    world.append(robot)
    ET.indent(sdf, space='  ')
    target = OUT / 'lab_scene_2d.sdf'
    with target.open('wb') as stream:
        ET.ElementTree(sdf).write(stream, encoding='utf-8', xml_declaration=True)

    known = int((pixels == 254).sum())
    result = {
        'source_map': str(MAP), 'source_map_sha256': sha(MAP),
        'resolution_m': RES, 'origin_m': origin,
        'map_cells': {'occupied': int(occupied.sum()), 'free': known,
                      'unknown': int((pixels == 205).sum())},
        'wall_height_m': WALL_HEIGHT,
        'wall_boxes': len(boxes), 'wall_mesh': str(mesh), 'wall_mesh_sha256': sha(mesh),
        'scene': str(target), 'world': WORLD,
        'vehicle_start': START,
        'generated': '2026-11-05',
        'unknown_geometry': 'none generated',
        'notes': ('Walls are the exact occupied cells extruded to WALL_HEIGHT; no furniture '
                  'height information exists in a 2-D map. Floor is a plane, so physics still '
                  'needs walls to block the vehicle.'),
    }
    (OUT / 'scene_manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                             encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    build()
