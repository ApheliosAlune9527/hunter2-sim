"""Independent scene check: is the world loaded and is its clock advancing?

The old load_check.json claimed success while its own output said
"Service call to [/gazebo/worlds] timed out" and `sim_time_reached: false`, so it
verified nothing.  This script asks the running simulation two questions that a
fake pass cannot answer:

  1. does the scene report the expected models (floor, walls, hz_hunter_full)?
  2. does /clock advance by the expected amount over a measured wall-clock window?

It also records the wall/sim ratio, because that number belongs to this run and must
not be quoted later as a property of the platform.

Writes outputs/lab_nav_fix_20261106/sim_load_check.json.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from rosgraph_msgs.msg import Clock

ROOT = Path('/mnt/d/rob-memory')
OUT = ROOT / 'outputs/lab_nav_fix_20261106'
WORLD = 'hz_lab_2d'
EXPECTED_MODELS = ['floor', 'walls', 'hz_hunter_full']


def list_models():
    try:
        out = subprocess.run(['ign', 'model', '--list'], capture_output=True, text=True,
                             timeout=15)
        # `ign model --list` prints a header and a bullet before each name.
        names = []
        for line in out.stdout.splitlines():
            line = line.strip()
            if not line or line.endswith('...') or line.startswith('Available'):
                continue
            names.append(line.lstrip('- ').strip())
        return names
    except Exception as exc:                      # pragma: no cover - diagnostic path
        return [f'<error: {exc}>']


def main():
    rclpy.init()
    node = Node('sim_load_check')
    samples = []

    def on_clock(msg):
        samples.append(msg.clock.sec + msg.clock.nanosec * 1e-9)

    node.create_subscription(Clock, '/clock', on_clock, 10)
    wall0 = time.monotonic()
    end = wall0 + 5.0
    while time.monotonic() < end and len(samples) < 200:
        rclpy.spin_once(node, timeout_sec=0.05)
    wall = time.monotonic() - wall0

    models = list_models()
    sim_span = (samples[-1] - samples[0]) if len(samples) >= 2 else 0.0
    advance_ok = len(samples) >= 10 and sim_span > 0.5 * wall

    doc = {
        'world': WORLD,
        'models_seen': models,
        'models_expected': EXPECTED_MODELS,
        'models_ok': all(m in models for m in EXPECTED_MODELS),
        'clock_messages': len(samples),
        'sim_span_s': round(sim_span, 3),
        'wall_span_s': round(wall, 3),
        'sim_per_wall': round(sim_span / wall, 3) if wall > 0 else None,
        'clock_advancing': bool(advance_ok),
        'note': ('sim_per_wall describes this run only; it is not a platform constant'),
    }
    doc['ok'] = bool(doc['models_ok'] and doc['clock_advancing'])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'sim_load_check.json').write_text(json.dumps(doc, indent=1), encoding='utf-8')
    print(json.dumps(doc, indent=1))
    node.destroy_node()
    rclpy.shutdown()
    return 0 if doc['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
