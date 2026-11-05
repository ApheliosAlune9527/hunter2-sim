"""Check file/launch refusal paths without starting ROS or Gazebo."""
from copy import deepcopy
from pathlib import Path
import subprocess
import unittest
import xml.etree.ElementTree as ET

from check_control_scene import validate_world


SCENES = Path(__file__).resolve().parent.parent / "scenes"
LAUNCHER = Path(__file__).with_name("start_control_scene.bash")


class ControlSceneChecks(unittest.TestCase):
    def setUp(self):
        self.root = ET.parse(SCENES / "hz_hunter_control.sdf").getroot()

    def controller(self, root):
        return root.find("world/model[@name='hz_hunter_core']/plugin")

    def test_accepts_the_personal_scene(self):
        report = validate_world(self.root)
        self.assertEqual(report["command_topic"], "/hz_sim/cmd_vel")
        self.assertLess(report["maximum_inner_steering_rad"], 0.58)
        self.assertGreater(report["minimum_turning_radius_m"], 1.6)

    def test_gui_requires_compatible_renderer_and_initial_pause(self):
        from check_control_scene import validate_gui
        original = (SCENES / "hz_hunter_preview_gui.config").read_text()
        with self.assertRaises(ValueError):
            validate_gui(original)
        compatible = original.replace("<engine>ogre2</engine>", "<engine>ogre</engine>")
        validate_gui(compatible)
        for invalid in [compatible.replace("<engine>ogre</engine>", ""),
                        compatible.replace("<start_paused>true</start_paused>",
                                           "<start_paused>false</start_paused>")]:
            with self.assertRaises(ValueError):
                validate_gui(invalid)

    def test_rejects_default_or_shared_topics(self):
        for key in ["topic", "odom_topic", "tf_topic"]:
            for value in ["", "/cmd_vel", "/model/hunter/cmd_vel"]:
                with self.subTest(key=key, value=value):
                    root = deepcopy(self.root)
                    self.controller(root).find(key).text = value
                    with self.assertRaises(ValueError):
                        validate_world(root)
            root = deepcopy(self.root)
            self.controller(root).remove(self.controller(root).find(key))
            with self.assertRaises(ValueError):
                validate_world(root)

    def test_rejects_extra_plugins_and_external_models(self):
        for parent_path, tag, attributes in [
            ("world", "plugin", {"filename": "ros_bridge", "name": "bridge"}),
            ("world/model[@name='hz_hunter_core']", "plugin",
             {"filename": "hardware_driver", "name": "driver"}),
            ("world", "include", {}),
        ]:
            root = deepcopy(self.root)
            ET.SubElement(root.find(parent_path), tag, attributes)
            with self.assertRaises(ValueError):
                validate_world(root)

    def test_rejects_wrong_or_duplicate_joint_references(self):
        for key, value in [
            ("left_joint", "front_left_wheel_joint"),
            ("left_steering_joint", "missing_joint"),
        ]:
            root = deepcopy(self.root)
            self.controller(root).find(key).text = value
            with self.assertRaises(ValueError):
                validate_world(root)
        root = deepcopy(self.root)
        ET.SubElement(self.controller(root), "left_joint").text = "rear_left_wheel_joint"
        with self.assertRaises(ValueError):
            validate_world(root)

    def test_rejects_changed_limits_and_geometry(self):
        for key, value in [("max_velocity", "1.5"), ("steering_limit", "0.8"),
                           ("wheel_base", "0.3"), ("kingpin_width", "1.2")]:
            root = deepcopy(self.root)
            self.controller(root).find(key).text = value
            with self.assertRaises(ValueError):
                validate_world(root)
        root = deepcopy(self.root)
        root.find("world/model[@name='hz_hunter_core']/joint[@name='front_left_steering_joint']/axis/limit/upper").text = "0.2"
        with self.assertRaises(ValueError):
            validate_world(root)

    def test_offline_launcher_only_checks_files(self):
        result = subprocess.run(["bash", str(LAUNCHER), "--check"],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("控制场景文件检查通过", result.stdout)

    def test_launcher_rejects_run_flags_and_other_worlds(self):
        for args in [["-r"], ["--run"], ["other.sdf"], ["--check", "-r"]]:
            with self.subTest(args=args):
                result = subprocess.run(["bash", str(LAUNCHER), *args],
                                        capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("不接受额外的仿真启动参数", result.stderr)


if __name__ == "__main__":
    unittest.main()
