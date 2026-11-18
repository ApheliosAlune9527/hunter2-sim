"""Derive the driveable lab world (handoff task 2) from the task-1 world.

Only additions and removals are recorded here so the diff against task 1 stays
auditable: Sensors system, AckermannSteering, JointStatePublisher and a single
2-D lidar; the RGB-D camera, the 32-beam lidar and the IMU are removed because
the first navigation baseline only needs odom + scan + clock.
"""
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'outputs/lab_nav_20261105/lab_nav_world.sdf'
DST = ROOT / 'outputs/lab_nav_20261105/lab_nav_world_drive.sdf'
MAP = ROOT / 'outputs/lab_nav_20261105/lab_nav_map.pgm'
MAP_YAML = ROOT / 'outputs/lab_nav_20261105/lab_nav_map.yaml'
NS = '/hz_sim/lab'
WALL_HEIGHT = 2.4
# 250 Hz. A 1 ms step costs the same wall-clock per iteration as 8 ms, so the
# larger step is nearly free throughput; motion accuracy is validated separately
# by test_drive_baseline.py.
MAX_STEP = 0.004

# Ackermann dims come from sim/hz_hunter_full_description/geometry_report.json:
# wheel_base 0.650, wheel_separation 0.605, wheel_radius 0.165.
WHEEL_BASE = 0.650
WHEEL_SEP = 0.605
WHEEL_RADIUS = 0.165
STEERING_LIMIT = 0.4          # plugin limit; joint hard limit is +/-0.58
JOINT_LIMIT = 0.58


def add_world_system(world, filename, name, extra=None):
    plugin = ET.SubElement(world, 'plugin', {'filename': filename, 'name': name})
    if extra:
        for key, value in extra.items():
            ET.SubElement(plugin, key).text = value
    return plugin


def map_rectangles():
    """Occupied cells -> maximal rectangles, in cell units."""
    pixels = np.array(Image.open(MAP).convert('L'))
    occupied = pixels == 0
    boxes = []
    for y, row in enumerate(occupied):
        edges = np.diff(np.r_[False, row, False].astype(np.int8))
        starts = np.flatnonzero(edges == 1)
        ends = np.flatnonzero(edges == -1)
        for x0, x1 in zip(starts, ends):
            boxes.append([int(x0), int(x1), int(y), int(y) + 1])
    boxes.sort(key=lambda b: (b[0], b[1], b[2]))
    merged, active = [], {}
    for x0, x1, y0, y1 in boxes:
        last = active.get((x0, x1))
        if last is not None and last[3] == y0:
            last[3] = y1
        else:
            new = [x0, x1, y0, y1]
            active[(x0, x1)] = new
            merged.append(new)
    return merged


def replace_wall_collision(world):
    """Swap the 1.3 MB trimesh collision for boxes (visual mesh stays)."""
    link = world.find("model[@name='walls']").find("link[@name='walls_link']")
    for collision in link.findall('collision'):
        link.remove(collision)
    text = MAP_YAML.read_text(encoding='utf-8')
    origin = [float(v) for v in re.search(r'origin:\s*\[([^\]]+)\]',
                                          text).group(1).split(',')]
    res = float(re.search(r'resolution:\s*([\d.]+)', text).group(1))
    rects = map_rectangles()
    rows = np.array(Image.open(MAP).convert('L')).shape[0]
    for x0, x1, y0, y1 in rects:
        cx = origin[0] + (x0 + x1) / 2.0 * res
        # ROS map rows run from the highest y downwards, so world y needs the flip.
        cy = origin[1] + (rows - (y0 + y1) / 2.0) * res
        collision = ET.SubElement(link, 'collision', {'name': f'w_{x0}_{y0}'})
        ET.SubElement(collision, 'pose').text = f'{cx:.4f} {cy:.4f} {WALL_HEIGHT / 2:.3f} 0 0 0'
        box = ET.SubElement(ET.SubElement(collision, 'geometry'), 'box')
        ET.SubElement(box, 'size').text = (f'{(x1 - x0) * res:.4f} '
                                           f'{(y1 - y0) * res:.4f} {WALL_HEIGHT}')
    return len(rects)


