"""Refusal and derived-world contracts; these tests never move a simulator."""
import copy
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
import run

class Contracts(unittest.TestCase):
    def test_invalid_identity_and_profile_are_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'world.sdf'
            for token,profile in [('bad','straight'),('0'*12,'arbitrary'),('../'*4,'straight')]:
                with self.assertRaises(ValueError):run.make_world(token,target,profile)
            self.assertFalse(target.exists())

    def test_derived_world_preserves_full_mechanical_model(self):
        with tempfile.TemporaryDirectory() as d:
            tree=run.make_world('a'*12,Path(d)/'world.sdf')
            original=ET.parse(run.ROOT/'sim/scenes/hz_hunter_full.sdf')
            model=copy.deepcopy(original.getroot().find("world/model[@name='hz_hunter_full']"))
            for link in model.findall('link'):
                for sensor in list(link.findall('sensor')):link.remove(sensor)
            for node in model.iter():
                if node.text:node.text=node.text.replace('/hz_sim/full','/hz_sim/motion/'+'a'*12)
            self.assertEqual(ET.canonicalize(ET.tostring(model,encoding='unicode'),strip_text=True),
                             ET.canonicalize(ET.tostring(tree.find("world/model[@name='hz_hunter_full']"),encoding='unicode'),strip_text=True))
            self.assertEqual(len(model.findall('joint')),6)
            self.assertNotIn('/hz_sim/full/cmd_vel',ET.tostring(tree.getroot(),encoding='unicode'))

    def test_transport_refuses_unknown_profile_without_network_actions(self):
        binary=run.OUT/'bin/full_motion_transport'
        for args in [['bad','straight'],['a'*12,'arbitrary']]:
            p=subprocess.run([str(binary),*args],capture_output=True,text=True,timeout=3)
            self.assertNotEqual(p.returncode,0)
            self.assertNotIn('"phase"',p.stdout)

    def test_transport_refuses_foreign_address_before_node_creation(self):
        p=subprocess.run([str(run.OUT/'bin/full_motion_transport'),'a'*12,'straight'],
                         env=dict(os.environ,IGN_IP='192.0.2.1'),capture_output=True,text=True,timeout=3)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('isolated Gazebo environment required',p.stderr)

if __name__=='__main__':unittest.main()
