"""Build the offline HUNTER CAD description from pinned data, using stdlib only.

This program never starts WSL, ROS, Gazebo, launch files, plugins or hardware.
Use --download only to retrieve missing, SHA256-pinned upstream data files.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import urllib.request
import xml.etree.ElementTree as ET

from hunter_sensor_profile import matrix_rpy, optical_to_engine, profile_report, relative_poses


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "sim/hz_hunter_full_description"
EVIDENCE = ROOT / "outputs/hunter_model_upgrade_20261030/references/geometry"
UPSTREAM = EVIDENCE / "upstream"
LOCAL = ROOT / "robot_assets/hunter_from_car_20261013_qjkgbbq5"
REFERENCE_URDF = ROOT / "outputs/hunter_sim_execution_20261012/references/hunter_reference_20261013.urdf"
REPOSITORY = "https://github.com/agilexrobotics/ugv_gazebo_sim"
COMMIT = "9d7888affce35321c657c1c8528307f3115b9d41"
PREFIX = "hunter/hunter2_base/"
PINS = {
    "meshes/base_link.STL": "2b3a9368436ee48505a9e48119f63be612407eb91a05a60e264248deded5f0cc",
    "meshes/front_left_wheel_link.STL": "a526ac8125c90f044c4977f659d050793a009197bb067ea9fe91c02b4cf9028a",
    "meshes/front_right_wheel_link.STL": "1a644b2ef550172ac8b255b84b6e30a39794fdf6680653698fdbee069beb91eb",
    "meshes/front_steer_left_link.STL": "091c1b863b790224b9affe5003f0fa79190d37bf037c69ffac4aa6b8f872a31f",
    "meshes/front_steer_right_link.STL": "5ed51bb9cda08f6940439761abf24bdf6950e37f6579d99880c320fc9b294db9",
    "meshes/front_steer_link.STL": "0299944ec73b0eff29b6d9887b4cb01ecce87d7a0a652a92ce6a8df783764c64",
    "meshes/left_rear_link.STL": "93cc252596d2d82947997694fd38299ec4733a49992e54f6bbac1c75f1f7b80f",
    "meshes/right_rear_link.STL": "220aba23b544d543b49305bd1ffc9b0f62223f2b38f88b6c8b738f4dcb00b996",
    "meshes/rear_wheel_link.STL": "f7db6f63c3fb6f19385af49b4468d09cf23ff22ba807d39a87361e545f24bebc",
    "package.xml": "142d5ae04f0b4225cfc79ba1802bfe89b5b6efe5fc0bd5cf6e0676ad897d5c11",
    "urdf/hunter2_base.urdf": "8cd98f8a5ae69b633798f1d808a7c913a4506e72c863ef11c266f21277383201",
}
WHEEL_SOURCES = {
    "rear_left": "left_rear_link", "rear_right": "right_rear_link",
    "front_left": "front_left_wheel_link", "front_right": "front_right_wheel_link",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vector(text):
    return tuple(float(value) for value in text.split())


def fmt(values):
    return " ".join(f"{value:.12g}" for value in values)


def rotation(rpy):
    roll, pitch, yaw = rpy
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return ((cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
            (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
            (-sp, cp * sr, cp * cr))


IDENTITY = rotation((0, 0, 0))


def apply_pose(point, pose):
    xyz, matrix = pose
    return tuple(xyz[i] + sum(matrix[i][j] * point[j] for j in range(3)) for i in range(3))


def compose(first, second):
    a, ra = first
    b, rb = second
    return apply_pose(b, first), tuple(tuple(sum(ra[i][k] * rb[k][j] for k in range(3))
                                           for j in range(3)) for i in range(3))


def link_poses(robot):
    poses = {"base_link": ((0, 0, 0), IDENTITY)}
    pending = list(robot.findall("joint"))
    while pending:
        old_count = len(pending)
        for joint in pending[:]:
            parent, child = joint.find("parent").get("link"), joint.find("child").get("link")
            if parent in poses:
                origin = joint.find("origin")
                poses[child] = compose(poses[parent], (vector(origin.get("xyz", "0 0 0")),
                                                       rotation(vector(origin.get("rpy", "0 0 0")))))
                pending.remove(joint)
        if old_count == len(pending):
            raise ValueError("Invalid link graph")
    return poses


def read_stl(path):
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + 50 * count:
        raise ValueError(f"Invalid binary STL: {path}")
    return [tuple(struct.unpack_from("<3f", data, 84 + i * 50 + 12 + j * 12) for j in range(3))
            for i in range(count)]


def mesh_points(triangles):
    return [point for triangle in triangles for point in triangle]


def bbox(points):
    lower = [min(point[i] for point in points) for i in range(3)]
    upper = [max(point[i] for point in points) for i in range(3)]
    return {"min": lower, "max": upper, "size": [upper[i] - lower[i] for i in range(3)]}


def transformed(triangles, pose):
    return [tuple(apply_pose(point, pose) for point in triangle) for triangle in triangles]


def write_stl(path, triangles):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(b"HUNTER2 pinned CAD; transforms baked; units metres".ljust(80, b"\0"))
        handle.write(struct.pack("<I", len(triangles)))
        for triangle in triangles:
            a, b, c = triangle
            u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
            normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            length = math.sqrt(sum(value * value for value in normal))
            normal = tuple(value / length for value in normal) if length > 1e-16 else (0, 0, 0)
            handle.write(struct.pack("<12fH", *normal, *a, *b, *c, 0))


def collada_points(path):
    document = ET.parse(path).getroot()
    ns = {"c": "http://www.collada.org/2005/11/COLLADASchema"}
    # The pinned local D435 file has a single node with identity transform.
    if any(document.findall(f".//c:node/c:{tag}", ns) for tag in ("matrix", "translate", "rotate", "scale")):
        raise ValueError("Camera DAE has changed: explicit node transform handling needed")
    points = []
    for mesh in document.findall(".//c:geometry/c:mesh", ns):
        source_ids = {element.get("source").removeprefix("#")
                      for element in mesh.findall("c:vertices/c:input[@semantic='POSITION']", ns)}
        for source in mesh.findall("c:source", ns):
            if source.get("id") in source_ids:
                values = vector(source.find("c:float_array", ns).text)
                points.extend(tuple(values[i:i + 3]) for i in range(0, len(values), 3))
    if not points:
        raise ValueError("No camera DAE positions")
    return points


def fetch_sources(allow_download):
    files = []
    for relative, digest in sorted(PINS.items()):
        repo_path = PREFIX + relative
        path = UPSTREAM / repo_path
        url = f"https://raw.githubusercontent.com/agilexrobotics/ugv_gazebo_sim/{COMMIT}/{repo_path}"
        if not path.exists():
            if not allow_download:
                raise FileNotFoundError(f"Missing pinned data {path}; use --download to retrieve data only")
            data = urllib.request.urlopen(url, timeout=60).read()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f"Downloaded data hash mismatch: {repo_path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        if sha256(path) != digest:
            raise ValueError(f"Pinned source hash mismatch: {path}")
        files.append({"repo_path": repo_path, "url": url, "sha256": digest,
                      "evidence_path": path.relative_to(ROOT).as_posix()})
    return files


def origin(parent, xyz=(0, 0, 0), rpy=(0, 0, 0)):
    return ET.SubElement(parent, "origin", xyz=fmt(xyz), rpy=fmt(rpy))


def inertial_box(link, mass, size, center=(0, 0, 0)):
    inertial = ET.SubElement(link, "inertial")
    origin(inertial, center)
    ET.SubElement(inertial, "mass", value=f"{mass:.12g}")
    x, y, z = size
    ET.SubElement(inertial, "inertia", ixx=f"{mass * (y*y + z*z)/12:.12g}",
                  iyy=f"{mass * (x*x + z*z)/12:.12g}", izz=f"{mass * (x*x + y*y)/12:.12g}",
                  ixy="0", ixz="0", iyz="0")


def inertial_wheel(link, mass, radius, width):
    inertial = ET.SubElement(link, "inertial")
    origin(inertial)
    ET.SubElement(inertial, "mass", value=f"{mass:.12g}")
    transverse = mass * (3 * radius * radius + width * width) / 12
    ET.SubElement(inertial, "inertia", ixx=f"{transverse:.12g}", iyy=f"{mass * radius * radius / 2:.12g}",
                  izz=f"{transverse:.12g}", ixy="0", ixz="0", iyz="0")


def collision_box(link, name, size, center=(0, 0, 0)):
    collision = ET.SubElement(link, "collision", name=name)
    origin(collision, center)
    ET.SubElement(ET.SubElement(collision, "geometry"), "box", size=fmt(size))


def collision_cylinder(link, name, radius, length, center=(0, 0, 0), rpy=(0, 0, 0)):
    collision = ET.SubElement(link, "collision", name=name)
    origin(collision, center, rpy)
    ET.SubElement(ET.SubElement(collision, "geometry"), "cylinder", radius=f"{radius:.12g}", length=f"{length:.12g}")


def visual_mesh(link, path, material, xyz=(0, 0, 0), rpy=(0, 0, 0), scale=(1, 1, 1)):
    visual = ET.SubElement(link, "visual")
    origin(visual, xyz, rpy)
    ET.SubElement(ET.SubElement(visual, "geometry"), "mesh",
                  filename="package://hz_hunter_full_description/" + path, scale=fmt(scale))
    if material:
        ET.SubElement(visual, "material", name=material)


def joint(robot, name, parent, child, xyz=(0, 0, 0), rpy=(0, 0, 0), kind="fixed", axis=None):
    node = ET.SubElement(robot, "joint", name=name, type=kind)
    ET.SubElement(node, "parent", link=parent)
    ET.SubElement(node, "child", link=child)
    origin(node, xyz, rpy)
    if axis:
        ET.SubElement(node, "axis", xyz=fmt(axis))
    if kind == "revolute":
        ET.SubElement(node, "limit", lower="-0.58", upper="0.58", effort="100", velocity="1")
        ET.SubElement(node, "dynamics", damping="0.3", friction="0.05")
    elif kind == "continuous":
        ET.SubElement(node, "limit", effort="100", velocity="12")
        ET.SubElement(node, "dynamics", damping="0.05", friction="0.02")
    return node


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build(allow_download=False):
    sensor_profile = profile_report(ROOT)
    upstream_files = fetch_sources(allow_download)
    (PACKAGE / "urdf").mkdir(parents=True, exist_ok=True)
    (PACKAGE / "meshes/upfit").mkdir(parents=True, exist_ok=True)
    upstream_root = UPSTREAM / PREFIX
    source_robot = ET.parse(upstream_root / "urdf/hunter2_base.urdf").getroot()
    source_poses = link_poses(source_robot)
    source_triangles = {link.get("name"): read_stl(upstream_root / "meshes" /
                                                Path(link.find("visual/geometry/mesh").get("filename")).name)
                        for link in source_robot.findall("link")}
    # Rear joint midpoint, expressed in the upstream CAD base frame. Its inverse
    # translation aligns the real chassis with the new rear-axle wheel-centre base.
    rear_midpoint = tuple((source_poses["left_rear_link"][0][i] + source_poses["right_rear_link"][0][i]) / 2
                          for i in range(3))
    chassis_shift = tuple(-value for value in rear_midpoint)
    normalized = {}
    normalization = {}
    body_points = []
    wheel_report = {}
    all_source_points = []
    for name, triangles in source_triangles.items():
        all_source_points.extend(mesh_points(transformed(triangles, source_poses[name])))
    for target, source in [("base_link", "base_link"), ("front_steer_bar_link", "front_steer_link"),
                           ("rear_axle_detail_link", "rear_wheel_link")]:
        pose = compose((chassis_shift, IDENTITY), source_poses[source])
        triangles = transformed(source_triangles[source], pose)
        path = f"meshes/chassis/{target}.stl"
        write_stl(PACKAGE / path, triangles)
        normalized[target] = path
        body_points.extend(mesh_points(triangles))
        normalization[target] = {"source_link": source, "source_rotation_matrix": source_poses[source][1],
                                 "baked_translation_m": pose[0], "bounds_m": bbox(mesh_points(triangles)),
                                 "triangles": len(triangles)}
    for wheel, source in WHEEL_SOURCES.items():
        world = transformed(source_triangles[source], source_poses[source])
        source_bounds = bbox(mesh_points(world))
        center = tuple((source_bounds["min"][i] + source_bounds["max"][i]) / 2 for i in range(3))
        local = transformed(world, (tuple(-value for value in center), IDENTITY))
        target = f"{wheel}_wheel_link"
        path = f"meshes/chassis/{target}.stl"
        write_stl(PACKAGE / path, local)
        normalized[target] = path
        wheel_position = (0.650 if wheel.startswith("front") else 0,
                          0.3025 if wheel.endswith("left") else -0.3025, 0)
        body_points.extend(apply_pose(point, (wheel_position, IDENTITY)) for point in mesh_points(local))
        normalization[target] = {"source_link": source, "source_zero_pose": source_poses[source],
                                 "source_world_bbox_center_m": center,
                                 "new_wheel_center_m": wheel_position,
                                 "world_reposition_delta_m": [wheel_position[i] - (center[i] + chassis_shift[i])
                                                               for i in range(3)],
                                 "method": "upstream zero-pose rotation, then bbox-centre subtraction; no scale/deformation",
                                 "bounds_m": bbox(mesh_points(local)), "triangles": len(local)}
        wheel_report[target] = {"mesh": path, "roll_axis": [0, 1, 0], "center_m": wheel_position,
                                "contact_radius_m": 0.165, "contact_width_m": 0.14,
                                "cad_bounds_m": bbox(mesh_points(local)), "source_link": source}

    local_sources = []
    used_local_files = [REFERENCE_URDF,
                       LOCAL / "realsense2_description/package.xml",
                       LOCAL / "hunter_description/package.xml"]
    for name in ("assembly.STL", "XT32.STL", "G60.STL", "ARS548.STL"):
        source = LOCAL / "hunter_description/meshes" / name
        shutil.copyfile(source, PACKAGE / "meshes/upfit" / name)
        used_local_files.append(source)
    camera_source = LOCAL / "realsense2_description/meshes/d435.dae"
    shutil.copyfile(camera_source, PACKAGE / "meshes/upfit/d435.dae")
    used_local_files.append(camera_source)
    # The local DAE has material colours and no external texture/image references.
    camera_points = collada_points(camera_source)
    local_sources.append({"path": (LOCAL / "hunter_description/meshes/D435i.STL").relative_to(ROOT).as_posix(),
                          "sha256": sha256(LOCAL / "hunter_description/meshes/D435i.STL"),
                          "usage": "alternative local camera CAD, not displayed; the reference URDF uses d435.dae"})
    for path in used_local_files:
        local_sources.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path),
                              "usage": "local robot export; visual/TF/provenance source"})
    for evidence in sensor_profile['sources']:
        local_sources.append({"path": evidence['path'], "sha256": evidence['sha256'],
                              "usage": "verified personal mapping settings/source; not executed"})

    robot = ET.Element("robot", name="hz_hunter_full")
    robot.append(ET.Comment("Generated from pinned upstream CAD and the local robot export. See source_manifest.json."))
    for name, color in (("chassis_silver", "0.79 0.82 0.86 1"), ("tire_dark", "0.12 0.12 0.13 1"),
                        ("mount_white", "0.88 0.88 0.88 1"), ("sensor_black", "0.1 0.1 0.1 1"),
                        ("lidar_grey", "0.3 0.3 0.3 1")):
        ET.SubElement(ET.SubElement(robot, "material", name=name), "color", rgba=color)
    masses = {}
    mass_methods = {}

    def physical_link(name, mass, size, center=(0, 0, 0), method="engineering box inertia assumption"):
        link = ET.SubElement(robot, "link", name=name)
        inertial_box(link, mass, size, center)
        masses[name] = mass
        mass_methods[name] = method
        return link

    base = physical_link("base_link", 47, (0.85, 0.48, 0.25), (0.325, 0, 0.055))
    visual_mesh(base, normalized["base_link"], "chassis_silver")
    collision_box(base, "battery_and_main_chassis", (0.85, 0.44, 0.205), (0.325, 0, 0.0425))
    collision_box(base, "top_deck", (0.90, 0.54, 0.055), (0.325, 0, 0.18))
    collision_box(base, "front_bumper", (0.05, 0.58, 0.08), (0.78, 0, 0.09))
    collision_box(base, "rear_bumper", (0.05, 0.58, 0.08), (-0.13, 0, 0.09))
    for wheel in WHEEL_SOURCES:
        side = "left" if wheel.endswith("left") else "right"
        position = wheel_report[f"{wheel}_wheel_link"]["center_m"]
        parent = "base_link"
        roll_position = position
        if wheel.startswith("front"):
            parent = f"front_{side}_steering_link"
            physical_link(parent, 0.3, (0.055, 0.055, 0.08))
            joint(robot, f"front_{side}_steering_joint", "base_link", parent, position,
                  kind="revolute", axis=(0, 0, 1))
            roll_position = (0, 0, 0)
        name = f"{wheel}_wheel_link"
        link = ET.SubElement(robot, "link", name=name)
        masses[name] = 5.5
        mass_methods[name] = "5.5 kg engineering allocation; solid cylinder inertia about Y; not a measured wheel mass"
        inertial_wheel(link, 5.5, 0.165, 0.14)
        visual_mesh(link, normalized[name], "tire_dark")
        collision_cylinder(link, "tire_contact", 0.165, 0.14, rpy=(math.pi / 2, 0, 0))
        joint(robot, f"{wheel}_wheel_joint", parent, name, roll_position, kind="continuous", axis=(0, 1, 0))
        gazebo = ET.SubElement(robot, "gazebo", reference=name)
        ET.SubElement(gazebo, "mu1").text = "0.8"
        ET.SubElement(gazebo, "mu2").text = "0.8"
    for name in ("front_steer_bar_link", "rear_axle_detail_link"):
        envelope = normalization[name]["bounds_m"]
        center = tuple((envelope["min"][i] + envelope["max"][i]) / 2 for i in range(3))
        link = physical_link(name, 0.2, envelope["size"], center,
                             "0.2 kg engineering detail allocation; box inertia centred on this component CAD envelope")
        visual_mesh(link, normalized[name], "chassis_silver")
        joint(robot, name.removesuffix("_link") + "_joint", "base_link", name)

    # Empty reference frames receive tiny finite inertias to keep importers valid.
    for name, parent, xyz in (("reference_base_link", "base_link", (0.325, 0, -0.165)),
                              ("hunter_link", "reference_base_link", (0, 0, 0.105))):
        physical_link(name, 0.001, (0.01, 0.01, 0.01), method="0.001 kg numerical frame proxy, not physical equipment")
        joint(robot, "reference_base_joint" if name == "reference_base_link" else "hunter_joint", parent, name, xyz)
    reference = ET.parse(REFERENCE_URDF).getroot()
    retained = ("assembly_link", "ars548_link", "gnss_link", "hesai_lidar", "camera_bottom_screw_frame", "camera_link")
    allocation = {"assembly_link": (4.0, (0.338, 0.346, 0.32), (-0.0176, -0.0021, 0.16)),
                  "ars548_link": (0.5, (0.06556, 0.137, 0.09), (-0.01787, 0, 0)),
                  "gnss_link": (0.5, (0.0492, 0.0425, 0.014), (0, 0, 0.007)),
                  "hesai_lidar": (0.8, (0.11, 0.11, 0.076), (0, 0, 0.038)),
                  "camera_bottom_screw_frame": (0.001, (0.01, 0.01, 0.01), (0, 0, 0)),
                  "camera_link": (0.072, (0.02505, 0.09, 0.025), (0, -0.0175, 0))}
    for name in retained:
        mass, size, center = allocation[name]
        link = physical_link(name, mass, size, center,
                             "reference nominal camera mass; recomputed box inertia" if name == "camera_link"
                             else "engineering equipment mass allocation; box inertia, uncalibrated")
        source_link = reference.find(f"link[@name='{name}']")
        for source_visual in source_link.findall("visual"):
            visual = copy.deepcopy(source_visual)
            mesh = visual.find("geometry/mesh")
            mesh.set("filename", "package://hz_hunter_full_description/meshes/upfit/" + Path(mesh.get("filename")).name)
            material = visual.find("material")
            if material is not None:
                material.set("name", {"White": "mount_white", "FlatBlack": "sensor_black", "DarkGrey": "lidar_grey"}[material.get("name")])
            link.append(visual)
        for source_joint in reference.findall("joint"):
            if source_joint.find("child").get("link") == name:
                robot.append(copy.deepcopy(source_joint))
        if name == "assembly_link":
            collision_box(link, "mount_bottom_plate", (0.338, 0.346, 0.008), (-0.0176, -0.0021, 0.004))
            for side, y in (("left", 0.125), ("right", -0.125)):
                collision_box(link, f"mount_{side}_post", (0.018, 0.018, 0.30), (-0.10, y, 0.158))
            collision_box(link, "mount_top_plate", (0.16, 0.23, 0.008), (0, 0, 0.312))
        elif name == "hesai_lidar":
            collision_cylinder(link, "lidar_housing", 0.055, 0.076, (0, 0, 0.038))
        elif name == "gnss_link":
            collision_cylinder(link, "gnss_housing", 0.025, 0.014, (0, 0, 0.007))
        elif name != "camera_bottom_screw_frame":
            collision_box(link, "sensor_housing", size, center)

    relative = relative_poses()
    imu_offset, imu_rotation = relative['imu_link']
    physical_link("imu_link", 0.001, (0.01, 0.01, 0.01),
                  method="0.001 kg numerical frame proxy; CH104 mapping-profile pose, physical accuracy unverified")
    joint(robot, "imu_joint", "hesai_lidar", "imu_link", imu_offset, matrix_rpy(imu_rotation))
    physical_link("camera_optical_frame", 0.001, (0.01, 0.01, 0.01),
                  method="0.001 kg numerical optical frame proxy; no equipment mass")
    optical_offset, optical_rotation = relative['camera_optical_frame']
    joint(robot, "camera_optical_joint", "hesai_lidar", "camera_optical_frame",
          optical_offset, matrix_rpy(optical_rotation))
    for name in ("lidar_joint", "camera_link_joint", "imu_joint", "camera_optical_joint"):
        ET.SubElement(ET.SubElement(robot, "gazebo", reference=name), "preserveFixedJoint").text = "true"

    ET.indent(robot, space="  ")
    urdf_path = PACKAGE / "urdf/hunter_full.urdf"
    ET.ElementTree(robot).write(urdf_path, encoding="utf-8", xml_declaration=True)
    with urdf_path.open("ab") as handle:
        handle.write(b"\n")
    poses = link_poses(robot)
    tf = {}
    for name, (xyz, matrix) in poses.items():
        rpy = (math.atan2(matrix[2][1], matrix[2][2]), math.asin(max(-1, min(1, -matrix[2][0]))),
               math.atan2(matrix[1][0], matrix[0][0]))
        tf[name] = {"xyz_m": list(xyz), "rpy_rad": list(rpy)}
    bare_mass = sum(masses[name] for name in ["base_link", "front_left_steering_link", "front_right_steering_link",
                                             "front_steer_bar_link", "rear_axle_detail_link",
                                             *(f"{wheel}_wheel_link" for wheel in WHEEL_SOURCES)])
    mesh_reports = {}
    for link in robot.findall("link"):
        for visual in link.findall("visual"):
            mesh = visual.find("geometry/mesh")
            path = PACKAGE / mesh.get("filename").split("hz_hunter_full_description/", 1)[1]
            points = camera_points if path.suffix.lower() == ".dae" else mesh_points(read_stl(path))
            scale = vector(mesh.get("scale", "1 1 1"))
            visual_origin = visual.find("origin")
            visual_pose = compose(poses[link.get("name")],
                                  (vector(visual_origin.get("xyz", "0 0 0")), rotation(vector(visual_origin.get("rpy", "0 0 0")))))
            world_points = [apply_pose(tuple(point[i] * scale[i] for i in range(3)), visual_pose) for point in points]
            mesh_reports[link.get("name")] = {"mesh": path.relative_to(PACKAGE).as_posix(),
                                               "bounds_in_base_m": bbox(world_points)}
    report = {"model_name": "hz_hunter_full", "coordinate_convention": "base_link at rear axle wheel-centre midpoint; X forward, Y left, Z up",
              "nominal_geometry_m": {"wheelbase": 0.650, "track": 0.605, "wheel_radius": 0.165},
              "bare_chassis_bounds_m": bbox(body_points), "upstream_zero_pose_bounds_m": bbox(all_source_points),
              "upstream_to_base_translation_m": chassis_shift,
              "normalization": normalization, "wheels": wheel_report,
              "excluded_visuals": {"front_steer_left_link.STL": "contains front wheel plus overlapping wheel/steering detail",
                                   "front_steer_right_link.STL": "duplicates the front right wheel",
                                   "hunter_2_0.STL": "whole chassis with embedded wheels; replaced by articulated manufacturer CAD",
                                   "PIPER.STL": "arm not installed / outside confirmed scope",
                                   "PiPER_plate.STL": "arm mount excluded with arm"},
              "tf_from_base_link": tf,
              "sensor_profile": sensor_profile,
              "reference_alignment": {"reference_base_link_xyz_m": [0.325, 0, -0.165],
                                      "reference_to_lidar_xyz_m": [0.214, 0, 0.690],
                                      "reference_to_lidar_yaw_rad": math.pi / 2,
                                      "status": "engineering registration of ground-centred local reference to rear-axle-centred model; not measured extrinsic calibration"},
              "sensor_carriers": {
                  "lidar": {"link": "hesai_lidar", **tf["hesai_lidar"], "status": "local exported TF preserved; physical calibration unverified"},
                  "camera": {"link": "camera_optical_frame", **tf["camera_optical_frame"],
                             "optical_frame": "camera_optical_frame", "visual_link": "camera_link",
                             "engine_rpy_rad": list(matrix_rpy(optical_to_engine(*poses['camera_optical_frame'])[1])),
                             "status": "existing mapping-profile optical frame; camera appearance mount retained; physical accuracy unverified"},
                  "imu": {"link": "imu_link", **tf["imu_link"], "lidar_to_imu_frame_xyz_m": list(imu_offset),
                          "status": "CH104 data frame from verified mapping settings/source; physical accuracy unverified"}},
              "visual_geometry": mesh_reports,
              "mass_assumptions": {"bare_chassis_kg": bare_mass, "extra_equipment_and_frame_proxies_kg": sum(masses.values()) - bare_mass,
                                   "total_kg": sum(masses.values()), "per_link_kg": masses, "methods": mass_methods,
                                   "basis": "70 kg bare HUNTER2 engineering target within supplied manufacturer 65–72 kg range; upper equipment masses are assumptions"},
              "collision_model": "separate convex primitives: split chassis boxes, Y-axis tire contact cylinders, mount bars/plates and sensor housings; never dynamic concave visual triangles",
              "uncalibrated": ["equipment mass and centre of mass", "inertia tensors and unsprung masses", "tire friction and contact stiffness",
                               "steering limits/rate/torque under load", "suspension/tire/motor response", "registration between manufacturer CAD and local upper-body export",
                               "sensor physical extrinsics and sensor noise/timing", "small frame proxy masses are numerical regularization, not measured hardware"],
              "validation_scope": "offline static geometry/URDF checks only; no simulator, WSL, hardware or motion command invoked by this builder"}
    write_json(PACKAGE / "geometry_report.json", report)
    (PACKAGE / "package.xml").write_text('''<?xml version="1.0"?>
<package format="3">
  <name>hz_hunter_full_description</name>
  <version>0.1.0</version>
  <description>Self-contained articulated HUNTER 2.0 CAD and local sensor mounting description.</description>
  <maintainer email="maintainer@example.invalid">Local simulation workspace</maintainer>
  <license>TODO: upstream CAD license unresolved; see SOURCE_NOTICE.md</license>
  <buildtool_depend>ament_cmake</buildtool_depend>
  <export><build_type>ament_cmake</build_type></export>
</package>
''', encoding="utf-8")
    (PACKAGE / "CMakeLists.txt").write_text('''cmake_minimum_required(VERSION 3.8)
project(hz_hunter_full_description)
find_package(ament_cmake REQUIRED)
install(DIRECTORY urdf meshes DESTINATION share/${PROJECT_NAME})
install(FILES source_manifest.json geometry_report.json README.md SOURCE_NOTICE.md DESTINATION share/${PROJECT_NAME})
ament_package()
''', encoding="utf-8")
    (PACKAGE / "SOURCE_NOTICE.md").write_text(f'''# Data source notice

Manufacturer split CAD and its original URDF/package metadata come from
{REPOSITORY}/tree/{COMMIT}/hunter/hunter2_base . The upstream package.xml license
field is literally `TODO`. No mesh license is invented or asserted here. The
unmodified original package.xml and all nine original STL files remain in the
geometry evidence folder; SHA256 values and exact raw URLs are in source_manifest.json.
This uncertainty remains relevant for any later redistribution.

Upper assembly, XT32, ARS548, G60, and camera appearance/TF come from the existing
local robot export, {LOCAL.relative_to(ROOT).as_posix()}. Camera d435.dae is copied
byte-for-byte, has embedded material colours and has no external texture files.
The local RealSense package.xml declares Apache-2.0; that declaration is preserved
as source evidence and does not resolve the manufacturer's separate CAD license.
The local hunter_description package metadata is also hashed in the manifest.

The camera optical and CH104 data frames use the existing personal FAST-LIVO2
configuration exported on 2026-10-30. The received YAML and source files are
hashed and read as evidence only. Their physical calibration accuracy is not
verified; the source serial publisher and mapping program are never executed.

The new URDF replaces upstream physical parameters and joint conventions. It
does not use or install upstream launch files, Classic plugins, CAN code, drivers,
or the local robot control packages. PIPER and its mounting plate are excluded.
''', encoding="utf-8")
    (PACKAGE / "README.md").write_text('''# HUNTER 2.0 complete geometry description

`urdf/hunter_full.urdf` is a self-contained CAD model named `hz_hunter_full`.
The origin is the rear axle wheel-centre midpoint. X points forward, Y left and Z
up. The four independent continuous wheel joints rotate about +Y. The front
steering joints rotate about +Z with limits ±0.58 rad. Nominal wheelbase is
0.650 m, track is 0.605 m and tire contact radius is 0.165 m.

The manufacturer chassis and four separate real wheel meshes are used. Wheel
zero-pose rotations are baked into metre-unit mesh copies, then each wheel is
recentred on its rolling axis. The source CAD tires have a roughly 0.328 m visual
diameter; the simple contact cylinders use the nominal 0.330 m diameter. Two
duplicate source steering meshes that already contain wheels are omitted. The
small distinct front steering bar and rear axle fitting remain fixed details.

The local assembly and sensor appearance retain the previous exported TF chain
through `reference_base_link`, located at (0.325, 0, -0.165) m in base_link. The
whole old chassis STL and the uninstalled mechanical arm/plate are excluded.
This registration is an engineering alignment, not an extrinsic calibration.

Sensor integration interfaces, in base_link coordinates:

| Carrier | xyz (m) | rpy (rad) | Basis |
| --- | --- | --- | --- |
| hesai_lidar | 0.539, 0, 0.525 | 0, 0, 1.570796326795 | Existing XT32 mount TF |
| camera_link | 0.65765, 0.0175, 0.481 | 0, 0, 0 | Existing camera mount TF |
| imu_link | 0.539, -0.110, 0.463 | 0, 0, 1.570796326795 | Existing CH104 mapping settings |
| camera_optical_frame | 0.644, 0.015, 0.475 | -1.570796326795, 0, -1.570796326795 | Existing lidar-to-camera mapping settings |

`camera_link` describes the visual housing mount and has +X forward.
`camera_optical_frame` describes the reused mapping optical origin and has +Z
forward. The RGBD engine is placed at that optical origin with its +X forward.
`imu_link` is the CH104 mapping data frame, rather than the D435i IMU. Its axes
follow the received publisher and mapping parameters. These settings are not
independent proof of physical calibration. These are carriers/TFs; engines belong to the
separate Fortress scene. Fixed-joint preservation hints keep carrier names
available to compatible URDF-to-SDF importers.

The bare chassis target mass is 70 kg. Additional equipment masses, finite frame
proxy masses, box/cylinder inertias, contact friction and simplified collision
shapes are engineering assumptions. Source CAD mass/zero inertias are not copied.
Every retained link has positive mass and a positive definite physically valid
inertia. Detailed allocations, extents, transforms, omitted parts and limitations
are in `geometry_report.json`. Physical dynamics have not been calibrated.

Build and test on Windows using Python only:

    python sim/tools/build_hunter_full_description.py
    python -m unittest discover -s sim/tools -p test_hunter_full_model.py -v

Add `--download` to the builder only if missing pinned source data must be
retrieved. It downloads pure data after validating pinned SHA256 values; it never
starts WSL, a simulator, ROS or hardware. Package resources are installed by the
ament_cmake data package. Licensing/source limitations are in SOURCE_NOTICE.md.
''', encoding="utf-8")
    outputs = []
    for path in sorted(PACKAGE.rglob("*")):
        if path.is_file() and path.name != "source_manifest.json":
            outputs.append({"path": path.relative_to(PACKAGE).as_posix(), "sha256": sha256(path)})
    manifest = {"schema_version": 1, "model_name": "hz_hunter_full",
                "upstream": {"repository": REPOSITORY, "branch_at_selection": "humble", "commit": COMMIT,
                             "license_note": "Upstream package.xml says TODO; no CAD license asserted or invented.",
                             "files": upstream_files},
                "local_sources": local_sources, "outputs": outputs,
                "sensor_profile": sensor_profile,
                "reference_urdf_canonical_sha256": hashlib.sha256(ET.canonicalize(REFERENCE_URDF.read_text(encoding="utf-8"), strip_text=True).encode("utf-8")).hexdigest(),
                "normalization": "All output STL copies use metres; source wheel zero-pose rotations baked, bbox-centred, moved to nominal axle/track coordinates; local sensor assets byte copies.",
                "excluded_assets": list(report["excluded_visuals"]),
                "builder": "sim/tools/build_hunter_full_description.py; Python standard library; no upstream code executed"}
    write_json(PACKAGE / "source_manifest.json", manifest)
    print(json.dumps({"urdf": str(urdf_path), "links": len(robot.findall("link")),
                      "moving_joints": sum(j.get("type") != "fixed" for j in robot.findall("joint")),
                      "bare_chassis_bounds_m": report["bare_chassis_bounds_m"], "total_mass_kg": sum(masses.values()),
                      "output_files": len(outputs)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="fetch missing SHA256-pinned pure data; never execute upstream files")
    build(parser.parse_args().download)
