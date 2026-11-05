"""Behavior checks use temporary personal workspaces, never robot files."""
import concurrent.futures
import importlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "package"))
try:
    support = importlib.import_module("hz_launch_support")
except ModuleNotFoundError:
    support = None

REFERENCE_CONFIG = PROJECT / "tests/fixtures/config"


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(support, "Personal launch safety component has not been implemented")
        self.temp = tempfile.TemporaryDirectory(prefix="hz_launch_test_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "hz_ws"
        self.root.mkdir()
        self.run = self.root / "maps/lab_20261015_120000_123456"
        (self.run / "pcd").mkdir(parents=True)
        (self.run / "config").mkdir()
        for name in ("mapping.yaml", "camera.yaml", "hesai.yaml", "mapping.rviz", "xt32_firetime.csv"):
            shutil.copyfile(REFERENCE_CONFIG / name, self.run / "config" / name)
        (self.root / "maps/hz_active_session.json").write_text(json.dumps({"run_dir": str(self.run)}))
        self.output = self.root / "src/FAST-LIVO2/Log/PCD"
        self.output.parent.mkdir(parents=True)
        self.output.symlink_to(self.run / "pcd", target_is_directory=True)
        for relative in (
            "install/fast_livo/lib/fast_livo/fastlivo_mapping",
            "install/hesai_ros_driver/lib/hesai_ros_driver/hesai_ros_driver_node",
            "scripts/ch104_imu_pub_legacy.py", "scripts/hz_mapping_session.py", "scripts/pcd_export.py",
        ):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture only\n")
        self.bundle = self.root / "hz_mapping_tools"
        self.bundle.mkdir()
        (self.bundle / "hz_diagnose.py").write_text("# fixture\n")
        self.sensors = {role: {"pid": 100 + i} for i, role in enumerate(("lidar", "imu", "camera"))}

    def spec(self, role="mapping", active=None):
        return support.build_spec(role, self.root, self.bundle, self.sensors if active is None else active)

    def test_current_round_is_read_without_changing_state(self):
        before = (self.root / "maps/hz_active_session.json").read_bytes()
        self.assertEqual(support.active_run(self.root), self.run)
        self.assertEqual(before, (self.root / "maps/hz_active_session.json").read_bytes())

    def test_state_cannot_point_outside_personal_maps(self):
        outside = self.root.parent / "senior_ws/lab_20261015_120000_123456"
        outside.mkdir(parents=True)
        (self.root / "maps/hz_active_session.json").write_text(json.dumps({"run_dir": str(outside)}))
        with self.assertRaisesRegex(support.SafetyError, "目录|路径"):
            self.spec()

    def test_state_symlink_cannot_escape_personal_maps(self):
        state = self.root / "maps/hz_active_session.json"
        outside = self.root.parent / "senior_state.json"
        state.rename(outside)
        state.symlink_to(outside)
        with self.assertRaises(support.SafetyError):
            support.active_run(self.root)

    def test_output_link_must_match_current_round(self):
        self.output.unlink()
        other = self.root / "maps/lab_20261011_141011_768151/pcd"
        other.mkdir(parents=True)
        self.output.symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(support.SafetyError, "PCD|链接"):
            self.spec()

    def test_mapping_refuses_old_clouds_without_touching_them(self):
        old = self.run / "pcd/1.pcd"
        old.write_bytes(b"preserve exactly")
        with self.assertRaisesRegex(support.SafetyError, "PCD|点云"):
            self.spec()
        self.assertEqual(old.read_bytes(), b"preserve exactly")

    def test_mapping_refuses_existing_log_even_if_empty(self):
        (self.run / "mapping.log").touch()
        with self.assertRaisesRegex(support.SafetyError, "mapping.log|日志"):
            self.spec()

    def test_mapping_refuses_duplicate_process(self):
        with self.assertRaisesRegex(support.SafetyError, "已运行|重复"):
            self.spec(active=dict(self.sensors, mapping={"pid": 999}))

    def test_camera_refuses_orphan_child(self):
        with self.assertRaisesRegex(support.SafetyError, "已运行|重复"):
            self.spec("camera", {"camera_child": {"pid": 111}})

    def test_mapping_requires_all_three_sensor_processes(self):
        with self.assertRaisesRegex(support.SafetyError, "传感器|camera"):
            self.spec(active={"lidar": {}, "imu": {}})

    def test_mapping_refuses_disabled_saving(self):
        path = self.run / "config/mapping.yaml"
        path.write_text(path.read_text(encoding="utf-8").replace("pcd_save_en: true", "pcd_save_en: false"), encoding="utf-8")
        with self.assertRaisesRegex(support.SafetyError, "pcd_save_en"):
            self.spec()

    def test_mapping_refuses_negative_interval(self):
        path = self.run / "config/mapping.yaml"
        path.write_text(path.read_text(encoding="utf-8").replace("interval: 1", "interval: -1"), encoding="utf-8")
        with self.assertRaisesRegex(support.SafetyError, "interval"):
            self.spec()

    def test_mapping_refuses_topic_mismatch(self):
        path = self.run / "config/mapping.yaml"
        path.write_text(path.read_text(encoding="utf-8").replace("/imu/data", "/other/imu"), encoding="utf-8")
        with self.assertRaisesRegex(support.SafetyError, "话题|imu_topic"):
            self.spec()

    def test_mapping_uses_personal_binary_and_round_params_without_edits(self):
        before = {p.name: p.read_bytes() for p in (self.run / "config").iterdir()}
        spec = self.spec()
        self.assertEqual(spec.cmd[0], str(self.root / "install/fast_livo/lib/fast_livo/fastlivo_mapping"))
        self.assertIn(str(self.run / "config/mapping.yaml"), spec.cmd)
        self.assertIn(str(self.run / "config/camera.yaml"), spec.cmd)
        self.assertIn("__node:=laserMapping", spec.cmd)
        self.assertTrue(spec.exclusive_log)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.run / "config").iterdir()})

    def test_driver_arguments_keep_existing_process_recognition(self):
        self.assertEqual(self.spec("lidar", {}).cmd[0], str(self.root / "install/hesai_ros_driver/lib/hesai_ros_driver/hesai_ros_driver_node"))
        imu = self.spec("imu", {}).cmd
        self.assertEqual(imu[:3], ["python3", "-u", "-B"])
        self.assertIn("port:=/dev/ch104", imu)
        camera = self.spec("camera", {}).cmd
        self.assertEqual(camera[:4], ["ros2", "launch", "realsense2_camera", "rs_launch.py"])
        self.assertIn("rgb_camera.color_profile:=640x480x15", camera)
        self.assertIn("enable_depth:=false", camera)

    def test_existing_stop_tool_recognizes_all_launched_node_commands(self):
        scripts = PROJECT / "tests/fixtures/tools"
        sys.path.insert(0, str(scripts))
        spec = importlib.util.spec_from_file_location("hz_reference_helper", scripts / "hz_mapping_session.py")
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        for role in ("lidar", "imu", "camera", "mapping", "rviz"):
            command = [s.replace(str(self.root), "/home/car/hz_ws").replace("\\", "/") for s in self.spec(role, {}).cmd] if role != "mapping" else [s.replace(str(self.root), "/home/car/hz_ws").replace("\\", "/") for s in self.spec(role).cmd]
            env = {"ROS_DOMAIN_ID": "88", "ROS_HOME": "/home/car/hz_ws/.ros"}
            self.assertEqual(helper.classify_process(command, env, 1000, 1000), role)

    def test_launch_file_exists_as_native_ros_entry(self):
        self.assertTrue((PROJECT / "package/hz_mapping.launch.py").is_file(), "Native ROS 2 launch entry has not been implemented")

    def test_prepare_refuses_live_personal_processes(self):
        with self.assertRaisesRegex(support.SafetyError, "运行|停止"):
            self.spec("prepare")

    def test_management_uses_original_helpers(self):
        for role in ("status", "stop", "check", "pack", "watch", "prepare"):
            spec = self.spec(role, {})
            self.assertEqual(spec.cmd, ["python3", "-u", "-B", str(self.root / "scripts/hz_mapping_session.py"), role])

    def test_merge_refuses_active_mapping(self):
        with self.assertRaisesRegex(support.SafetyError, "停止|运行"):
            self.spec("merge", {"mapping": {"pid": 100}})

    def test_merge_does_not_realign_or_overwrite_existing_map(self):
        spec = self.spec("merge", {})
        self.assertEqual(spec.cmd[-3:], ["merge", str(self.run / "pcd"), str(self.run / "merged")])
        (self.run / "merged").mkdir()
        (self.run / "merged/map_raw.pcd").write_bytes(b"keep map")
        with self.assertRaisesRegex(support.SafetyError, "存在|覆盖"):
            self.spec("merge", {})
        self.assertEqual((self.run / "merged/map_raw.pcd").read_bytes(), b"keep map")

    def test_unknown_role_is_rejected(self):
        with self.assertRaises(support.SafetyError):
            self.spec("navigation", {})

    def test_exclusive_log_allows_exactly_one_starter(self):
        path = self.run / "mapping.log"
        def attempt(_):
            try:
                writer = support.LogCapture(path, exclusive=True)
                writer.write(b"one start\n")
                writer.close()
                return True
            except (FileExistsError, support.SafetyError):
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            self.assertEqual(sum(pool.map(attempt, range(6))), 1)
        self.assertEqual(path.read_bytes(), b"one start\n")

    def test_log_appends_stdout_and_stderr_bytes_immediately(self):
        path = self.run / "lidar.log"
        path.write_bytes(b"old\n")
        writer = support.LogCapture(path, exclusive=False)
        self.addCleanup(writer.close)
        writer.write("新日志\n".encode("utf-8"))
        writer.write(b"stderr\n")
        self.assertEqual(path.read_bytes(), b"old\n" + "新日志\n".encode("utf-8") + b"stderr\n")
        writer.close()
        writer.close()

    def test_log_symlink_cannot_modify_an_existing_file(self):
        outside = self.root.parent / "senior.log"
        outside.write_bytes(b"do not touch")
        path = self.run / "imu.log"
        path.symlink_to(outside)
        with self.assertRaises(support.SafetyError):
            support.LogCapture(path, exclusive=False)
        self.assertEqual(outside.read_bytes(), b"do not touch")


if __name__ == "__main__":
    unittest.main()
