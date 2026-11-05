import importlib
import importlib.util
import json
import struct
import tarfile
import tempfile
import unittest
from pathlib import Path


def fixture(path, points, fields="x y z rgb"):
    payload = b"".join(struct.pack("<fffI", *p) for p in points)
    header = (
        "# .PCD v0.7\nVERSION 0.7\nFIELDS " + fields + "\n"
        "SIZE 4 4 4 4\nTYPE F F F U\nCOUNT 1 1 1 1\n"
        f"WIDTH {len(points)}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\n"
        f"POINTS {len(points)}\nDATA binary\n"
    ).encode("ascii")
    path.write_bytes(header + payload)
    return payload


class PcdTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("pcd_export"), "PCD 工具尚未实现")
        self.mod = importlib.import_module("pcd_export")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_binary_size_is_checked(self):
        p = self.root / "1.pcd"
        fixture(p, [(1, 2, 3, 0xAABBCC)])
        self.assertEqual(self.mod.pcd_info(p)["points"], 1)
        p.write_bytes(p.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, "字节|length|size"):
            self.mod.pcd_info(p)

    def test_numeric_order_and_rgb_preserved_in_merge(self):
        src = self.root / "pcd"
        src.mkdir()
        a = fixture(src / "2.pcd", [(0.01, 0, 0, 0x123456), (0.02, 0, 0, 0xABCDEF)])
        b = fixture(src / "10.pcd", [(0.30, 0, 0, 0xDEADBE)])
        out = self.root / "merged"
        result = self.mod.merge_pcd(src, out, 0.15)
        info = self.mod.pcd_info(out / "map_raw.pcd")
        self.assertEqual(info["points"], 3)
        with (out / "map_raw.pcd").open("rb") as f:
            f.seek(info["offset"])
            self.assertEqual(f.read(), a + b)
        self.assertEqual(result["preview_points"], 2)

    def test_mixed_layout_does_not_create_output(self):
        src = self.root / "pcd"
        src.mkdir()
        fixture(src / "1.pcd", [(0, 0, 0, 1)])
        fixture(src / "2.pcd", [(1, 0, 0, 2)], fields="x y z intensity")
        with self.assertRaises(ValueError):
            self.mod.merge_pcd(src, self.root / "out", 0.15)
        self.assertFalse((self.root / "out" / "map_raw.pcd").exists())

    def test_existing_result_is_not_overwritten(self):
        src = self.root / "pcd"
        src.mkdir()
        fixture(src / "1.pcd", [(0, 0, 0, 1)])
        out = self.root / "out"
        out.mkdir()
        (out / "map_raw.pcd").write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            self.mod.merge_pcd(src, out, 0.15)
        self.assertEqual((out / "map_raw.pcd").read_bytes(), b"keep")

    def test_empty_run_is_rejected(self):
        with self.assertRaises(ValueError):
            self.mod.validate_pcd_dir(self.root)

    def test_unpack_rejects_traversal(self):
        archive = self.root / "evil.tar.gz"
        with tarfile.open(archive, "w:gz") as t:
            item = tarfile.TarInfo("../escape")
            item.size = 0
            t.addfile(item)
        with self.assertRaises(ValueError):
            self.mod.unpack_map(archive, self.root / "dest")
        self.assertFalse((self.root / "escape").exists())

    def test_unpack_validates_real_round_trip(self):
        run = self.root / "lab_20261011_140000"
        (run / "pcd").mkdir(parents=True)
        fixture(run / "pcd" / "1.pcd", [(1, 2, 3, 42)])
        archive = self.root / (run.name + ".tar.gz")
        with tarfile.open(archive, "w:gz") as t:
            t.add(run / "pcd", arcname=run.name + "/pcd")
        restored = self.mod.unpack_map(archive, self.root / "download")
        self.assertEqual(restored.name, run.name)
        self.assertEqual(self.mod.validate_pcd_dir(restored / "pcd")["total_points"], 1)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("hz_mapping_session"), "会话工具尚未实现")
        self.mod = importlib.import_module("hz_mapping_session")
        self.env = {"ROS_DOMAIN_ID": "88", "ROS_HOME": "/home/car/hz_ws/.ros"}

    def test_selection_does_not_signal_other_user_or_workspace(self):
        argv = ["/home/car/hz_ws/install/fast_livo/lib/fast_livo/fastlivo_mapping"]
        self.assertEqual(self.mod.classify_process(argv, self.env, 1000, 1000), "mapping")
        self.assertIsNone(self.mod.classify_process(argv, self.env, 1001, 1000))
        env = dict(self.env, ROS_HOME="/home/car/.ros")
        self.assertIsNone(self.mod.classify_process(argv, env, 1000, 1000))
        argv[0] = "/home/car/other_ws/install/fast_livo/lib/fast_livo/fastlivo_mapping"
        self.assertIsNone(self.mod.classify_process(argv, self.env, 1000, 1000))

    def test_camera_parent_selected_and_grep_not_selected(self):
        argv = ["/usr/bin/python3", "/opt/ros/humble/bin/ros2", "launch", "realsense2_camera", "rs_launch.py"]
        self.assertEqual(self.mod.classify_process(argv, self.env, 1000, 1000), "camera")
        self.assertIsNone(self.mod.classify_process(["grep", "fastlivo_mapping"], self.env, 1000, 1000))

    def test_autosave_copy_preserves_original_parameter_types(self):
        original = {"/**": {"ros__parameters": {"pcd_save": {"pcd_save_en": True, "interval": -1}, "vio": {"img_point_cov": 100}}}}
        before = json.dumps(original)
        copied = self.mod.autosave_params(original)
        self.assertEqual(json.dumps(original), before)
        self.assertEqual(copied["/**"]["ros__parameters"]["pcd_save"]["interval"], 1)
        self.assertIsInstance(copied["/**"]["ros__parameters"]["vio"]["img_point_cov"], int)


if __name__ == "__main__":
    unittest.main()
