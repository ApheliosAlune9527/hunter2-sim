"""Windows/offline acceptance and mutation tests; never starts a simulator."""
from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / "sim/scenes/hz_hunter_full.sdf"
GUI = ROOT / "sim/scenes/hz_hunter_full_gui.config"
MANIFEST = ROOT / "sim/scenes/hz_hunter_full_manifest.json"
PREFIX = "file:///mnt/f/rob-memory/sim/hz_hunter_full_description/"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HunterFullSceneTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("build_hunter_full_scene"),
                             "Offline full-scene builder is not implemented")
        self.assertIsNotNone(importlib.util.find_spec("check_hunter_full_scene"),
                             "Strict full-scene validator is not implemented")
        self.builder = importlib.import_module("build_hunter_full_scene")
        self.checker = importlib.import_module("check_hunter_full_scene")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        directory = Path(self.tmp.name)
        self.scene = directory / SCENE.name
        self.gui = directory / GUI.name
        self.manifest = directory / MANIFEST.name
        self.builder.build_scene(self.scene, self.gui, self.manifest, ROOT)
        self.tree = ET.parse(self.scene)
        self.world = self.tree.getroot().find("world")
        self.model = self.world.find("model[@name='hz_hunter_full']")

    def check(self):
        return self.checker.check_scene(self.scene, self.gui, self.manifest, ROOT)

    def save_mutated_scene(self):
        self.tree.write(self.scene, encoding="utf-8", xml_declaration=True)
        self.rehash_artifact("scene", self.scene)

    def rehash_artifact(self, key, path):
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        data["artifacts"][key]["sha256"] = sha(path)
        self.manifest.write_text(json.dumps(data), encoding="utf-8")

    def reject_scene(self, mutate, message):
        original = copy.deepcopy(self.tree.getroot())
        mutate()
        self.save_mutated_scene()
        with self.assertRaisesRegex(ValueError, message):
            self.check()
        self.tree = ET.ElementTree(original)
        self.world = original.find("world")
        self.model = self.world.find("model[@name='hz_hunter_full']")
        self.save_mutated_scene()

    def test_generator_and_validator_produce_a_complete_offline_scene(self):
        report = self.check()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["world"], "hz_hunter_full")
        self.assertEqual(report["physical_links"], 7)
        self.assertEqual(report["active_joints"], 6)
        self.assertEqual(report["visual_meshes"], 12)
        self.assertEqual(report["world_plugins"], 5)
        self.assertEqual(report["model_plugins"], 2)
        self.assertEqual(report["sensors"], ["camera", "imu", "lidar"])
        self.assertEqual(report["gui_render_engine"], "ogre")
        self.assertTrue(report["gui_start_paused"])
        self.assertFalse(report["runtime_verified"])
        gui = self.checker.parse_gui(self.gui.read_text(encoding="utf-8"))
        self.assertEqual(gui.findtext("plugin[@filename='MinimalScene']/camera_pose"),
                         "1.35 -1.3 1.05 0 0.347 2.238")

    def test_camera_view_uses_verified_car_rgb_focal_length(self):
        camera = self.model.find("link[@name='base_link']/sensor[@name='camera']/camera")
        fov = float(camera.findtext("horizontal_fov"))
        simulated_fx = 640 / (2 * math.tan(fov / 2))
        self.assertAlmostEqual(simulated_fx, 606.7595825195312, places=6)
        # This Ogre1 RGBD implementation renders centered square pixels. The
        # info must describe that image rather than claim an off-center model.
        self.assertIsNone(camera.find("lens"))
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        source = data["inputs"]["camera_source"]
        self.assertEqual(source["sha256"], "790333f3aa749400429f27d0fa0838662dc8c65e5ad6e64b96dfa9de8d183daf")

    def test_generated_scene_retains_converted_physical_inertias_and_meshes(self):
        source = ET.parse(ROOT / "outputs/hunter_model_upgrade_20261030/references/ament/hunter_full.converted.sdf").getroot().find("model")
        for link in source.findall("link"):
            actual = self.model.find(f"link[@name='{link.get('name')}']")
            signature = lambda node: [(part.tag, part.attrib, (part.text or "").strip()) for part in node.iter()]
            self.assertEqual(signature(actual.find("inertial")), signature(link.find("inertial")))
        uris = [node.text for node in self.model.findall(".//visual/geometry/mesh/uri")]
        self.assertEqual(len(set(uris)), 12)
        self.assertTrue(all(uri.startswith(PREFIX) for uri in uris))
        self.assertFalse(any("hunter_2_0" in uri.lower() for uri in uris))
        self.assertEqual(self.model.findtext("pose"), "0 0 0.167 0 0 0")
        self.assertEqual(self.model.findtext("static"), "false")

    def test_manifest_records_every_input_and_mesh_hash(self):
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(data["artifacts"]["scene"]["sha256"], sha(self.scene))
        self.assertEqual(data["artifacts"]["gui"]["sha256"], sha(self.gui))
        self.assertEqual(set(data["inputs"]), {"converted_sdf", "conversion_urdf", "urdf", "source_manifest", "geometry_report", "camera_source"})
        for entry in data["inputs"].values():
            self.assertEqual(entry["sha256"], sha(ROOT / entry["path"]))
        self.assertEqual(len(data["meshes"]), 12)
        for entry in data["meshes"]:
            self.assertEqual(entry["uri"], PREFIX + entry["path"])
            self.assertEqual(entry["sha256"], sha(ROOT / "sim/hz_hunter_full_description" / entry["path"]))

    def test_generation_is_byte_for_byte_deterministic(self):
        before = [path.read_bytes() for path in (self.scene, self.gui, self.manifest)]
        self.builder.build_scene(self.scene, self.gui, self.manifest, ROOT)
        self.assertEqual(before, [path.read_bytes() for path in (self.scene, self.gui, self.manifest)])

    def test_checked_in_artifacts_are_current_and_valid(self):
        self.assertEqual(self.checker.check_scene(resource_root=ROOT)["status"], "PASS")
        self.assertEqual(self.scene.read_bytes(), SCENE.read_bytes())
        self.assertEqual(self.gui.read_bytes(), GUI.read_bytes())
        self.assertEqual(self.manifest.read_bytes(), MANIFEST.read_bytes())

    def test_rejects_plugin_injection_duplicates_and_unexpected_scopes(self):
        for scope in ("world", "vehicle", "link", "static"):
            with self.subTest(scope=scope):
                def mutate():
                    parent = {"world": self.world, "vehicle": self.model,
                              "link": self.model.find("link"),
                              "static": self.world.find("model[@name='ground_plane']")}[scope]
                    ET.SubElement(parent, "plugin", filename="libarbitrary.so", name="Injected")
                self.reject_scene(mutate, "plugin")
        self.reject_scene(lambda: self.world.append(copy.deepcopy(self.world.find("plugin"))), "plugin")

    def test_rejects_default_or_cross_scene_control_topics(self):
        for bad in ("/cmd_vel", "/hz_sim/cmd_vel", "/hz_sim/full/cmd_vel/extra"):
            with self.subTest(topic=bad):
                self.reject_scene(lambda: setattr(self.model.find("plugin/topic"), "text", bad), "topic")

    def test_rejects_missing_duplicate_or_extra_controller_parameters(self):
        def duplicate():
            controller = self.model.find("plugin")
            controller.append(copy.deepcopy(controller.find("topic")))
        self.reject_scene(duplicate, "parameter")
        self.reject_scene(lambda: ET.SubElement(self.model.find("plugin"), "max_jerk"), "parameter")
        self.reject_scene(lambda: self.model.find("plugin").remove(self.model.find("plugin/left_joint")), "parameter")

    def test_rejects_arbitrary_mesh_uris_even_with_rehashed_manifest(self):
        for bad in ("https://evil.invalid/robot.stl", "file:///etc/passwd", "model://other/robot.stl",
                    PREFIX + "../urdf/hunter_full.urdf", PREFIX + "meshes/chassis/not_in_manifest.stl"):
            with self.subTest(uri=bad):
                self.reject_scene(lambda: setattr(self.model.find(".//mesh/uri"), "text", bad), "mesh|resource")

    def test_rejects_includes_and_non_mesh_resource_references(self):
        self.reject_scene(lambda: ET.SubElement(ET.SubElement(self.world, "include"), "uri"), "include")
        self.reject_scene(lambda: ET.SubElement(self.world.find("scene"), "uri"), "resource|uri")

    def test_rejects_unexpected_world_and_gui_elements_with_hidden_resources(self):
        def actor():
            ET.SubElement(ET.SubElement(ET.SubElement(self.world, "actor", name="hidden"), "skin"), "filename").text = "https://evil.invalid/actor.dae"
        self.reject_scene(actor, "world|resource|parameter")
        self.reject_scene(lambda: ET.SubElement(self.world.find("scene"), "cubemap_uri"), "scene|resource|parameter")
        gui = self.gui.read_text(encoding="utf-8")
        gui += '<script><filename>/tmp/unreviewed.qml</filename></script>'
        self.gui.write_text(gui, encoding="utf-8")
        self.rehash_artifact("gui", self.gui)
        with self.assertRaisesRegex(ValueError, "GUI|parameter|resource"):
            self.check()

    def test_rejects_static_environment_and_mesh_scale_mutations(self):
        self.reject_scene(lambda: setattr(self.world.find("model[@name='target_red']/pose"), "text", "0 0 0 0 0 0"), "target|environment|pose")
        self.reject_scene(lambda: setattr(self.model.find(".//mesh/scale"), "text", "1000 1000 1000"), "mesh scale")

    def test_conversion_input_is_only_the_original_urdf_without_preserve_tags(self):
        self.assertTrue(hasattr(self.checker, "check_conversion_inputs"), "Conversion provenance relationship is not checked")
        original = ET.parse(ROOT / "sim/hz_hunter_full_description/urdf/hunter_full.urdf").getroot()
        converted = ET.parse(ROOT / "outputs/hunter_model_upgrade_20261030/references/ament/hunter_full_lump_input.urdf").getroot()
        self.checker.check_conversion_inputs(original, converted)
        converted.find("link/inertial/mass").set("value", "999")
        with self.assertRaisesRegex(ValueError, "conversion|URDF"):
            self.checker.check_conversion_inputs(original, converted)

    def test_rejects_missing_sensors_and_wrong_sensor_frame(self):
        def missing():
            base = self.model.find("link[@name='base_link']")
            base.remove(base.find("sensor[@name='lidar']"))
        self.reject_scene(missing, "sensor")
        self.reject_scene(lambda: setattr(self.model.find(".//sensor[@name='camera']/ignition_frame_id"), "text", "camera_link"), "frame")

    def test_rejects_sensor_type_pose_rate_range_and_scan_mutations(self):
        mutations = ((".//sensor[@name='lidar']", "type", "ray"),
                     (".//sensor[@name='camera']/pose", None, "0 0 0 0 0 0"),
                     (".//sensor[@name='imu']/update_rate", None, "500"),
                     (".//sensor[@name='lidar']/lidar/scan/horizontal/samples", None, "360"),
                     (".//sensor[@name='lidar']/lidar/range/max", None, "100"),
                     (".//sensor[@name='camera']/camera/image/width", None, "1280"))
        for path, attribute, bad in mutations:
            with self.subTest(path=path):
                def mutate():
                    node = self.model.find(path)
                    node.set(attribute, bad) if attribute else setattr(node, "text", bad)
                self.reject_scene(mutate, "sensor|lidar|camera|imu")

    def test_rejects_zero_nonfinite_and_non_positive_definite_inertias(self):
        for path, bad in (("mass", "0"), ("mass", "nan"), ("inertia/ixx", "0"),
                          ("inertia/iyy", "inf"), ("inertia/ixy", "10000")):
            with self.subTest(path=path, bad=bad):
                self.reject_scene(lambda: setattr(self.model.find("link/inertial/" + path), "text", bad), "inertia|mass|finite")

    def test_rejects_mesh_collisions_and_zero_or_negative_primitive_sizes(self):
        def mesh_collision():
            geometry = self.model.find("link/collision/geometry")
            geometry.clear()
            ET.SubElement(ET.SubElement(geometry, "mesh"), "uri").text = PREFIX + "meshes/chassis/base_link.stl"
        self.reject_scene(mesh_collision, "collision|primitive")
        self.reject_scene(lambda: setattr(self.model.find("link/collision/geometry/box/size"), "text", "1 0 -1"), "collision|primitive|size")

    def test_rejects_joint_axis_parent_limits_and_disconnected_topology(self):
        for path, bad in (("axis/xyz", "1 0 0"), ("parent", "unknown_link"),
                          ("child", "base_link"), ("axis/limit/lower", "0"),
                          ("axis/limit/velocity", "nan"), ("pose", "0 0 0 0 0 0")):
            with self.subTest(path=path):
                self.reject_scene(lambda: setattr(self.model.find("joint/" + path), "text", bad), "joint|finite")

    def test_rejects_joint_state_publisher_with_incomplete_joint_names(self):
        def mutate():
            plugin = self.model.find("plugin[@name='ignition::gazebo::systems::JointStatePublisher']")
            plugin.remove(plugin.find("joint_name"))
        self.reject_scene(mutate, "joint|parameter")

    def test_rejects_non_ogre_sensors_engine(self):
        self.reject_scene(lambda: setattr(self.world.find("plugin[@name='ignition::gazebo::systems::Sensors']/render_engine"), "text", "ogre2"), "engine|plugin")

    def test_rejects_wrong_identity_pose_static_or_extra_model(self):
        self.reject_scene(lambda: self.world.set("name", "default"), "world|identity")
        self.reject_scene(lambda: setattr(self.model.find("pose"), "text", "0 0 1 0 0 0"), "pose")
        self.reject_scene(lambda: setattr(self.model.find("static"), "text", "true"), "static")
        self.reject_scene(lambda: ET.SubElement(self.world, "model", name="extra"), "model")

    def test_rejects_model_pose_reference_that_changes_world_placement(self):
        self.reject_scene(lambda: self.model.find("pose").set("relative_to", "target_red"), "pose|reference")

    def test_resource_root_maps_only_the_reviewed_local_files_and_checks_bytes(self):
        mirror = Path(self.tmp.name) / "resources"
        for relative in (*self.checker.INPUT_PATHS.values(),
                         *(self.checker.PACKAGE + "/" + mesh for mesh in self.checker.MESH_PATHS)):
            destination = mirror / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        self.assertEqual(self.checker.check_scene(self.scene, self.gui, self.manifest, mirror)["status"], "PASS")
        mesh = mirror / self.checker.PACKAGE / "meshes/chassis/base_link.stl"
        mesh.write_bytes(b"CORRUPTED" + mesh.read_bytes()[9:])
        with self.assertRaisesRegex(ValueError, "SHA|hash"):
            self.checker.check_scene(self.scene, self.gui, self.manifest, mirror)

    def test_rejects_gui_running_wrong_engine_or_plugin_injection(self):
        original = self.gui.read_text(encoding="utf-8")
        mutations = (original.replace("<start_paused>true</start_paused>", "<start_paused>false</start_paused>"),
                     original.replace("<engine>ogre</engine>", "<engine>ogre2</engine>"),
                     original + '<plugin filename="Injected" name="Injected"/>',
                     original + '<include><uri>https://evil.invalid/gui</uri></include>')
        for text in mutations:
            with self.subTest(gui=text[-120:]):
                self.gui.write_text(text, encoding="utf-8")
                self.rehash_artifact("gui", self.gui)
                with self.assertRaisesRegex(ValueError, "GUI|include|plugin"):
                    self.check()
        self.gui.write_text(original, encoding="utf-8")

    def test_rejects_stale_artifact_or_tampered_mesh_manifest_hashes(self):
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        original = copy.deepcopy(data)
        for key in ("artifact", "mesh", "source"):
            with self.subTest(key=key):
                data = copy.deepcopy(original)
                if key == "artifact":
                    data["artifacts"]["scene"]["sha256"] = "0" * 64
                elif key == "mesh":
                    data["meshes"][0]["sha256"] = "0" * 64
                else:
                    data["inputs"]["urdf"]["sha256"] = "0" * 64
                self.manifest.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "SHA|hash"):
                    self.check()


if __name__ == "__main__":
    unittest.main(verbosity=2)
