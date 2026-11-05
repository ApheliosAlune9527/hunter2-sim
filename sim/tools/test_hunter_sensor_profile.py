"""Source pins and transform direction checks without ROS or device imports."""
import math
from pathlib import Path
import shutil
import tempfile
import unittest

import hunter_sensor_profile as profile

ROOT = Path(__file__).resolve().parents[2]


class SensorProfileTests(unittest.TestCase):
    def test_exported_sources_are_verified_and_physical_accuracy_is_not_claimed(self):
        data = profile.profile_report(ROOT)
        self.assertEqual(len(data['sources']), 4)
        self.assertEqual(data['imu']['device'], 'CH104')
        self.assertFalse(data['imu']['axis_permutation'])
        self.assertFalse(data['physical_calibration_verified'])

    def test_changed_source_is_rejected_before_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative, _ in profile.SOURCE_FILES.values():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, path)
            profile.validate_sources(root)
            source = root / profile.SOURCE_FILES['source_ch104'][0]
            source.write_bytes(source.read_bytes() + b'\n# changed\n')
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                profile.validate_sources(root)

    def test_inverse_pose_handles_nonsymmetric_rotation_and_translation(self):
        angle = .37
        c, s = math.cos(angle), math.sin(angle)
        rotation = ((c, -s, 0.), (s, c, 0.), (0., 0., 1.))
        translation = (.13, -.27, .08)
        t_inv, r_inv = profile.inverse_pose(translation, rotation)
        for point in ((0., 0., 0.), (.21, -.73, 1.4)):
            mapped = [sum(rotation[i][j] * point[j] for j in range(3)) + translation[i]
                      for i in range(3)]
            recovered = [sum(r_inv[i][j] * mapped[j] for j in range(3)) + t_inv[i]
                         for i in range(3)]
            for actual, expected in zip(recovered, point):
                self.assertAlmostEqual(actual, expected, places=12)


if __name__ == '__main__':
    unittest.main()