def main():
    tree = ET.parse(SRC)
    root = tree.getroot()
    world = root.find('world')

    changes = []

    # 1. Sensor rendering system: without it gpu_lidar never produces samples.
    add_world_system(world, 'ignition-gazebo-sensors-system',
                     'ignition::gazebo::systems::Sensors',
                     {'render_engine': 'ogre'})
    changes.append('added Sensors system (render_engine=ogre)')

    # Contact reporting: task 4 requires a collision source that is actually
    # observed, not inferred from a costmap.
    add_world_system(world, 'ignition-gazebo-contact-system',
                     'ignition::gazebo::systems::Contact')
    changes.append('added Contact system (/world/.../contacts)')

    step = world.find("physics[@name='lab_physics']").find('max_step_size')
    step.text = str(MAX_STEP)
    changes.append(f'physics max_step_size -> {MAX_STEP} s (250 Hz)')

    box_count = replace_wall_collision(world)
    changes.append(f'replaced mesh wall collision with {box_count} boxes')

    robot = world.find("model[@name='hz_hunter_full']")
    base = robot.find("link[@name='base_link']")

    # 2. Drop camera and IMU; replace the 32-beam lidar with a single-plane scan.
    for name in ('camera', 'imu', 'lidar'):
        for sensor in base.findall(f"sensor[@name='{name}']"):
            base.remove(sensor)
            changes.append(f'removed sensor {name}')

    scan = ET.SubElement(base, 'sensor', {'name': 'scan', 'type': 'gpu_lidar'})
    # 0.62 m：原 0.525 m 正好贴着 lidar 外壳碰撞圆柱的底面（z 0.525-0.601），
    # 扫描平面因此打到自身外壳，720 束全部返回最小量程 0.1 m。
    # 垂直必须 >=3 条：垂直 samples=1 时 gz 自身 vertical_angle_step 为 nan，
    # 桥接后的 LaserScan 也会退化成全 0.1 m。
    ET.SubElement(scan, 'pose').text = '0.539 0 0.62 0 -0 1.570796326795'
    ET.SubElement(scan, 'always_on').text = 'true'
    ET.SubElement(scan, 'update_rate').text = '10'
    ET.SubElement(scan, 'visualize').text = 'false'
    ET.SubElement(scan, 'topic').text = f'{NS}/scan'
    ET.SubElement(scan, 'ignition_frame_id').text = 'laser'
    lidar = ET.SubElement(scan, 'lidar')
    hscan = ET.SubElement(lidar, 'scan')
    horizontal = ET.SubElement(hscan, 'horizontal')
    ET.SubElement(horizontal, 'samples').text = '720'
    ET.SubElement(horizontal, 'resolution').text = '1'
    ET.SubElement(horizontal, 'min_angle').text = '-3.141592653589793'
    ET.SubElement(horizontal, 'max_angle').text = '3.141592653589793'
    vertical = ET.SubElement(hscan, 'vertical')
    ET.SubElement(vertical, 'samples').text = '3'
    ET.SubElement(vertical, 'resolution').text = '1'
    ET.SubElement(vertical, 'min_angle').text = '-0.017'
    ET.SubElement(vertical, 'max_angle').text = '0.017'
    rng = ET.SubElement(lidar, 'range')
    ET.SubElement(rng, 'min').text = '0.1'
    ET.SubElement(rng, 'max').text = '20'
    ET.SubElement(rng, 'resolution').text = '0.01'
    changes.append('added single-plane gpu_lidar -> %s/scan (720x3, 10 Hz, 0.1-20 m)' % NS)

    # 3. Drive plugin: the only ROS -> Gazebo velocity entry for this world.
    drive = ET.SubElement(robot, 'plugin', {
        'filename': 'ignition-gazebo-ackermann-steering-system',
        'name': 'ignition::gazebo::systems::AckermannSteering'})
    for tag, value in (
        ('left_joint', 'rear_left_wheel_joint'),
        ('right_joint', 'rear_right_wheel_joint'),
        ('left_steering_joint', 'front_left_steering_joint'),
        ('right_steering_joint', 'front_right_steering_joint'),
        ('topic', f'{NS}/cmd_vel'),
        ('odom_topic', f'{NS}/odom'),
        ('tf_topic', f'{NS}/tf'),
        ('frame_id', 'odom'),
        ('child_frame_id', 'base_link'),
        ('wheel_separation', str(WHEEL_SEP)),
        ('kingpin_width', str(WHEEL_SEP)),
        ('wheel_base', str(WHEEL_BASE)),
        ('wheel_radius', str(WHEEL_RADIUS)),
        ('steering_limit', str(STEERING_LIMIT)),
        ('min_velocity', '-0.3'),
        ('max_velocity', '0.3'),
        ('min_acceleration', '-0.2'),
        ('max_acceleration', '0.2'),
        ('odom_publish_frequency', '100.0'),
    ):
        ET.SubElement(drive, tag).text = value
    changes.append('added AckermannSteering -> %s/cmd_vel, %s/odom, %s/tf' % (NS, NS, NS))

    joints = ET.SubElement(robot, 'plugin', {
        'filename': 'ignition-gazebo-joint-state-publisher-system',
        'name': 'ignition::gazebo::systems::JointStatePublisher'})
    ET.SubElement(joints, 'topic').text = f'{NS}/joint_states'
    for joint in ('front_left_steering_joint', 'front_left_wheel_joint',
                  'front_right_steering_joint', 'front_right_wheel_joint',
                  'rear_left_wheel_joint', 'rear_right_wheel_joint'):
        ET.SubElement(joints, 'joint_name').text = joint
    changes.append('added JointStatePublisher -> %s/joint_states' % NS)

    # 4. Ground-truth odometry: the world-frame pose of the model, used only by the
    #    truth-localization evaluation and never fed back into the controller.
    truth = ET.SubElement(robot, 'plugin', {
        'filename': 'ignition-gazebo-odometry-publisher-system',
        'name': 'ignition::gazebo::systems::OdometryPublisher'})
    for tag, value in (('odom_frame', 'map'), ('robot_base_frame', 'base_link'),
                       ('odom_topic', f'{NS}/ground_truth'),
                       ('odom_publish_frequency', '100'),
                       ('dimensions', '2')):
        ET.SubElement(truth, tag).text = value
    changes.append('added OdometryPublisher -> %s/ground_truth (map-frame truth)' % NS)

    tree.write(DST, encoding='utf-8', xml_declaration=True)

    # Ackermann geometry: the steer angle is measured at the wheel, so the rear-axle
    # centre traces R = L / sin(delta). Using L/(2*delta) would be the small-angle
    # bicycle shortcut and underestimates the radius by roughly half.
    min_radius = WHEEL_BASE / math.sin(STEERING_LIMIT)
    joint_min_radius = WHEEL_BASE / math.sin(JOINT_LIMIT)
    inner = math.atan(WHEEL_BASE / (min_radius - WHEEL_SEP / 2.0))
    summary = {
        'world': str(DST.relative_to(ROOT)),
        'source': str(SRC.relative_to(ROOT)),
        'changes': changes,
        'geometry': {
            'wheel_base_m': WHEEL_BASE,
            'wheel_separation_m': WHEEL_SEP,
            'wheel_radius_m': WHEEL_RADIUS,
            'plugin_steering_limit_rad': STEERING_LIMIT,
            'joint_hard_limit_rad': JOINT_LIMIT,
            'min_turn_radius_from_plugin_limit_m': round(min_radius, 3),
            'min_turn_radius_from_joint_limit_m': round(joint_min_radius, 3),
            'inner_wheel_angle_at_plugin_limit_rad': round(inner, 3),
        },
        'sensors_kept': ['scan'],
        'sensors_removed': ['lidar(32 beam)', 'camera(rgbd)', 'imu'],
        'performance': {
            'max_step_size_s': MAX_STEP,
            'wall_collision': f'{box_count} boxes (visual still uses walls.stl)',
        },
    }
    (ROOT / 'outputs/lab_nav_20261105/drive_world_summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
