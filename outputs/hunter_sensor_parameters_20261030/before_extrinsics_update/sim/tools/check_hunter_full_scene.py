"""Strict, dependency-free HUNTER full-scene gate. Reads local files only.

``check_scene(scene_path=None, gui_path=None, manifest_path=None,
resource_root=None)`` returns a JSON-compatible PASS report or raises ValueError.
``resource_root`` is the repository root, including on Windows. Scene mesh URIs
always name the reviewed /mnt/f checkout; resource_root only maps those exact
allowlisted URIs to local files for offline checking. No URI is ever fetched.
"""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
NAME = "hz_hunter_full"
PACKAGE = "sim/hz_hunter_full_description"
URI_PREFIX = "file:///mnt/f/rob-memory/" + PACKAGE + "/"
SCENE_REL = "sim/scenes/hz_hunter_full.sdf"
GUI_REL = "sim/scenes/hz_hunter_full_gui.config"
MANIFEST_REL = "sim/scenes/hz_hunter_full_manifest.json"
INPUT_PATHS = {
    "converted_sdf": "outputs/hunter_model_upgrade_20261030/references/ament/hunter_full.converted.sdf",
    "conversion_urdf": "outputs/hunter_model_upgrade_20261030/references/ament/hunter_full_lump_input.urdf",
    "urdf": PACKAGE + "/urdf/hunter_full.urdf",
    "source_manifest": PACKAGE + "/source_manifest.json",
    "geometry_report": PACKAGE + "/geometry_report.json",
    "camera_source": "robot_assets/car_sensor_config_20261030/camera_d435i_640x480.yaml",
}
CAMERA_SOURCE_SHA256 = "790333f3aa749400429f27d0fa0838662dc8c65e5ad6e64b96dfa9de8d183daf"
CAMERA_SOURCE_FX = 606.7595825195312
CAMERA_FOV = 2 * math.atan(640 / (2 * CAMERA_SOURCE_FX))
CAMERA_MODEL = {
    "source": "camera_source", "source_stream": "D435i color 640x480 mapping configuration",
    "rendering": "Ogre1 centered square-pixel approximation",
    "fx": CAMERA_SOURCE_FX, "fy": CAMERA_SOURCE_FX, "cx": 320.0, "cy": 240.0,
    "depth_uses_color_approximation": True,
    "mounting_extrinsics_verified": False,
}
MESH_PATHS = (
    "meshes/chassis/base_link.stl", "meshes/chassis/front_left_wheel_link.stl",
    "meshes/chassis/front_right_wheel_link.stl", "meshes/chassis/front_steer_bar_link.stl",
    "meshes/chassis/rear_axle_detail_link.stl", "meshes/chassis/rear_left_wheel_link.stl",
    "meshes/chassis/rear_right_wheel_link.stl", "meshes/upfit/ARS548.STL",
    "meshes/upfit/assembly.STL", "meshes/upfit/d435.dae", "meshes/upfit/G60.STL",
    "meshes/upfit/XT32.STL",
)
WORLD_PLUGINS = {
    "Physics": "physics", "UserCommands": "user-commands",
    "SceneBroadcaster": "scene-broadcaster", "Sensors": "sensors", "Imu": "imu",
}
MODEL_PLUGINS = {"AckermannSteering": "ackermann-steering", "JointStatePublisher": "joint-state-publisher"}
CONTROL_TEXT = {
    "left_joint": "rear_left_wheel_joint", "right_joint": "rear_right_wheel_joint",
    "left_steering_joint": "front_left_steering_joint", "right_steering_joint": "front_right_steering_joint",
    "topic": "/hz_sim/full/cmd_vel", "odom_topic": "/hz_sim/full/odom", "tf_topic": "/hz_sim/full/tf",
    "frame_id": "hz_sim/full/odom", "child_frame_id": "hz_sim/full/base_link",
}
CONTROL_NUMBERS = {
    "wheel_separation": 0.605, "kingpin_width": 0.605, "wheel_base": 0.65, "wheel_radius": 0.165,
    "steering_limit": 0.4, "min_velocity": -0.3, "max_velocity": 0.3,
    "min_acceleration": -0.2, "max_acceleration": 0.2, "odom_publish_frequency": 30.0,
}
JOINTS = {
    "front_left_steering_joint": ("base_link", "front_left_steering_link", (0.65, 0.3025, 0, 0, 0, 0), (0, 0, 1)),
    "front_right_steering_joint": ("base_link", "front_right_steering_link", (0.65, -0.3025, 0, 0, 0, 0), (0, 0, 1)),
    "front_left_wheel_joint": ("front_left_steering_link", "front_left_wheel_link", (0, 0, 0, 0, 0, 0), (0, 1, 0)),
    "front_right_wheel_joint": ("front_right_steering_link", "front_right_wheel_link", (0, 0, 0, 0, 0, 0), (0, 1, 0)),
    "rear_left_wheel_joint": ("base_link", "rear_left_wheel_link", (0, 0.3025, 0, 0, 0, 0), (0, 1, 0)),
    "rear_right_wheel_joint": ("base_link", "rear_right_wheel_link", (0, -0.3025, 0, 0, 0, 0), (0, 1, 0)),
}
LINKS = {"base_link", *(spec[1] for spec in JOINTS.values())}
GUI_PLUGINS = {"MinimalScene", "GzSceneManager", "InteractiveViewControl", "WorldControl", "WorldStats",
               "EntityTree", "ComponentInspector", "Screenshot"}
