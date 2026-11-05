"""Adapter contracts with stand-ins for unavailable ROS imports, not ROS runtime tests."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "package"))
import hz_launch_support as support


class Action:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class Configuration:
    def __init__(self, name):
        self.name = name

    def perform(self, context):
        return context[self.name]


def module(name, **attributes):
    result = types.ModuleType(name)
    result.__dict__.update(attributes)
    return result


class AdapterTests(unittest.TestCase):
    def setUp(self):
        modules = {
            "launch": module("launch", LaunchDescription=Action),
            "launch.actions": module("launch.actions", **{name: type(name, (Action,), {}) for name in ("DeclareLaunchArgument", "EmitEvent", "ExecuteProcess", "OpaqueFunction", "RegisterEventHandler")}),
            "launch.event_handlers": module("launch.event_handlers", OnProcessIO=type("OnProcessIO", (Action,), {})),
            "launch.events": module("launch.events", Shutdown=type("Shutdown", (Action,), {})),
            "launch.substitutions": module("launch.substitutions", LaunchConfiguration=Configuration),
        }
        self.modules = patch.dict(sys.modules, modules)
        self.modules.start()
        self.addCleanup(self.modules.stop)
        spec = importlib.util.spec_from_file_location("hz_adapter_test", PROJECT / "package/hz_mapping.launch.py")
        self.entry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.entry)
        temp = tempfile.TemporaryDirectory(prefix="hz_adapter_test_")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.log = self.root / "mapping.log"

    def start(self):
        spec = support.ProcessSpec(["mapping-fixture"], self.root, self.log, True)
        with patch.object(support, "require_robot_environment"), patch.object(support, "verify_helpers"), patch.object(support, "load_existing_helper", return_value=types.SimpleNamespace(processes=lambda: {})), patch.object(support, "build_spec", return_value=spec):
            return self.entry.start_role({"role": "mapping"})

    def test_stdout_stderr_are_copied_while_screen_output_is_enabled(self):
        actions = self.start()
        handler, process = actions
        self.assertEqual(process.kwargs["output"], "screen")
        self.assertTrue(process.kwargs["emulate_tty"])
        self.assertFalse(process.kwargs["cached_output"])
        self.assertFalse(process.kwargs["respawn"])
        io_handler = handler.args[0]
        io_handler.kwargs["on_stdout"](types.SimpleNamespace(text=b"stdout line\n"))
        io_handler.kwargs["on_stderr"](types.SimpleNamespace(text=b"stderr line\n"))
        self.assertEqual(self.log.read_bytes(), b"stdout line\nstderr line\n")
        result = process.kwargs["on_exit"](types.SimpleNamespace(returncode=0), {})
        self.assertEqual(len(result), 1)
        self.assertEqual(type(result[0].kwargs["event"]).__name__, "Shutdown")

    def test_failed_child_is_reported_and_restart_marker_is_preserved(self):
        _, process = self.start()
        with self.assertRaisesRegex(RuntimeError, "退出码为 1"):
            process.kwargs["on_exit"](types.SimpleNamespace(returncode=1), {})
        self.assertTrue(self.log.exists())
        with self.assertRaises(FileExistsError):
            self.start()

    def test_omitting_role_defaults_to_read_only_status(self):
        description = self.entry.generate_launch_description()
        role_argument = description.args[0][0]
        self.assertEqual(role_argument.kwargs["default_value"], "status")
        self.assertEqual(set(role_argument.kwargs["choices"]), set(support.ROLES))


if __name__ == "__main__":
    unittest.main()
