"""Check refusal conditions without importing ROS or starting nodes."""
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).with_name("check_ros_isolation.py")
GOOD_ENV = {
    "WSL_DISTRO_NAME": "Ubuntu-22.04",
    "ROS_DISTRO": "humble",
    "ROS_DOMAIN_ID": "73",
    "ROS_LOCALHOST_ONLY": "1",
    "RMW_IMPLEMENTATION": "rmw_cyclonedds_cpp",
}


class IsolationChecks(unittest.TestCase):
    def setUp(self):
        if not MODULE_PATH.is_file():
            self.fail("The isolation checker has not been implemented")
        spec = importlib.util.spec_from_file_location("hz_isolation", MODULE_PATH)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_accepts_the_personal_local_environment(self):
        self.module.validate_environment(
            GOOD_ENV, "6.6.87-microsoft-standard-WSL2", "aphelios"
        )

    def test_refuses_unsafe_or_foreign_environments_before_ros(self):
        changes = [
            {"ROS_DISTRO": "jazzy"},
            {"ROS_DOMAIN_ID": "88"},
            {"ROS_LOCALHOST_ONLY": "0"},
            {"RMW_IMPLEMENTATION": "rmw_fastrtps_cpp"},
            {"WSL_DISTRO_NAME": "other"},
            {"CYCLONEDDS_URI": "file:///unexpected.xml"},
        ]
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    self.module.validate_environment(
                        dict(GOOD_ENV, **change),
                        "6.6.87-microsoft-standard-WSL2", "aphelios"
                    )
        with self.assertRaises(ValueError):
            self.module.validate_environment(GOOD_ENV, "6.8.0-generic", "aphelios")
        with self.assertRaises(ValueError):
            self.module.validate_environment(
                GOOD_ENV, "6.6.87-microsoft-standard-WSL2", "car"
            )

    def test_uses_selected_addresses_not_enumerated_interfaces(self):
        trace = (
            "interfaces: lo udp/127.0.0.1 eth0 udp/192.0.2.10\n"
            "[73] probe: ownip: udp/127.0.0.1\n"
        )
        self.assertEqual(self.module.selected_addresses(trace), ["127.0.0.1"])

    def test_rejects_missing_or_nonlocal_selection_evidence(self):
        traces = [
            "config: NetworkInterface address=127.0.0.1\n",
            "ownip: udp/192.0.2.10\n",
            "ownip: udp/127.0.0.1, udp/192.0.2.10\n",
            "ownip: udp/127.0.0.1 (ext: udp/192.0.2.10)\n",
        ]
        for trace in traces:
            with self.subTest(trace=trace):
                with self.assertRaises(ValueError):
                    self.module.selected_addresses(trace)


if __name__ == "__main__":
    unittest.main()
