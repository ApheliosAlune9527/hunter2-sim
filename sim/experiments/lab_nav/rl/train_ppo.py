"""Train a small PPO policy on the lab navigation task.

PPO is a candidate, not a commitment: the point of this stage is that the
interface, the reward and the evaluation exist, and that a policy can be trained
in the same world the baseline was measured in.

Everything that a later reader needs to reproduce the run is written next to the
weights: hyperparameters, seeds, library versions, the goal split, and a copy of
the environment parameters.  A learning curve is written as JSON lines so it can
be plotted without re-running anything.
"""
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import torch
import gymnasium
import stable_baselines3 as sb3
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from gym_wrapper import LabNavGym  # noqa: E402

OUT = ROOT / 'outputs/lab_nav_20261105/rl'


class Curve(BaseCallback):
    def __init__(self, path, dump_every=2048):
        super().__init__()
        self.path = path
        self.dump_every = dump_every
        self.last = 0
        self.episode_returns = []

    def _on_step(self):
        infos = self.locals.get('infos') or []
        for info in infos:
            if 'episode' in info:
                row = {
                    't': int(self.num_timesteps),
                    'return': round(float(info['episode']['r']), 3),
                    'length': int(info['episode']['l']),
                }
                # Why the episode ended matters more than the return: a policy that
                # times out and one that drives into a wall look identical if only
                # the return is kept.
                for key in ('reason', 'contact_proxy', 'final_distance_m'):
                    if key in info:
                        row[key] = info[key]
                self.episode_returns.append(row)
        if self.num_timesteps - self.last >= self.dump_every:
            self.last = self.num_timesteps
            with self.path.open('a', encoding='utf-8') as f:
                for row in self.episode_returns:
                    f.write(json.dumps(row) + '\n')
            self.episode_returns = []
            self.model.save(str(OUT / 'checkpoint'))
        return True


def main():
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 4096
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    episode_s = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0
    nearest = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    reward_variant = sys.argv[5] if len(sys.argv) > 5 else 'progress'
    OUT.mkdir(parents=True, exist_ok=True)
    # One run, one tag: a longer run must never truncate the curve, the metadata or
    # the weights of a shorter one -- that happened once and the shorter curve was
    # lost.  Append mode plus a tag per (seed, budget) keeps every run readable.
    tag = f'seed{seed}_{steps}' + (f'_near{nearest}' if nearest else '')
    if reward_variant != 'progress':
        tag += f'_{reward_variant.split("_")[-1]}'
    curve_path = OUT / f'curve_{tag}.jsonl'
    meta_path = OUT / f'run_meta_{tag}.json'
    model_path = OUT / f'ppo_{tag}'

    env = LabNavGym(split='train', seed=seed, episode_s=episode_s,
                    nearest=nearest or None, reward_variant=reward_variant)
    model = PPO(
        'MlpPolicy', env,
        learning_rate=3e-4, n_steps=512, batch_size=128, n_epochs=10,
        gamma=0.99, gae_lambda=0.95, clip_range=0.2, ent_coef=0.01,
        policy_kwargs={'net_arch': [64, 64]},
        seed=seed, verbose=0, device='cpu',
    )
    meta = {
        'total_timesteps': steps,
        'seed': seed,
        'episode_s': episode_s,
        'train_goals': len(env.goals),
        'reward_variant': reward_variant,
        'train_goal_filter': (f'nearest {nearest} by distance' if nearest
                                 else 'full train split'),
        'control_dt_s': 0.10,
        'observation': '72 min-pooled scan beams / 3 m, goal range / 6 m, goal '
                       'bearing / pi, last v / 0.26, last w / 0.20',
        'action': 'linear velocity [0, 0.26] m/s, yaw rate [-0.20, 0.20] rad/s',
        'reward': '2.0 * progress_m - 0.01 per step - 0.05 * |dv| + 5.0 on goal, '
                  '-5.0 on contact',
        'termination': 'goal within 0.25 m, contact proxy, or 30 simulated seconds',
        'truth_use': 'teleport, success check, contact proxy; the policy input is '
                     'scan and odometry only',
        'library': {'python': platform.python_version(), 'torch': torch.__version__,
                    'gymnasium': gymnasium.__version__, 'sb3': sb3.__version__},
        'started': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    meta_path.write_text(json.dumps(meta, indent=1), encoding='utf-8')

    t0 = time.time()
    model.learn(total_timesteps=steps, callback=Curve(curve_path), progress_bar=False)
    model.save(str(model_path))
    meta['wall_seconds'] = round(time.time() - t0, 1)
    meta['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    meta_path.write_text(json.dumps(meta, indent=1), encoding='utf-8')
    print(json.dumps({'steps': steps, 'wall_seconds': meta['wall_seconds'],
                      'saved': str(model_path) + '.zip'}))


if __name__ == '__main__':
    main()
