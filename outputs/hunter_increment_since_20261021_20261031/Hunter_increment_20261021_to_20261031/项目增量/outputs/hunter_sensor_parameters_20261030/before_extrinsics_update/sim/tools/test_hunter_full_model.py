"""Offline acceptance checks for the self-contained HUNTER 2.0 description.

These tests only read files. They never invoke ROS, WSL, a simulator or hardware.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "sim/hz_hunter_full_description"
URDF = PACKAGE / "urdf/hunter_full.urdf"
COMMIT = "9d7888affce35321c657c1c8528307f3115b9d41"
WHEELS = ("rear_left", "rear_right", "front_left", "front_right")


def numbers(text):
    return tuple(map(float, text.split()))


def stl_vertices(path):
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + count * 50:
        raise AssertionError(f"Expected a complete binary STL: {path}")
    return [struct.unpack_from("<3f", data, 84 + i * 50 + 12 + j * 12)
            for i in range(count) for j in range(3)]


def bounds(vertices):
    lower = tuple(min(v[i] for v in vertices) for i in range(3))
    upper = tuple(max(v[i] for v in vertices) for i in range(3))
    return lower, upper, tuple(upper[i] - lower[i] for i in range(3))


def rpy_matrix(rpy):
    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return ((cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
            (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
            (-sp, cp * sr, cp * cr))


def transform(point, xyz, rotation):
    return tuple(xyz[i] + sum(rotation[i][j] * point[j] for j in range(3)) for i in range(3))


def compose(a, b):
    ta, ra = a
    tb, rb = b
    return transform(tb, ta, ra), tuple(tuple(sum(ra[i][k] * rb[k][j] for k in range(3))
                                           for j in range(3)) for i in range(3))


class HunterFullModelTests(unittest.TestCase):
    def model(self):
        self.assertTrue(URDF.is_file(), "Full CAD URDF has not been generated")
        return ET.parse(URDF).getroot()

    def report(self):
        self.model()
        path = PACKAGE / "geometry_report.json"
        self.assertTrue(path.is_file(), "Geometry/TF evidence is required")
        return json.loads(path.read_text(encoding="utf-8"))

    def mesh_path(self, uri):
        prefix = "package://hz_hunter_full_description/"
        self.assertTrue(uri.startswith(prefix), f"External mesh URI: {uri}")
        path = PACKAGE / uri.removeprefix(prefix)
        self.assertTrue(path.resolve().is_relative_to(PACKAGE.resolve()))
        self.assertTrue(path.is_file(), f"Missing local mesh: {path}")
        return path

    def frames(self, model):
        frames = {"base_link": ((0, 0, 0), rpy_matrix((0, 0, 0)))}
        pending = list(model.findall("joint"))
        while pending:
            count = len(pending)
            for joint in pending[:]:
                parent, child = joint.find("parent").get("link"), joint.find("child").get("link")
                if parent in frames:
                    origin = joint.find("origin")
                    xyz = numbers(origin.get("xyz", "0 0 0"))
                    rpy = numbers(origin.get("rpy", "0 0 0"))
                    frames[child] = compose(frames[parent], (xyz, rpy_matrix(rpy)))
                    pending.remove(joint)
            self.assertLess(len(pending), count, "Disconnected or cyclic link tree")
        return frames

    def test_ament_data_package_and_exact_model_identity(self):
        model = self.model()
        self.assertEqual(model.get("name"), "hz_hunter_full")
        package_xml = ET.parse(PACKAGE / "package.xml").getroot()
        self.assertEqual(package_xml.findtext("name"), "hz_hunter_full_description")
        self.assertEqual(package_xml.findtext("export/build_type"), "ament_cmake")
        cmake = (PACKAGE / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("install(DIRECTORY urdf meshes", cmake)

    def test_four_independent_y_axis_roll_and_two_z_axis_steering(self):
        model = self.model()
        joints = {joint.get("name"): joint for joint in model.findall("joint")}
        active = {name for name, joint in joints.items() if joint.get("type") != "fixed"}
        expected = {f"{wheel}_wheel_joint" for wheel in WHEELS}
        expected |= {f"front_{side}_steering_joint" for side in ("left", "right")}
        self.assertEqual(active, expected)
        frames = self.frames(model)
        for wheel in WHEELS:
            joint = joints[f"{wheel}_wheel_joint"]
            self.assertEqual(joint.get("type"), "continuous")
            self.assertEqual(numbers(joint.find("axis").get("xyz")), (0, 1, 0))
            child = joint.find("child").get("link")
            self.assertEqual(child, f"{wheel}_wheel_link")
            expected_xyz = (0.650 if wheel.startswith("front") else 0,
                            0.3025 if wheel.endswith("left") else -0.3025, 0)
            for value, expected_value in zip(frames[child][0], expected_xyz):
                self.assertAlmostEqual(value, expected_value, places=8)
        for side in ("left", "right"):
            steering = joints[f"front_{side}_steering_joint"]
            self.assertEqual(steering.get("type"), "revolute")
            self.assertEqual(numbers(steering.find("axis").get("xyz")), (0, 0, 1))
            self.assertAlmostEqual(float(steering.find("limit").get("lower")), -0.58)
            self.assertAlmostEqual(float(steering.find("limit").get("upper")), 0.58)

    def test_cad_chassis_and_four_wheels_without_duplicate_steer_wheels(self):
        model = self.model()
        links = {link.get("name"): link for link in model.findall("link")}
        chassis_mesh = links["base_link"].find("visual/geometry/mesh")
        self.assertIsNotNone(chassis_mesh, "The chassis must use actual CAD")
        self.assertGreater(len(stl_vertices(self.mesh_path(chassis_mesh.get("filename")))), 3000)
        wheel_uris = []
        for wheel in WHEELS:
            visuals = links[f"{wheel}_wheel_link"].findall("visual")
            self.assertEqual(len(visuals), 1)
            mesh = visuals[0].find("geometry/mesh")
            self.assertIsNotNone(mesh)
            wheel_uris.append(mesh.get("filename"))
            self.assertGreater(len(stl_vertices(self.mesh_path(mesh.get("filename")))), 1000)
        self.assertEqual(len(set(wheel_uris)), 4)
        all_uris = [mesh.get("filename") for mesh in model.findall(".//visual/geometry/mesh")]
        for uri in wheel_uris:
            self.assertEqual(all_uris.count(uri), 1)
        for side in ("left", "right"):
            self.assertEqual(links[f"front_{side}_steering_link"].findall("visual"), [])
        self.assertFalse(any("front_steer_left_link.STL" in uri or "front_steer_right_link.STL" in uri
                             or "hunter_2_0.STL" in uri for uri in all_uris))

    def test_local_wheel_geometry_is_centered_on_y_roll_axis(self):
        model = self.model()
        for wheel in WHEELS:
            link = model.find(f"link[@name='{wheel}_wheel_link']")
            mesh = link.find("visual/geometry/mesh")
            lower, upper, size = bounds(stl_vertices(self.mesh_path(mesh.get("filename"))))
            self.assertAlmostEqual(size[0], 0.330, delta=0.012)
            self.assertAlmostEqual(size[2], 0.330, delta=0.012)
            self.assertGreater(size[1], 0.09)
            self.assertLess(size[1], 0.16)
            for i in range(3):
                self.assertAlmostEqual((lower[i] + upper[i]) / 2, 0, delta=0.003)

    def test_real_bare_chassis_visual_envelope_matches_hunter_dimensions(self):
        model = self.model()
        frames = self.frames(model)
        vertices = []
        body_links = {"base_link", *(f"{wheel}_wheel_link" for wheel in WHEELS),
                      "front_steer_bar_link", "rear_axle_detail_link"}
        for link in model.findall("link"):
            if link.get("name") not in body_links:
                continue
            for visual in link.findall("visual"):
                mesh = visual.find("geometry/mesh")
                self.assertIsNotNone(mesh)
                origin = visual.find("origin")
                local = (numbers(origin.get("xyz", "0 0 0")), rpy_matrix(numbers(origin.get("rpy", "0 0 0"))))
                pose = compose(frames[link.get("name")], local)
                scale = numbers(mesh.get("scale", "1 1 1"))
                vertices.extend(transform(tuple(v[i] * scale[i] for i in range(3)), *pose)
                                for v in stl_vertices(self.mesh_path(mesh.get("filename"))))
        _, _, size = bounds(vertices)
        for actual, expected in zip(size, (0.980, 0.745, 0.370)):
            self.assertAlmostEqual(actual, expected, delta=0.026)
        report = self.report()
        for actual, reported in zip(size, report["bare_chassis_bounds_m"]["size"]):
            self.assertAlmostEqual(actual, reported, places=6)

    def test_reference_tf_and_actual_sensor_carriers_preserved(self):
        model = self.model()
        frames = self.frames(model)
        expected = {"reference_base_link": (0.325, 0, -0.165),
                    "hesai_lidar": (0.539, 0, 0.525),
                    "camera_link": (0.65765, 0.0175, 0.481),
                    "imu_link": (0.64591, 0.01198, 0.4861)}
        for name, xyz in expected.items():
            self.assertIn(name, frames)
            for actual, target in zip(frames[name][0], xyz):
                self.assertAlmostEqual(actual, target, places=7)
        yaw = math.atan2(frames["hesai_lidar"][1][1][0], frames["hesai_lidar"][1][0][0])
        self.assertAlmostEqual(yaw, math.pi / 2, places=7)
        report = self.report()
        for name in ("hesai_lidar", "camera_link", "imu_link"):
            self.assertIn(name, report["tf_from_base_link"])
        self.assertEqual(report["sensor_carriers"]["lidar"]["link"], "hesai_lidar")
        self.assertEqual(report["sensor_carriers"]["camera"]["link"], "camera_link")
        self.assertEqual(report["sensor_carriers"]["imu"]["link"], "imu_link")
        self.assertIn("assumption", report["sensor_carriers"]["imu"]["status"].lower())

    def test_no_arm_and_all_visual_assets_are_self_contained(self):
        model = self.model()
        self.assertFalse(any("piper" in link.get("name").lower() for link in model.findall("link")))
        for mesh in model.findall(".//mesh"):
            self.mesh_path(mesh.get("filename"))
        names = {Path(mesh.get("filename")).name.lower() for mesh in model.findall(".//visual/geometry/mesh")}
        self.assertTrue({"assembly.stl", "xt32.stl", "d435.dae", "g60.stl", "ars548.stl"}.issubset(names))
        camera_path = self.mesh_path(model.find("link[@name='camera_link']/visual/geometry/mesh").get("filename"))
        collada = ET.parse(camera_path).getroot()
        ns = {"c": "http://www.collada.org/2005/11/COLLADASchema"}
        for init in collada.findall(".//c:library_images/c:image/c:init_from", ns):
            self.assertFalse("://" in init.text, "Remote camera textures are not allowed")
            self.assertTrue((camera_path.parent / init.text).is_file())

    def test_positive_rigid_body_inertias_and_separate_simple_collisions(self):
        model = self.model()
        total_mass = 0
        for link in model.findall("link"):
            inertial = link.find("inertial")
            self.assertIsNotNone(inertial, f"Every retained physical/frame link needs valid inertia: {link.get('name')}")
            mass = float(inertial.find("mass").get("value"))
            self.assertTrue(math.isfinite(mass) and mass > 0)
            total_mass += mass
            tensor = inertial.find("inertia").attrib
            xx, yy, zz = (float(tensor[key]) for key in ("ixx", "iyy", "izz"))
            xy, xz, yz = (float(tensor[key]) for key in ("ixy", "ixz", "iyz"))
            self.assertTrue(all(math.isfinite(value) for value in (xx, yy, zz, xy, xz, yz)))
            self.assertGreater(xx, 0)
            self.assertGreater(xx * yy - xy * xy, 0)
            determinant = xx * yy * zz + 2 * xy * xz * yz - xx * yz * yz - yy * xz * xz - zz * xy * xy
            self.assertGreater(determinant, 0)
            for a, b, c in ((xx, yy, zz), (yy, zz, xx), (zz, xx, yy)):
                self.assertLessEqual(a, b + c + 1e-12, "Inertia violates the triangle inequality")
            self.assertEqual(link.findall("collision/geometry/mesh"), [])
        self.assertGreater(total_mass, 70)
        self.assertLess(total_mass, 90)
        for wheel in WHEELS:
            link = model.find(f"link[@name='{wheel}_wheel_link']")
            cylinder = link.find("collision/geometry/cylinder")
            self.assertIsNotNone(cylinder)
            self.assertAlmostEqual(float(cylinder.get("radius")), 0.165)
            rpy = numbers(link.find("collision/origin").get("rpy"))
            axis = transform((0, 0, 1), (0, 0, 0), rpy_matrix(rpy))
            self.assertAlmostEqual(abs(axis[1]), 1)
        report = self.report()
        self.assertAlmostEqual(report["mass_assumptions"]["bare_chassis_kg"], 70)
        self.assertAlmostEqual(report["mass_assumptions"]["total_kg"], total_mass, places=5)
        self.assertTrue(report["uncalibrated"])

    def test_visual_mass_centres_lie_inside_their_component_envelopes(self):
        model = self.model()
        frames = self.frames(model)
        visual_bounds = self.report()["visual_geometry"]
        for link in model.findall("link"):
            name = link.get("name")
            if name not in visual_bounds:
                continue
            local = numbers(link.find("inertial/origin").get("xyz"))
            centre = transform(local, *frames[name])
            envelope = visual_bounds[name]["bounds_in_base_m"]
            for axis in range(3):
                self.assertGreaterEqual(centre[axis], envelope["min"][axis] - 1e-6,
                                        f"{name} mass centre lies outside its own geometry")
                self.assertLessEqual(centre[axis], envelope["max"][axis] + 1e-6,
                                     f"{name} mass centre lies outside its own geometry")

    def test_fixed_revision_and_output_sha256_manifest(self):
        self.model()
        manifest = json.loads((PACKAGE / "source_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["upstream"]["commit"], COMMIT)
        self.assertIn("TODO", manifest["upstream"]["license_note"])
        self.assertGreaterEqual(len(manifest["upstream"]["files"]), 10)
        self.assertGreaterEqual(len(manifest["local_sources"]), 7)
        for entry in manifest["outputs"]:
            path = PACKAGE / entry["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])
        output_paths = {entry["path"] for entry in manifest["outputs"]}
        self.assertIn("urdf/hunter_full.urdf", output_paths)
        self.assertTrue(any(path.startswith("meshes/chassis/") for path in output_paths))
        self.assertTrue(any(path.startswith("meshes/upfit/") for path in output_paths))


if __name__ == "__main__":
    unittest.main(verbosity=2)
