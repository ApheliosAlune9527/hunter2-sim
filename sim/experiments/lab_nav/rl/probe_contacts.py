"""Drive straight into the far wall and report what the contact bridge sees.

Collision scoring is only worth anything if the data behind it exists.  A run
that reports "0 collisions" while the contact topic carries nothing looks like a
clean run and is not one, so this probe drives into a wall on purpose and prints
the raw contact count, the filtered count and the first few pairs.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hz_nav_env import HzLabNavEnv, _vehicle_contacts  # noqa: E402

OUT = Path(__file__).resolve().parents[4] / 'outputs/lab_nav_20261105/rl_contact_probe.json'


def main():
    env = HzLabNavEnv(seed=3)
    env.start()
    result = {'seconds': [], 'goal': None}
    try:
        env.reset(goal=(1.885, 0.435))
        env._node.raw_contacts = 0
        env._node.contacts = []
        for i in range(140):
            env.step((1.0, 0.0))
            truth = env._node.truth
            result['seconds'].append({
                't': round(env._node.sim_time - env._sim_start, 1),
                'x': round(truth[0], 2), 'y': round(truth[1], 2),
                'raw': env._node.raw_contacts,
                'kept': len(_vehicle_contacts(env._node.contacts)),
            })
            env._node.contacts = []
            if env._node.raw_contacts:
                break
        result['raw_contact_messages'] = env._node.raw_contacts
        result['truth_at_end'] = [round(v, 3) for v in env._node.truth]
        result['contact_topic_seen'] = bool(env._node.raw_contacts)
    finally:
        env.close()
    OUT.write_text(json.dumps(result, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'seconds'}, indent=1))
    print('last samples:', json.dumps(result['seconds'][-3:]))


if __name__ == '__main__':
    main()
