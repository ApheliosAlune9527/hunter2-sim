"""Refuse an actuation bridge or a frame/topic leak in the full-model entry."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class FullRosInterfacesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            'full_ros_interfaces', ROOT / 'sim/tools/check_full_ros_interfaces.py')
        cls.contract = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.contract)
        cls.config = json.loads((ROOT / 'sim/config/hunter_full_bridge.yaml').read_text(encoding='utf-8'))

    def test_sensor_and_state_interfaces_are_complete_and_gazebo_to_ros_only(self):
        report = self.contract.validate_bridge_config(self.config)
        self.assertEqual(9, report['bridge_count'])
        self.assertFalse(report['actuation_bridge'])

    def test_rejects_command_publisher_added_to_config(self):
        data = copy.deepcopy(self.config)
        data.append({'ros_topic_name': '/hz_sim/full/cmd_vel',
                     'gz_topic_name': '/hz_sim/full/cmd_vel',
                     'ros_type_name': 'geometry_msgs/msg/Twist',
                     'gz_type_name': 'ignition.msgs.Twist', 'direction': 'ROS_TO_GZ'})
        with self.assertRaises(ValueError):
            self.contract.validate_bridge_config(data)

    def test_rejects_reverse_bridge_missing_interface_and_unscoped_tf(self):
        for mutation in ('direction', 'missing', 'tf'):
            with self.subTest(mutation=mutation):
                data = copy.deepcopy(self.config)
                if mutation == 'direction':
                    data[0]['direction'] = 'BIDIRECTIONAL'
                elif mutation == 'missing':
                    data.pop()
                else:
                    data[-1]['ros_topic_name'] = '/tf'
                with self.assertRaises(ValueError):
                    self.contract.validate_bridge_config(data)

    def test_rejects_nonlocal_or_wrong_message_type(self):
        for key, value in [('ros_topic_name', '/scan'),
                           ('gz_type_name', 'ignition.msgs.Twist'),
                           ('ros_type_name', 'geometry_msgs/msg/Twist')]:
            with self.subTest(key=key):
                data = copy.deepcopy(self.config)
                data[1][key] = value
                with self.assertRaises(ValueError):
                    self.contract.validate_bridge_config(data)

    def test_scan_height_filter_preserves_original_ground_referenced_band(self):
        settings = self.contract.scan_parameters()
        self.assertEqual('hz_sim/full/base_link', settings['target_frame'])
        self.assertAlmostEqual(.10, settings['min_height'] + .165)
        self.assertAlmostEqual(.85, settings['max_height'] + .165)
        self.assertTrue(settings['use_sim_time'])


if __name__ == '__main__':
    unittest.main()