SENSOR_SPECS = {
    "lidar": ("gpu_lidar", "hesai_lidar", "hz_sim/full/hesai_lidar", 10),
    "camera": ("rgbd_camera", "camera_link", "hz_sim/full/camera_optical_frame", 5),
    "imu": ("imu", "imu_link", "hz_sim/full/imu_link", 50),
}
STATIC_MODELS = {"ground_plane", "target_red", "target_green", "target_blue"}
TARGET_SPECS = {
    "target_red": ((4, 0, 0.65, 0, 0, 0), (0.4, 1.2, 1.3), (0.9, 0.12, 0.10, 1)),
    "target_green": ((3.5, 2, 0.5, 0, 0, 0), (0.6, 0.6, 1), (0.12, 0.8, 0.2, 1)),
    "target_blue": ((-3, -2, 0.75, 0, 0, 0), (0.5, 0.5, 1.5), (0.12, 0.3, 0.95, 1)),
}


def require(condition, message):
    if not condition:
        raise ValueError("Full scene check failed: " + message)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_file(root, relative):
    require(isinstance(relative, str) and relative and "\\" not in relative, "invalid local resource path")
    parts = PurePosixPath(relative)
    require(not parts.is_absolute() and not any(part in ("..", ".") for part in parts.parts)
            and ":" not in relative, "resource path escapes repository")
    path = root / relative
    require(path.resolve().is_relative_to(root.resolve()), "resource symlink escapes repository")
    require(path.is_file(), "missing local resource: " + relative)
    return path


def read_xml(path):
    text = path.read_text(encoding="utf-8")
    require(not re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.I), "external XML entity/DOCTYPE is forbidden")
    return ET.fromstring(text)


def parse_gui(text):
    require(not re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.I), "GUI external XML entity is forbidden")
    text = re.sub(r"^\s*<\?xml[^?]*\?>", "", text, count=1)
    return ET.fromstring("<gui>" + text + "</gui>")


def numbers(text, count, label):
    values = tuple(float(item) for item in (text or "").split())
    require(len(values) == count and all(math.isfinite(value) for value in values), label + " must be finite")
    return values


def close_values(text, expected, label):
    actual = numbers(text, len(expected), label)
    require(all(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-10) for a, b in zip(actual, expected)), label + " mismatch")


def exact_children(node, expected, label):
    require(Counter(child.tag for child in node) == Counter(list(expected)), label + " parameters missing, duplicate or unexpected")


def plugin_identity(short, slug):
    return {"filename": "ignition-gazebo-" + slug + "-system", "name": "ignition::gazebo::systems::" + short}


def check_plugins(parent, allowed, label):
    plugins = parent.findall("plugin")
    identities = [plugin_identity(short, slug) for short, slug in allowed.items()]
    require(len(plugins) == len(identities) and all(plugin.attrib in identities for plugin in plugins)
            and len({plugin.get("name") for plugin in plugins}) == len(identities), label + " plugin allowlist/uniqueness mismatch")
    return {plugin.get("name").split("::")[-1]: plugin for plugin in plugins}


