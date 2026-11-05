"""Deterministically assemble the reviewed Fortress full-model scene offline.

The conversion is an input, never executed here. No ROS, WSL, Gazebo process,
network access or motion command is used. The original 19-link URDF is untouched.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from check_hunter_full_scene import (
    ROOT, NAME, PACKAGE, URI_PREFIX, SCENE_REL, GUI_REL, MANIFEST_REL, INPUT_PATHS,
    MESH_PATHS, WORLD_PLUGINS, MODEL_PLUGINS, CONTROL_TEXT, CONTROL_NUMBERS, JOINTS,
    GUI_PLUGINS, SENSOR_SPECS, check_scene, local_file, parse_gui, plugin_identity,
    read_xml, require, sensor_poses, sha256, CAMERA_FOV, CAMERA_MODEL,
)


def element(parent, tag, text=None, **attributes):
    node = ET.SubElement(parent, tag, attributes)
    if text is not None:
        node.text = str(text)
    return node


def vector(values):
    return " ".join(format(value, ".16g") for value in values)


def material(parent, color):
    node = element(parent, "material")
    element(node, "ambient", vector(color))
    element(node, "diffuse", vector(color))


def add_environment(world):
    scene = element(world, "scene")
    element(scene, "ambient", "0.5 0.5 0.5 1")
    element(scene, "background", "0.75 0.83 0.89 1")
    element(scene, "shadows", "true")
    sun = element(world, "light", name="sun", type="directional")
    element(sun, "pose", "0 0 10 0 0 0")
    element(sun, "cast_shadows", "true")
    element(sun, "diffuse", "0.85 0.85 0.85 1")
    element(sun, "specular", "0.2 0.2 0.2 1")
    attenuation = element(sun, "attenuation")
    for key, value in {"range": 1000, "constant": 0.9, "linear": 0.01, "quadratic": 0.001}.items():
        element(attenuation, key, value)
    element(sun, "direction", "-0.5 -0.3 -1")
    ground = element(world, "model", name="ground_plane")
    element(ground, "static", "true")
    link = element(ground, "link", name="ground")
    for tag in ("collision", "visual"):
        node = element(link, tag, name="ground_" + tag)
        plane = element(element(node, "geometry"), "plane")
        element(plane, "normal", "0 0 1")
        element(plane, "size", "20 20")
        if tag == "visual":
            material(node, (0.55, 0.58, 0.60, 1))
    # Targets are static, well away from the initial vehicle and visible to both
    # the forward RGB-D camera and the 360-degree lidar. No lab map is loaded.
    for name, pose, size, color in (
        ("target_red", (4, 0, 0.65, 0, 0, 0), (0.4, 1.2, 1.3), (0.9, 0.12, 0.10, 1)),
        ("target_green", (3.5, 2, 0.5, 0, 0, 0), (0.6, 0.6, 1), (0.12, 0.8, 0.2, 1)),
        ("target_blue", (-3, -2, 0.75, 0, 0, 0), (0.5, 0.5, 1.5), (0.12, 0.3, 0.95, 1)),
    ):
        target = element(world, "model", name=name)
        element(target, "static", "true")
        element(target, "pose", vector(pose))
        link = element(target, "link", name="body")
        for tag in ("collision", "visual"):
            node = element(link, tag, name=name + "_" + tag)
            element(element(element(node, "geometry"), "box"), "size", vector(size))
            if tag == "visual":
                material(node, color)


def add_sensors(model, poses):
    base = model.find("link[@name='base_link']")
    for name, (sensor_type, _, frame, rate) in SENSOR_SPECS.items():
        sensor = element(base, "sensor", name=name, type=sensor_type)
        element(sensor, "pose", vector(poses[name]))
        element(sensor, "always_on", "true")
        element(sensor, "update_rate", rate)
        element(sensor, "visualize", "false")
        element(sensor, "topic", "/hz_sim/full/" + name)
        # Fortress sensors 6.9 supports this tag. The camera engine uses the
        # carrier's +X pose while its message frame names the URDF optical frame.
        element(sensor, "ignition_frame_id", frame)
        if name == "lidar":
            lidar = element(sensor, "lidar")
            scan = element(lidar, "scan")
            for axis, samples, lower, upper in (
                ("horizontal", 720, -math.pi, math.pi),
                ("vertical", 32, math.radians(-16), math.radians(15)),
            ):
                sweep = element(scan, axis)
                for key, value in {"samples": samples, "resolution": 1, "min_angle": lower, "max_angle": upper}.items():
                    element(sweep, key, format(value, ".16g"))
            distance = element(lidar, "range")
            for key, value in {"min": 0.1, "max": 20, "resolution": 0.01}.items():
                element(distance, key, value)
        elif name == "camera":
            camera = element(sensor, "camera")
            element(camera, "horizontal_fov", format(CAMERA_FOV, ".16g"))
            image = element(camera, "image")
            element(image, "width", 640)
            element(image, "height", 480)
            element(image, "format", "R8G8B8")
            clip = element(camera, "clip")
            element(clip, "near", "0.1")
            element(clip, "far", 20)
        else:
            element(sensor, "imu")


def scene_tree(root):
    converted = read_xml(local_file(root, INPUT_PATHS["converted_sdf"]))
    require(converted.tag == "sdf" and len(converted.findall("model")) == 1, "conversion input needs one model")
    model = copy.deepcopy(converted.find("model"))
    require(model.get("name") == NAME, "conversion input model identity mismatch")
    for uri in model.findall(".//mesh/uri"):
        prefix = "model://hz_hunter_full_description/"
        require((uri.text or "").startswith(prefix), "conversion input has external mesh URI")
        relative = uri.text.removeprefix(prefix)
        require(relative in MESH_PATHS, "conversion input mesh is not allowlisted")
        uri.text = URI_PREFIX + relative
    model.insert(0, ET.Element("pose"))
    model[0].text = "0 0 0.167 0 0 0"
    model.insert(1, ET.Element("static"))
    model[1].text = "false"
    report = json.loads(local_file(root, INPUT_PATHS["geometry_report"]).read_text(encoding="utf-8"))
    poses = sensor_poses(root, report)
    add_sensors(model, poses)
    controller = element(model, "plugin", **plugin_identity("AckermannSteering", MODEL_PLUGINS["AckermannSteering"]))
    for key, value in {**CONTROL_TEXT, **CONTROL_NUMBERS}.items():
        element(controller, key, value)
    publisher = element(model, "plugin", **plugin_identity("JointStatePublisher", MODEL_PLUGINS["JointStatePublisher"]))
    element(publisher, "topic", "/hz_sim/full/joint_states")
    for name in sorted(JOINTS):
        element(publisher, "joint_name", name)
    sdf = ET.Element("sdf", version="1.9")
    world = element(sdf, "world", name=NAME)
    physics = element(world, "physics", name="hz_full_physics", type="ignored")
    element(physics, "max_step_size", "0.001")
    element(physics, "real_time_factor", "1.0")
    element(world, "gravity", "0 0 -9.81")
    for short, slug in WORLD_PLUGINS.items():
        plugin = element(world, "plugin", **plugin_identity(short, slug))
        if short == "Sensors":
            element(plugin, "render_engine", "ogre")
    add_environment(world)
    world.append(model)
    ET.indent(sdf, space="  ")
    return ET.ElementTree(sdf)


def gui_text(root):
    source = root / "sim/scenes/hz_hunter_control_gui.config"
    gui = parse_gui(source.read_text(encoding="utf-8"))
    for plugin in gui.findall("plugin"):
        if plugin.get("filename") not in GUI_PLUGINS:
            gui.remove(plugin)
    gui.find("plugin[@filename='MinimalScene']/camera_pose").text = "1.35 -1.3 1.05 0 0.347 2.238"
    gui.find("plugin[@filename='MinimalScene']/engine").text = "ogre"
    gui.find("plugin[@filename='WorldControl']/start_paused").text = "true"
    ET.indent(gui, space="  ")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + "\n".join(ET.tostring(child, encoding="unicode").rstrip() for child in gui) + "\n"


def build_scene(scene_path=None, gui_path=None, manifest_path=None, resource_root=None):
    """Write scene, GUI and provenance manifest; verify them before returning."""
    root = Path(resource_root).resolve() if resource_root is not None else ROOT
    scene = Path(scene_path) if scene_path is not None else root / SCENE_REL
    gui = Path(gui_path) if gui_path is not None else root / GUI_REL
    manifest = Path(manifest_path) if manifest_path is not None else root / MANIFEST_REL
    for path in (scene, gui, manifest):
        path.parent.mkdir(parents=True, exist_ok=True)
    scene_tree(root).write(scene, encoding="utf-8", xml_declaration=True)
    gui.write_text(gui_text(root), encoding="utf-8", newline="\n")
    source = json.loads(local_file(root, INPUT_PATHS["source_manifest"]).read_text(encoding="utf-8"))
    mesh_hashes = {entry["path"]: entry["sha256"] for entry in source["outputs"]}
    data = {
        "schema_version": 1, "model_name": NAME,
        "camera_model": CAMERA_MODEL,
        "artifacts": {"scene": {"path": SCENE_REL, "sha256": sha256(scene)},
                      "gui": {"path": GUI_REL, "sha256": sha256(gui)}},
        "inputs": {key: {"path": relative, "sha256": sha256(local_file(root, relative))} for key, relative in INPUT_PATHS.items()},
        "meshes": [{"path": relative, "uri": URI_PREFIX + relative, "sha256": mesh_hashes[relative]} for relative in MESH_PATHS],
        "conversion": {"method": "Fortress ign sdf -p on a copy with preserveFixedJoint tags removed",
                       "original_urdf_unchanged": True, "rsp_links": 19, "physical_links": 7, "active_joints": 6},
        "render_engine": "ogre", "gui_start_paused": True,
        "transport_topics": {"command": "/hz_sim/full/cmd_vel", "odom": "/hz_sim/full/odom", "tf": "/hz_sim/full/tf",
                             "joint_states": "/hz_sim/full/joint_states", "lidar_scan": "/hz_sim/full/lidar",
                             "lidar_points": "/hz_sim/full/lidar/points", "camera_rgb": "/hz_sim/full/camera/image",
                             "camera_depth": "/hz_sim/full/camera/depth_image", "camera_info": "/hz_sim/full/camera/camera_info",
                             "imu": "/hz_sim/full/imu"},
        "sensor_pose_source": "geometry_report.sensor_carriers, checked against original URDF chain",
        "uncalibrated": True,
        "limitations": ["Masses, inertia/collision approximations and IMU mounting are engineering assumptions.",
                        "RGB uses source horizontal focal length with centered square pixels; RGBD depth shares that approximation.",
                        "Offline generation and validation do not claim runtime sensor, ROS or GUI acceptance."],
    }
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return check_scene(scene, gui, manifest, root)


if __name__ == "__main__":
    print(json.dumps(build_scene(), ensure_ascii=False, indent=2))
