"""Build the standalone lab navigation package (handoff task 1).

Copies the accepted 2026-11-01 map and the accepted 2-D scene into a new
experiment directory, rewrites the map YAML so its `image` field points at the
file that actually exists, re-points the wall mesh URI at the copied mesh, and
then measures the things the handoff asks to be checked: map/world agreement,
initial clearance, collision geometry presence and the unknown-cell policy.

Nothing outside the target directory is written.
"""
import hashlib
import json
import math
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
MAP_SRC = ROOT / 'outputs/lab_map_compare_20261105/lab_odom_06_new.pgm'
SCENE_SRC = ROOT / 'outputs/lab_scene_odom06_20261105/lab_scene_2d.sdf'
MESH_SRC = ROOT / 'outputs/lab_scene_odom06_20261105/walls.stl'
OUT = ROOT / 'outputs/lab_nav_20261105'

RES = 0.05
ORIGIN = (-5.09, -4.89)
START = (-0.21, -0.77, 0.0)          # x, y, yaw (base_link at rear-axle centre)
START_Z = 0.165
# Gazebo resolves URIs inside WSL, so the mesh path must be the mounted form,
# never the Windows drive form (file://D:/... fails with "A host is mandatory").
WSL_ROOT = '/mnt/d/rob-memory'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def world_to_cell(x, y, height):
    col = int(math.floor((x - ORIGIN[0]) / RES))
    row = height - 1 - int(math.floor((y - ORIGIN[1]) / RES))
    return col, row


def clearance_m(blocking, col, row):
    """Distance to the nearest blocking cell, in metres."""
    ys, xs = blocking.nonzero()
    if len(xs) == 0:
        return float('inf')
    d = ((xs - col) ** 2 + (ys - row) ** 2).min()
    return math.sqrt(float(d)) * RES


def main():
    pixels = Image.open(MAP_SRC).convert('L')
    width, height = pixels.size
    array = np.array(pixels)

    start_col, start_row = world_to_cell(START[0], START[1], height)
    start_value = int(array[start_row, start_col])

    OUT.mkdir(parents=True, exist_ok=True)
    map_out = OUT / 'lab_nav_map.pgm'
    mesh_out = OUT / 'walls.stl'
    scene_out = OUT / 'lab_nav_world.sdf'
    yaml_out = OUT / 'lab_nav_map.yaml'
    shutil.copy2(MAP_SRC, map_out)
    shutil.copy2(MESH_SRC, mesh_out)

    tree = ET.parse(SCENE_SRC)
    root = tree.getroot()
    mesh_uri = f'file://{WSL_ROOT}/{str(mesh_out.relative_to(ROOT)).replace(chr(92), "/")}'
    rewritten = 0
    for element in root.iter('uri'):
        if element.text and element.text.endswith('walls.stl'):
            element.text = mesh_uri
            rewritten += 1
    tree.write(scene_out, encoding='utf-8', xml_declaration=True)

    yaml_out.write_text(
        f'image: {map_out.name}\n'
        'mode: trinary\n'
        f'resolution: {RES}\n'
        f'origin: [{ORIGIN[0]}, {ORIGIN[1]}, 0]\n'
        'negate: 0\n'
        'occupied_thresh: 0.65\n'
        'free_thresh: 0.25\n',
        encoding='utf-8')

    classes = {
        'occupied': int((array == 0).sum()),
        'free': int((array == 254).sum()),
        'unknown': int((array == 205).sum()),
        'other': int(((array != 0) & (array != 254) & (array != 205)).sum()),
    }

    world = root.find('world')
    models = [m.get('name') for m in world.findall('model')]
    robot = world.find("model[@name='hz_hunter_full']")
    robot_pose = [float(v) for v in robot.find('pose').text.split()]
    collisions = len(robot.findall('.//collision'))
    sensors = [s.get('name') for s in robot.findall('.//sensor')]
    plugins = [p.get('name') for p in robot.findall('plugin')]

    checks = {
        'yaml_image_resolves': (OUT / yaml_out.read_text(encoding='utf-8').split('image:')[1].split()[0]).exists(),
        'map_dimensions': [width, height],
        'map_extent_m': [round(width * RES, 2), round(height * RES, 2)],
        'map_resolution': RES,
        'map_origin': list(ORIGIN),
        'map_classes': classes,
        'start_cell': [start_col, start_row],
        'start_cell_value': start_value,
        'start_cell_is_free': start_value == 254,
        'start_clearance_to_obstacle_m': round(clearance_m(array == 0, start_col, start_row), 2),
        'start_clearance_to_any_nonfree_m': round(
            clearance_m((array == 0) | (array == 205), start_col, start_row), 2),
        'world_name': world.get('name'),
        'models': models,
        'robot_pose': robot_pose,
        'robot_pose_matches_request': (
            abs(robot_pose[0] - START[0]) < 1e-6
            and abs(robot_pose[1] - START[1]) < 1e-6
            and abs(robot_pose[5] - START[2]) < 1e-6),
        'robot_collisions': collisions,
        'robot_sensors': sensors,
        'robot_plugins': plugins,
        'mesh_uri': mesh_uri,
        'mesh_uri_rewritten': rewritten == 2,
        'mesh_uri_uses_wsl_mount': mesh_uri.startswith('file:///mnt/d/'),
        'mesh_exists': mesh_out.exists(),
        'mesh_bytes': mesh_out.stat().st_size,
        'unknown_policy': 'unknown cells (205) are not free; map_server trinary publishes them '
                          'as unknown and the costmap treats them as impassable',
    }

    hashes = {
        'sources': {
            str(MAP_SRC.relative_to(ROOT)): sha256(MAP_SRC),
            str(SCENE_SRC.relative_to(ROOT)): sha256(SCENE_SRC),
            str(MESH_SRC.relative_to(ROOT)): sha256(MESH_SRC),
        },
        'outputs': {
            str(path.relative_to(ROOT)): sha256(path)
            for path in (map_out, mesh_out, scene_out, yaml_out)
        },
    }

    manifest = {
        'stage': 'handoff task 1 - standalone lab navigation scene',
        'date': '2026-11-05',
        'map_decision': 'unpatched 2026-11-01 lab_odom_06 (user decision: do not use the '
                        'old-map patched variant; new furniture is real)',
        'checks': checks,
        'hashes': hashes,
        'known_gaps': [
            'robot control plugin removed on purpose; restored in task 2',
            'world has no Sensors/Imu system plugin yet, so sensor tags emit nothing',
            'wall height 2.4 m is an engineering assumption, unknown cells carry no geometry',
        ],
    }
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                       encoding='utf-8')
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    print('hashes:', json.dumps(hashes['outputs'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