def rpy_matrix(rpy):
    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return ((cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
            (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr), (-sp, cp * sr, cp * cr))


def sensor_poses(root, report):
    """Cross-check geometry evidence against the unchanged 19-link RSP URDF."""
    urdf = read_xml(local_file(root, INPUT_PATHS["urdf"]))
    require(urdf.get("name") == NAME and len(urdf.findall("link")) == 19, "URDF identity/link count mismatch")
    frames = {"base_link": ((0, 0, 0), rpy_matrix((0, 0, 0)))}
    pending = list(urdf.findall("joint"))
    while pending:
        progress = False
        for joint in pending[:]:
            parent, child = joint.find("parent").get("link"), joint.find("child").get("link")
            if parent not in frames:
                continue
            origin = joint.find("origin")
            xyz = numbers(origin.get("xyz", "0 0 0"), 3, "URDF pose")
            rotation = rpy_matrix(numbers(origin.get("rpy", "0 0 0"), 3, "URDF rotation"))
            previous_xyz, previous_rotation = frames[parent]
            frames[child] = (tuple(previous_xyz[i] + sum(previous_rotation[i][k] * xyz[k] for k in range(3)) for i in range(3)),
                             tuple(tuple(sum(previous_rotation[i][k] * rotation[k][j] for k in range(3)) for j in range(3)) for i in range(3)))
            pending.remove(joint)
            progress = True
        require(progress, "URDF has cyclic/disconnected joint tree")
    result = {}
    for name, (_, carrier, _, _) in SENSOR_SPECS.items():
        evidence = report["sensor_carriers"][name]
        require(evidence["link"] == carrier, "sensor carrier identity mismatch: " + name)
        xyz = tuple(evidence["xyz_m"])
        rpy = tuple(evidence["rpy_rad"])
        close_values(" ".join(map(str, xyz)), frames[carrier][0], name + " sensor URDF position")
        rotation = rpy_matrix(rpy)
        close_values(" ".join(str(v) for row in rotation for v in row),
                     tuple(v for row in frames[carrier][1] for v in row), name + " sensor URDF rotation")
        result[name] = (*xyz, *rpy)
    require(report["sensor_carriers"]["camera"]["optical_frame"] == "camera_optical_frame", "camera optical frame evidence mismatch")
    return result


def check_inertia(link):
    inertials = link.findall("inertial")
    require(len(inertials) == 1, "one inertia required per physical link")
    inertial = inertials[0]
    exact_children(inertial, ["pose", "mass", "inertia"], "inertia")
    numbers(inertial.findtext("pose"), 6, "inertia pose")
    mass = numbers(inertial.findtext("mass"), 1, "mass")[0]
    require(mass > 0, "mass must be positive")
    tensor = inertial.find("inertia")
    exact_children(tensor, ["ixx", "ixy", "ixz", "iyy", "iyz", "izz"], "inertia tensor")
    xx, yy, zz, xy, xz, yz = (numbers(tensor.findtext(key), 1, "inertia " + key)[0]
                             for key in ("ixx", "iyy", "izz", "ixy", "ixz", "iyz"))
    determinant = xx * yy * zz + 2 * xy * xz * yz - xx * yz * yz - yy * xz * xz - zz * xy * xy
    require(xx > 0 and xx * yy - xy * xy > 0 and determinant > 0, "inertia must be positive definite")
    require(all(a <= b + c + 1e-10 for a, b, c in ((xx, yy, zz), (yy, xx, zz), (zz, xx, yy))), "inertia violates triangle inequality")
    return mass


def check_collision(collision, static=False):
    geometries = collision.findall("geometry")
    require(len(geometries) == 1 and len(geometries[0]) == 1, "collision needs one primitive geometry")
    shape = geometries[0][0]
    allowed = {"box", "cylinder", "sphere"} | ({"plane"} if static else set())
    require(shape.tag in allowed, "collision must use an allowed primitive, never a mesh")
    fields = {"box": {"size": 3}, "cylinder": {"radius": 1, "length": 1}, "sphere": {"radius": 1},
              "plane": {"size": 2, "normal": 3}}[shape.tag]
    exact_children(shape, fields, "collision primitive")
    for key, count in fields.items():
        values = numbers(shape.findtext(key), count, "collision primitive " + key)
        require(all(value > 0 for value in values) if key != "normal" else values == (0, 0, 1), "collision primitive size/normal mismatch")
    if collision.find("pose") is not None:
        numbers(collision.findtext("pose"), 6, "collision pose")


def check_joints(model):
    joints = model.findall("joint")
    require(len(joints) == 6 and {j.get("name") for j in joints} == set(JOINTS), "joint count/identity mismatch")
    for joint in joints:
        name = joint.get("name")
        parent, child, pose, axis = JOINTS[name]
        require(joint.attrib == {"name": name, "type": "revolute"}, "joint type/attributes mismatch")
        exact_children(joint, ["pose", "parent", "child", "axis"], "joint")
        require(joint.findtext("parent") == parent and joint.findtext("child") == child, "joint parent/child topology mismatch")
        require(joint.find("pose").attrib == {"relative_to": parent}, "joint pose reference mismatch")
        close_values(joint.findtext("pose"), pose, "joint pose")
        close_values(joint.findtext("axis/xyz"), axis, "joint axis")
        steering = "steering" in name
        for key, expected in {"lower": -0.58 if steering else -1e16, "upper": 0.58 if steering else 1e16,
                              "effort": 100, "velocity": 1 if steering else 12}.items():
            close_values(joint.findtext("axis/limit/" + key), (expected,), "joint " + key)
        for value in joint.findall("axis/dynamics/*"):
            numbers(value.text, 1, "joint dynamics")


def signature(element):
    return (element.tag, tuple(sorted(element.attrib.items())), (element.text or "").strip(), tuple(signature(child) for child in element))


def check_conversion_inputs(original, conversion):
    expected = copy.deepcopy(original)
    for gazebo in expected.findall("gazebo"):
        for preserve in gazebo.findall("preserveFixedJoint"):
            gazebo.remove(preserve)
        if len(gazebo) == 0:
            expected.remove(gazebo)
    require(signature(expected) == signature(conversion), "conversion URDF must only remove preserveFixedJoint tags")


def check_preserved_conversion(model, source):
    # Independent semantic gates run first. This comparison additionally prevents
    # loss of CAD placements, fixed carrier frames, masses, or collision offsets.
    actual = copy.deepcopy(model)
    for child in list(actual):
        if child.tag in {"pose", "static", "plugin"}:
            actual.remove(child)
    for link in actual.findall("link"):
        for sensor in link.findall("sensor"):
            link.remove(sensor)
    expected = copy.deepcopy(source)
    for uri in expected.findall(".//mesh/uri"):
        prefix = "model://hz_hunter_full_description/"
        require((uri.text or "").startswith(prefix), "converted source mesh resource URI mismatch")
        uri.text = URI_PREFIX + uri.text.removeprefix(prefix)
    require(signature(actual) == signature(expected), "physical links/joints/frames/visual mesh placements differ from converted source")


def check_sensors(model, poses):
    sensors = model.findall(".//sensor")
    base = model.find("link[@name='base_link']")
    require(len(sensors) == 3 and len(base.findall("sensor")) == 3 and {s.get("name") for s in sensors} == set(SENSOR_SPECS), "sensor set/scope mismatch")
    for sensor in sensors:
        name = sensor.get("name")
        sensor_type, _, frame, rate = SENSOR_SPECS[name]
        require(sensor.attrib == {"name": name, "type": sensor_type}, name + " sensor type mismatch")
        detail = "lidar" if name == "lidar" else name
        exact_children(sensor, ["pose", "always_on", "update_rate", "visualize", "topic", "ignition_frame_id", detail], name + " sensor")
        require(sensor.find("pose").attrib == {}, name + " sensor pose must be base_link relative")
        close_values(sensor.findtext("pose"), poses[name], name + " sensor pose")
        require(sensor.findtext("always_on") == "true" and sensor.findtext("visualize") == "false", name + " sensor enable/visualize mismatch")
        close_values(sensor.findtext("update_rate"), (rate,), name + " sensor rate")
        require(sensor.findtext("topic") == "/hz_sim/full/" + name, name + " sensor topic mismatch")
        require(sensor.findtext("ignition_frame_id") == frame, name + " sensor frame mismatch")
        if name == "lidar":
            lidar = sensor.find("lidar")
            exact_children(lidar, ["scan", "range"], "lidar")
            exact_children(lidar.find("scan"), ["horizontal", "vertical"], "lidar scan")
            for axis, samples, lo, hi in (("horizontal", 720, -math.pi, math.pi), ("vertical", 32, math.radians(-16), math.radians(15))):
                node = lidar.find("scan/" + axis)
                exact_children(node, ["samples", "resolution", "min_angle", "max_angle"], "lidar scan " + axis)
                for key, expected in {"samples": samples, "resolution": 1, "min_angle": lo, "max_angle": hi}.items():
                    close_values(node.findtext(key), (expected,), "lidar " + axis + " " + key)
            exact_children(lidar.find("range"), ["min", "max", "resolution"], "lidar range")
            for key, expected in {"min": 0.1, "max": 20, "resolution": 0.01}.items():
                close_values(lidar.findtext("range/" + key), (expected,), "lidar range " + key)
        elif name == "camera":
            camera = sensor.find("camera")
            exact_children(camera, ["horizontal_fov", "image", "clip"], "camera")
            exact_children(camera.find("image"), ["width", "height", "format"], "camera image")
            exact_children(camera.find("clip"), ["near", "far"], "camera clip")
            for key, expected in {"horizontal_fov": CAMERA_FOV, "image/width": 640, "image/height": 480, "clip/near": 0.1, "clip/far": 20}.items():
                close_values(camera.findtext(key), (expected,), "camera " + key)
            require(camera.findtext("image/format") == "R8G8B8", "camera image format mismatch")
        else:
            require(len(sensor.find("imu")) == 0, "imu parameters must remain defaults")


def check_gui(gui):
    require(not gui.findall(".//include") and not gui.findall(".//uri"), "GUI include/resource reference forbidden")
    exact_children(gui, ["dialog", "window"] + ["plugin"] * 8, "GUI")
    allowed_tags = {"gui", "dialog", "window", "width", "height", "style", "menus", "drawer", "dialog_on_exit",
                    "plugin", "ignition-gui", "title", "property", "anchors", "line", "engine", "scene",
                    "ambient_light", "background_color", "camera_pose", "play_pause", "step", "start_paused",
                    "use_event", "sim_time", "real_time", "real_time_factor", "iterations"}
    require(all(node.tag in allowed_tags for node in gui.iter()), "GUI element/resource allowlist mismatch")
    require(all("://" not in (node.text or "") and all("://" not in value for value in node.attrib.values())
                for node in gui.iter()), "GUI external resource forbidden")
    plugins = gui.findall("plugin")
    require(len(plugins) == len(GUI_PLUGINS) and {p.get("filename") for p in plugins} == GUI_PLUGINS
            and len(gui.findall(".//plugin")) == len(plugins), "GUI plugin allowlist/uniqueness mismatch")
    minimal = gui.find("plugin[@filename='MinimalScene']")
    require(len(minimal.findall("engine")) == 1 and minimal.findtext("engine") == "ogre", "GUI engine must be ogre")
    numbers(minimal.findtext("camera_pose"), 6, "GUI camera pose")
    control = gui.find("plugin[@filename='WorldControl']")
    require(len(control.findall("start_paused")) == 1 and control.findtext("start_paused") == "true", "GUI must start_paused=true")
    require(control.findtext("play_pause") == "true", "GUI pause control required")
    require(all(p.get("filename") and set(p.attrib) == {"filename", "name"} for p in plugins), "GUI plugin attributes mismatch")
    for plugin in plugins:
        filename = plugin.get("filename")
        expected = ["ignition-gui"]
        if filename == "MinimalScene":
            expected += ["engine", "scene", "ambient_light", "background_color", "camera_pose"]
        elif filename == "WorldControl":
            expected += ["play_pause", "step", "start_paused", "use_event"]
        elif filename == "WorldStats":
            expected += ["sim_time", "real_time", "real_time_factor", "iterations"]
        exact_children(plugin, expected, "GUI plugin " + filename)


def check_manifest(data, root, scene_path, gui_path):
    require(data.get("schema_version") == 1 and data.get("model_name") == NAME, "manifest identity/schema mismatch")
    require(data.get("camera_model") == CAMERA_MODEL, "camera model provenance mismatch")
    require(set(data["inputs"]) == set(INPUT_PATHS), "manifest input allowlist mismatch")
    for key, relative in INPUT_PATHS.items():
        entry = data["inputs"][key]
        require(entry.get("path") == relative, "manifest input resource path mismatch")
        require(entry.get("sha256") == sha256(local_file(root, relative)), "input SHA256 mismatch: " + key)
    require(data["inputs"]["camera_source"]["sha256"] == CAMERA_SOURCE_SHA256, "camera source SHA256 mismatch")
    require(set(data["artifacts"]) == {"scene", "gui"}, "manifest artifact allowlist mismatch")
    for key, path, relative in (("scene", scene_path, SCENE_REL), ("gui", gui_path, GUI_REL)):
        entry = data["artifacts"][key]
        require(entry.get("path") == relative, "artifact resource path mismatch")
        require(entry.get("sha256") == sha256(path), "artifact SHA256 mismatch: " + key)
    source = json.loads(local_file(root, INPUT_PATHS["source_manifest"]).read_text(encoding="utf-8"))
    require(source.get("model_name") == NAME, "source manifest identity mismatch")
    outputs = source["outputs"]
    require(len({entry["path"] for entry in outputs}) == len(outputs), "source manifest duplicate resource")
    hashes = {entry["path"]: entry["sha256"] for entry in outputs}
    for relative in ("geometry_report.json", "urdf/hunter_full.urdf", *MESH_PATHS):
        require(relative in hashes and hashes[relative] == sha256(local_file(root, PACKAGE + "/" + relative)), "source manifest SHA256 mismatch: " + relative)
    entries = data["meshes"]
    require(len(entries) == len(MESH_PATHS) and {entry["path"] for entry in entries} == set(MESH_PATHS), "manifest mesh resource allowlist mismatch")
    for entry in entries:
        relative = entry["path"]
        require(entry.get("uri") == URI_PREFIX + relative and entry.get("sha256") == hashes[relative], "mesh resource URI/SHA256 mismatch")
    check_conversion_inputs(read_xml(local_file(root, INPUT_PATHS["urdf"])),
                            read_xml(local_file(root, INPUT_PATHS["conversion_urdf"])))
    # The reviewed Collada embeds all materials. Do not let it acquire a remote
    # texture or a second, unmanifested local resource through a nested reference.
    collada = read_xml(local_file(root, PACKAGE + "/meshes/upfit/d435.dae"))
    for node in collada.iter():
        require(not node.tag.endswith("init_from"), "unmanifested Collada texture resource")
        for key in ("url", "source", "target"):
            if key in node.attrib:
                require(node.get(key).startswith("#"), "external Collada resource forbidden")


def validate_scene(root, gui, resource_root):
    require(root.tag == "sdf" and root.attrib == {"version": "1.9"} and len(root) == 1 and root[0].tag == "world", "one SDF 1.9 world required")
    world = root[0]
    require(world.attrib == {"name": NAME}, "world identity mismatch")
    require(not root.findall(".//include"), "include forbidden")
    exact_children(world, ["physics", "gravity", "scene", "light"] + ["plugin"] * 5 + ["model"] * 5,
                   "world plugin/model")
    scene = world.find("scene")
    exact_children(scene, ["ambient", "background", "shadows"], "scene resource")
    close_values(scene.findtext("ambient"), (0.5, 0.5, 0.5, 1), "scene ambient")
    close_values(scene.findtext("background"), (0.75, 0.83, 0.89, 1), "scene background")
    require(scene.findtext("shadows") == "true", "scene shadows mismatch")
    light = world.find("light")
    require(light.attrib == {"name": "sun", "type": "directional"}, "light identity mismatch")
    exact_children(light, ["pose", "cast_shadows", "diffuse", "specular", "attenuation", "direction"], "light resource")
    for key, values in {"pose": (0, 0, 10, 0, 0, 0), "diffuse": (0.85, 0.85, 0.85, 1),
                        "specular": (0.2, 0.2, 0.2, 1), "direction": (-0.5, -0.3, -1)}.items():
        close_values(light.findtext(key), values, "light " + key)
    exact_children(light.find("attenuation"), ["range", "constant", "linear", "quadratic"], "light attenuation")
    for key, value in {"range": 1000, "constant": 0.9, "linear": 0.01, "quadratic": 0.001}.items():
        close_values(light.findtext("attenuation/" + key), (value,), "light attenuation " + key)
    models = world.findall("model")
    require(len(models) == 5 and {m.get("name") for m in models} == STATIC_MODELS | {NAME}
            and len(world.findall(".//model")) == 5, "world model allowlist mismatch")
    model = world.find("model[@name='hz_hunter_full']")
    require(model.attrib == {"name": NAME}, "model identity mismatch")
    close_values(model.findtext("pose"), (0, 0, 0.167, 0, 0, 0), "model initial pose")
    require(model.find("pose").attrib == {}, "model initial pose must use the world reference")
    require(len(model.findall("pose")) == 1 and len(model.findall("static")) == 1 and model.findtext("static") == "false", "model static flag must be false")
    world_plugins = check_plugins(world, WORLD_PLUGINS, "world")
    model_plugins = check_plugins(model, MODEL_PLUGINS, "model")
    require(len(root.findall(".//plugin")) == 7, "unexpected nested plugin")
    for short, plugin in world_plugins.items():
        exact_children(plugin, ["render_engine"] if short == "Sensors" else [], "world plugin " + short)
        if short == "Sensors":
            require(plugin.findtext("render_engine") == "ogre", "Sensors plugin engine must be ogre")
    controller = model_plugins["AckermannSteering"]
    exact_children(controller, [*CONTROL_TEXT, *CONTROL_NUMBERS], "controller")
    for key, value in CONTROL_TEXT.items():
        require(controller.findtext(key) == value, "controller " + key + " mismatch")
    for key, value in CONTROL_NUMBERS.items():
        close_values(controller.findtext(key), (value,), "controller " + key)
    publisher = model_plugins["JointStatePublisher"]
    exact_children(publisher, ["topic"] + ["joint_name"] * 6, "joint state publisher")
    require(publisher.findtext("topic") == "/hz_sim/full/joint_states", "joint state topic mismatch")
    require(Counter(node.text for node in publisher.findall("joint_name")) == Counter(JOINTS.keys()), "joint state joint_name set mismatch")
    links = model.findall("link")
    require(len(links) == 7 and {link.get("name") for link in links} == LINKS, "physical link identity/count mismatch")
    mass = sum(check_inertia(link) for link in links)
    for link in links:
        for collision in link.findall("collision"):
            check_collision(collision)
    check_joints(model)
    meshes = model.findall(".//visual/geometry/mesh")
    allowed_uris = {URI_PREFIX + relative for relative in MESH_PATHS}
    require(len(meshes) == 12 and {mesh.findtext("uri") for mesh in meshes} == allowed_uris, "visual mesh resource allowlist/count mismatch")
    all_uris = root.findall(".//uri")
    require(len(all_uris) == 12 and {uri.text for uri in all_uris} == allowed_uris and len(root.findall(".//mesh")) == 12, "unexpected mesh/non-mesh resource URI")
    for mesh in meshes:
        exact_children(mesh, ["scale", "uri"], "visual mesh")
        millimetre_cad = mesh.findtext("uri").endswith(("assembly.STL", "ARS548.STL", "G60.STL", "XT32.STL"))
        scale = 0.001 if millimetre_cad else 1
        close_values(mesh.findtext("scale"), (scale, scale, scale), "visual mesh scale")
    require(len(world.findall("physics")) == 1, "one physics element required")
    physics = world.find("physics")
    require(physics.attrib == {"name": "hz_full_physics", "type": "ignored"}, "physics identity mismatch")
    exact_children(physics, ["max_step_size", "real_time_factor"], "physics")
    close_values(physics.findtext("max_step_size"), (0.001,), "physics step")
    close_values(physics.findtext("real_time_factor"), (1,), "physics rate")
    require(len(world.findall("gravity")) == 1, "one gravity element required")
    close_values(world.findtext("gravity"), (0, 0, -9.81), "gravity")
    for static_model in models:
        if static_model is model:
            continue
        name = static_model.get("name")
        expected_tags = ["static", "link"] + (["pose"] if name in TARGET_SPECS else [])
        exact_children(static_model, expected_tags, "static environment model")
        require(static_model.attrib == {"name": name} and static_model.findtext("static") == "true", "static environment model mismatch")
        require(not static_model.findall(".//sensor") and not static_model.findall("joint"), "static environment has sensor/joint")
        link = static_model.find("link")
        require(link.attrib == {"name": "body" if name in TARGET_SPECS else "ground"}, "static environment link identity mismatch")
        exact_children(link, ["collision", "visual"], "static environment link")
        for tag in ("collision", "visual"):
            component = link.find(tag)
            expected_name = name + "_" + tag if name in TARGET_SPECS else "ground_" + tag
            require(component.attrib == {"name": expected_name}, "static environment component identity mismatch")
            exact_children(component, ["geometry"] + (["material"] if tag == "visual" else []), "static environment component")
            check_collision(component, static=True)
            shape = component.find("geometry")[0]
            require(shape.tag == ("box" if name in TARGET_SPECS else "plane"), "static environment geometry mismatch")
            expected_size = TARGET_SPECS[name][1] if name in TARGET_SPECS else (20, 20)
            close_values(shape.findtext("size"), expected_size, "static environment size")
            if tag == "visual":
                exact_children(component.find("material"), ["ambient", "diffuse"], "static environment material")
                color = TARGET_SPECS[name][2] if name in TARGET_SPECS else (0.55, 0.58, 0.60, 1)
                close_values(component.findtext("material/ambient"), color, "static environment color")
                close_values(component.findtext("material/diffuse"), color, "static environment color")
        if name in TARGET_SPECS:
            close_values(static_model.findtext("pose"), TARGET_SPECS[name][0], "static target pose")
            require(static_model.find("pose").attrib == {}, "static target pose must use the world reference")
    ground = world.find("model[@name='ground_plane']")
    close_values(ground.findtext("link/collision/geometry/plane/size"), (20, 20), "ground size")
    require(len(root.findall(".//sensor")) == 3, "unexpected sensor scope")
    report = json.loads(local_file(resource_root, INPUT_PATHS["geometry_report"]).read_text(encoding="utf-8"))
    poses = sensor_poses(resource_root, report)
    check_sensors(model, poses)
    converted = read_xml(local_file(resource_root, INPUT_PATHS["converted_sdf"]))
    check_preserved_conversion(model, converted.find("model"))
    check_gui(gui)
    return {"status": "PASS", "world": NAME, "model": NAME, "physical_links": len(links), "active_joints": 6,
            "visual_meshes": len(meshes), "total_mass_kg": mass, "world_plugins": 5, "model_plugins": 2,
            "sensors": sorted(SENSOR_SPECS), "sensor_poses_from_base_link": {name: list(pose) for name, pose in poses.items()},
            "command_topic": CONTROL_TEXT["topic"], "joint_states_topic": "/hz_sim/full/joint_states",
            "gui_render_engine": "ogre", "gui_start_paused": True, "runtime_verified": False,
            "ros_bridge": False, "hardware_driver": False,
            "concerns": ["Mass, collision proxies and mounting transforms retain uncalibrated engineering assumptions.",
                         "This offline gate does not establish runtime sensor, ROS, or GUI behavior."]}


def check_scene(scene_path=None, gui_path=None, manifest_path=None, resource_root=None):
    """Read all inputs locally, validate structure and SHA256s, return a report."""
    root = Path(resource_root).resolve() if resource_root is not None else ROOT
    scene = Path(scene_path) if scene_path is not None else root / SCENE_REL
    gui = Path(gui_path) if gui_path is not None else root / GUI_REL
    manifest = Path(manifest_path) if manifest_path is not None else root / MANIFEST_REL
    try:
        result = validate_scene(read_xml(scene), parse_gui(gui.read_text(encoding="utf-8")), root)
        data = json.loads(manifest.read_text(encoding="utf-8"))
        check_manifest(data, root, scene, gui)
        result["sha256"] = {"scene": sha256(scene), "gui": sha256(gui), "manifest": sha256(manifest),
                            "inputs": {key: value["sha256"] for key, value in data["inputs"].items()}}
        return result
    except (OSError, ET.ParseError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("Full scene check failed: malformed or missing local input: " + str(exc)) from exc


if __name__ == "__main__":
    print(json.dumps(check_scene(), ensure_ascii=False, indent=2))
