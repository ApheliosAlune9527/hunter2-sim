"""Exercise only offline and refusal modes, never launch the GUI."""
from pathlib import Path
import subprocess
import unittest

LAUNCHER = Path(__file__).with_name("start_paused_scene.bash")


class PausedLauncherChecks(unittest.TestCase):
    def setUp(self):
        if not LAUNCHER.is_file():
            self.fail("The paused scene launcher has not been implemented")

    def test_offline_check_completes_without_running_a_simulator(self):
        result = subprocess.run(
            ["bash", str(LAUNCHER), "--check"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("暂停场景文件检查通过", result.stdout)

    def test_rejects_arguments_that_can_change_the_launch_mode(self):
        for args in [["-r"], ["--run"], ["other.sdf"], ["--check", "-r"]]:
            with self.subTest(args=args):
                result = subprocess.run(
                    ["bash", str(LAUNCHER), *args],
                    capture_output=True, text=True, timeout=10,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("不接受额外的仿真启动参数", result.stderr)


if __name__ == "__main__":
    unittest.main()
