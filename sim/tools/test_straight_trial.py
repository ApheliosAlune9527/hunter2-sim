"""Check refusal and cleanup paths without publishing or stepping Gazebo."""
from copy import deepcopy
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

try:
    import straight_trial
except ModuleNotFoundError:
    straight_trial = None


WORLD = Path(__file__).resolve().parent.parent / "scenes" / "hz_hunter_control.sdf"


def snapshot():
    provider = {"address": "tcp://127.0.0.1:46709", "process_uuid": "test-server",
                "request_type": "ignition.msgs.WorldControl", "response_type": "ignition.msgs.Boolean"}
    sdf_provider = dict(provider, request_type="ignition.msgs.SdfGeneratorConfig",
                        response_type="ignition.msgs.StringMsg")
    return {"stats": {"paused": True, "sim_time": {"sec": "0", "nsec": 0}, "iterations": "0"},
            "sdf": {"data": WORLD.read_text()}, "control_providers": [provider],
            "sdf_providers": [sdf_provider], "command_publishers": 0}


class TransportDouble:
    """Represent the external transport boundary and inject failures."""
    def __init__(self, state=None, fail=None):
        self.state = deepcopy(state or snapshot())
        self.calls = []
        self.fail = fail

    def call(self, operation):
        self.calls.append(operation)
        if operation == self.fail:
            raise TimeoutError("injected transport timeout")
        if operation == "snapshot":
            return deepcopy(self.state)
        if operation in ["step-drive", "step-stop"]:
            seconds = 2 if operation == "step-drive" else 1
            old = int(self.state["stats"]["sim_time"]["sec"])
            self.state["stats"]["sim_time"]["sec"] = str(old + seconds)
            self.state["stats"]["iterations"] = str((old + seconds) * 1000)
            root = ET.fromstring(self.state["sdf"]["data"])
            pose = root.find("world/model[@name='hz_hunter_core']/pose")
            pose.text = "0.175 0 0.165 0 0 0" if seconds == 2 else "0.2 0 0.165 0 0 0"
            self.state["sdf"]["data"] = ET.tostring(root, encoding="unicode")
        return {"ok": True, "odom": {"twist": {"linear": {"x": 0.0}}}}


class StraightTrialChecks(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(straight_trial, "The bounded trial coordinator has not been implemented")

    def test_check_mode_does_not_publish_or_advance(self):
        client = TransportDouble()
        result = straight_trial.run_trial(client, run=False)
        self.assertTrue(result["ok"])
        self.assertEqual(client.calls, ["snapshot"])

    def test_unpaused_world_is_refused_before_any_motion(self):
        state = snapshot()
        state["stats"]["paused"] = False
        client = TransportDouble(state)
        with self.assertRaises(ValueError):
            straight_trial.run_trial(client, run=True)
        self.assertEqual(client.calls, ["snapshot"])

    def test_wrong_topic_and_physics_step_are_refused(self):
        for source, replacement in [("/hz_sim/cmd_vel", "/cmd_vel"),
                                    ("<max_step_size>0.001</max_step_size>", "<max_step_size>0.01</max_step_size>")]:
            state = snapshot()
            state["sdf"]["data"] = state["sdf"]["data"].replace(source, replacement)
            client = TransportDouble(state)
            with self.assertRaises(ValueError):
                straight_trial.run_trial(client, run=True)
            self.assertEqual(client.calls, ["snapshot"])

    def test_ambiguous_or_remote_service_is_refused(self):
        for mutation in ["remote", "duplicate", "different-server", "publisher"]:
            state = snapshot()
            if mutation == "remote":
                state["control_providers"][0]["address"] = "tcp://192.168.31.204:1234"
            elif mutation == "duplicate":
                state["control_providers"] *= 2
            elif mutation == "different-server":
                state["sdf_providers"][0]["process_uuid"] = "other-server"
            else:
                state["command_publishers"] = 1
            client = TransportDouble(state)
            with self.assertRaises(ValueError):
                straight_trial.run_trial(client, run=True)
            self.assertEqual(client.calls, ["snapshot"])

    def test_success_uses_only_the_fixed_steps_and_clears_then_pauses(self):
        client = TransportDouble()
        result = straight_trial.run_trial(client, run=True)
        self.assertTrue(result["ok"])
        self.assertAlmostEqual(result["longitudinal_distance_m"], 0.2)
        self.assertEqual(result["advanced_sim_s"], 3)
        self.assertEqual(client.calls.count("step-drive"), 1)
        self.assertEqual(client.calls.count("step-stop"), 1)
        self.assertEqual(client.calls[-2:], ["stop", "pause"])

    def test_step_timeout_is_not_retried_and_triggers_stop_and_pause(self):
        client = TransportDouble(fail="step-drive")
        result = straight_trial.run_trial(client, run=True)
        self.assertFalse(result["ok"])
        self.assertEqual(client.calls.count("step-drive"), 1)
        self.assertNotIn("step-stop", client.calls)
        self.assertEqual(client.calls[-2:], ["stop", "pause"])
        self.assertTrue(result["restart_required_after_failure"])

    def test_stop_failure_still_attempts_to_pause(self):
        client = TransportDouble(fail="stop")
        result = straight_trial.run_trial(client, run=True)
        self.assertFalse(result["ok"])
        self.assertEqual(client.calls[-1], "pause")

    def test_interrupted_trial_requires_a_new_server_before_retry(self):
        previous = {"restart_required_after_failure": True, "before": snapshot()}
        client = TransportDouble()
        with self.assertRaises(ValueError):
            straight_trial.run_trial(client, run=True, previous_report=previous)
        self.assertEqual(client.calls, ["snapshot"])
        state = snapshot()
        for key in ["control_providers", "sdf_providers"]:
            state[key][0]["process_uuid"] = "new-server"
        self.assertTrue(straight_trial.run_trial(TransportDouble(state), run=True,
                                               previous_report=previous)["ok"])

    def test_check_mode_reports_restart_requirement_without_motion(self):
        previous = {"restart_required_after_failure": True, "before": snapshot()}
        client = TransportDouble()
        with self.assertRaisesRegex(ValueError, "重新打开"):
            straight_trial.run_trial(client, run=False, previous_report=previous)
        self.assertEqual(client.calls, ["snapshot"])

        state = snapshot()
        for key in ["control_providers", "sdf_providers"]:
            state[key][0]["process_uuid"] = "new-server"
        client = TransportDouble(state)
        self.assertTrue(straight_trial.run_trial(client, run=False,
                                               previous_report=previous)["ok"])
        self.assertEqual(client.calls, ["snapshot"])


if __name__ == "__main__":
    unittest.main()
