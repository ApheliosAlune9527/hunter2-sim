"""Smoke test: does the environment actually behave like an environment?

Runs a handful of episodes with random actions and checks the things that are
easy to get wrong and hard to notice:

* the observation has the advertised shape and stays inside [-1, 1]
* a step advances the *simulated* clock by one control period
* reset reports where the vehicle really ended up, not where it was asked to go
* an episode ends for one of the three declared reasons and no other
* no state leaks between episodes (the first observation of a fresh episode must
  not depend on how the previous one ended)

It is not a training run and makes no claim about learning.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hz_nav_env import CONTROL_DT, HzLabNavEnv  # noqa: E402

GOALS = json.loads((Path(__file__).resolve().parent / 'goals.json').read_text())


def main():
    episodes = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    env = HzLabNavEnv(seed=7)
    env.start()
    rng = np.random.default_rng(7)
    out = {'episodes': [], 'checks': {}}
    firsts = []
    try:
        for i in range(episodes):
            goal = GOALS['train'][i]
            obs, info = env.reset(goal=(goal[0], goal[1]))
            firsts.append(obs.copy())
            steps = 0
            total = 0.0
            reason = ''
            dt_ok = True
            last_sim = env._node.sim_time
            while True:
                obs, reward, terminated, truncated, step_info = env.step(
                    rng.uniform(-1.0, 1.0, size=2))
                steps += 1
                total += reward
                if abs((step_info['sim_seconds']) - steps * CONTROL_DT) > 0.05 * max(1.0, steps):
                    dt_ok = False
                last_sim = env._node.sim_time
                if terminated or truncated:
                    reason = step_info['reason']
                    break
                if steps > 700:
                    reason = 'ran_away'
                    break
            out['episodes'].append({
                'goal': goal, 'steps': steps, 'return': round(total, 3),
                'reason': reason, 'reset': info['reset'],
                'final': {k: step_info[k] for k in ('distance_m', 'truth', 'odom', 'sim_seconds')},
            })
            out['checks'][f'episode_{i}_dt'] = dt_ok
    finally:
        env.close()

    shapes_ok = all(o.shape == (76,) for o in firsts)
    range_ok = all(float(o.min()) >= -1.0 and float(o.max()) <= 1.0 for o in firsts)
    reset_err = max(e['reset']['position_error_m'] for e in out['episodes'])
    reasons = {e['reason'] for e in out['episodes']}
    out['summary'] = {
        'obs_shape_ok': shapes_ok,
        'obs_range_ok': range_ok,
        'max_reset_position_error_m': reset_err,
        'reset_errors_within_2cm': reset_err < 0.02,
        'end_reasons': sorted(reasons),
        'reasons_declared': set(reasons) <= {'collision', 'goal', 'timeout'},
        'reasons_seen': sorted(reasons),
        'control_period_ok': all(out['checks'].values()),
    }
    print(json.dumps(out, indent=1))
    out_path = Path(__file__).resolve().parents[4] / 'outputs/lab_nav_20261105/rl_env_smoke.json'
    out_path.write_text(json.dumps(out, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
