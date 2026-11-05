import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "build_support"))
try:
    installer = importlib.import_module("installer")
except ModuleNotFoundError:
    installer = None


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(installer, "Non-overwrite installer has not been implemented")
        self.temp = tempfile.TemporaryDirectory(prefix="hz_install_test_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "hz_ws"
        (self.root / "scripts").mkdir(parents=True)
        self.helper = self.root / "scripts/hz_mapping_session.py"
        self.helper.write_bytes(b"original helper\n")
        self.exporter = self.root / "scripts/pcd_export.py"
        self.exporter.write_bytes(b"original exporter\n")
        self.payload = {
            "hz_env.sh": b"# personal environment\n",
            "hz_mapping.launch.py": b"# personal launch\n",
            "compatibility.json": json.dumps({"files": {
                "scripts/hz_mapping_session.py": hashlib.sha256(self.helper.read_bytes()).hexdigest(),
                "scripts/pcd_export.py": hashlib.sha256(self.exporter.read_bytes()).hexdigest(),
            }}).encode(),
        }
        self.archive = Path(self.temp.name) / "final.zip"

    def make_archive(self, extra=None, bad_payload=False):
        manifest = {"format": "hz_mapping_tools_bundle_v1", "bundle_name": "hz_mapping_tools", "files": {
            name: hashlib.sha256(data).hexdigest() for name, data in self.payload.items()
        }}
        with zipfile.ZipFile(self.archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("__main__.py", b"# test installer\n")
            z.writestr("manifest.json", json.dumps(manifest).encode())
            for name, data in self.payload.items():
                z.writestr("payload/" + name, b"tampered" if bad_payload and name == "hz_env.sh" else data)
            if extra:
                extra(z)
        return hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def install(self, sha):
        return installer.install_archive(self.archive, self.root, sha)

    def test_installs_only_new_directory_and_keeps_originals(self):
        sha = self.make_archive()
        target = self.install(sha)
        self.assertEqual(target, self.root / "hz_mapping_tools")
        for name, data in self.payload.items():
            self.assertEqual((target / name).read_bytes(), data)
        self.assertEqual(self.helper.read_bytes(), b"original helper\n")
        self.assertEqual(self.exporter.read_bytes(), b"original exporter\n")

    def test_identical_install_is_verified_without_rewrite(self):
        sha = self.make_archive()
        target = self.install(sha)
        before = {p.name: p.stat().st_mtime_ns for p in target.iterdir()}
        self.assertEqual(self.install(sha), target)
        self.assertEqual(before, {p.name: p.stat().st_mtime_ns for p in target.iterdir()})

    def test_different_existing_file_is_never_overwritten(self):
        sha = self.make_archive()
        target = self.install(sha)
        (target / "hz_env.sh").write_bytes(b"user changed this")
        with self.assertRaisesRegex(installer.InstallError, "存在|覆盖|不同"):
            self.install(sha)
        self.assertEqual((target / "hz_env.sh").read_bytes(), b"user changed this")

    def test_hash_mismatch_does_not_create_target(self):
        self.make_archive()
        with self.assertRaisesRegex(installer.InstallError, "SHA256"):
            self.install("0" * 64)
        self.assertFalse((self.root / "hz_mapping_tools").exists())

    def test_changed_existing_helper_refuses_install(self):
        sha = self.make_archive()
        self.helper.write_bytes(b"different version")
        with self.assertRaisesRegex(installer.InstallError, "版本|校验|依赖"):
            self.install(sha)
        self.assertFalse((self.root / "hz_mapping_tools").exists())
        self.assertEqual(self.helper.read_bytes(), b"different version")

    def test_parent_traversal_is_rejected_before_any_write(self):
        sha = self.make_archive(lambda z: z.writestr("payload/../../senior.yaml", b"bad"))
        with self.assertRaises(installer.InstallError):
            self.install(sha)
        self.assertFalse((self.root.parent / "senior.yaml").exists())
        self.assertFalse((self.root / "hz_mapping_tools").exists())

    def test_unlisted_payload_is_rejected(self):
        sha = self.make_archive(lambda z: z.writestr("payload/unknown.sh", b"bad"))
        with self.assertRaises(installer.InstallError):
            self.install(sha)

    def test_zip_symlink_is_rejected(self):
        def link(z):
            info = zipfile.ZipInfo("payload/link")
            info.create_system = 3
            info.external_attr = (0o120777 << 16)
            z.writestr(info, "/home/car/senior_ws/config")
        sha = self.make_archive(link)
        with self.assertRaises(installer.InstallError):
            self.install(sha)

    def test_corrupt_member_is_rejected(self):
        sha = self.make_archive(bad_payload=True)
        with self.assertRaisesRegex(installer.InstallError, "校验|SHA256"):
            self.install(sha)

    def test_target_symlink_is_rejected(self):
        sha = self.make_archive()
        outside = self.root.parent / "senior_ws"
        outside.mkdir()
        (self.root / "hz_mapping_tools").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(installer.InstallError):
            self.install(sha)
        self.assertEqual(list(outside.iterdir()), [])

    def test_root_symlink_is_rejected(self):
        sha = self.make_archive()
        alias = self.root.parent / "alias_ws"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(installer.InstallError):
            installer.install_archive(self.archive, alias, sha)


if __name__ == "__main__":
    unittest.main()
