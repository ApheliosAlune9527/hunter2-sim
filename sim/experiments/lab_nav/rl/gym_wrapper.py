"""Gymnasium adapter around the lab navigation environment.

The environment itself has no third-party dependency; this wrapper only adds the
``spaces`` that a learning library expects, and the goal sampling that decides
what "training" means.  Training goals come from the train split in
``goals.json``; the held-out split is never sampled here, so an evaluation on it
measures generalisation rather than recall.
"""
import json
from pathlib import Path

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from hz_nav_env import HzLabNavEnv

HERE = Path(__file__).resolve().parent


class LabNavGym(gym.Env):
    metadata = {'render_modes': []}

    def __init__(self, split='train', seed=0, episode_s=30.0, fixed_goal=None,
                 nearest=None, reward_variant='progress'):
        super().__init__()
        goals = json.loads((HERE / 'goals.json').read_text())
        self.goals = goals[split]
        if nearest:
            # Restricting the pool to the nearest few goals is a deliberate
            # small-scale experiment: with 40 goals a 76-dim MLP spends its whole
            # budget re-learning "where am I" and never practises arriving.
            self.goals = sorted(self.goals, key=lambda g: g[2])[:int(nearest)]
        self.rng = np.random.default_rng(seed)
        self.env = HzLabNavEnv(seed=seed, episode_s=episode_s,
                               reward_variant=reward_variant)
        self.fixed_goal = fixed_goal
        self.observation_space = spaces.Box(-1.0, 1.0, shape=(76,), dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(2,), dtype=np.float32)
        self._episode_goal = None

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        if self.fixed_goal is not None:
            goal = self.fixed_goal
        elif options and 'goal' in options:
            goal = options['goal']
        else:
            pick = self.goals[int(self.rng.integers(0, len(self.goals)))]
            goal = (pick[0], pick[1])
        self._episode_goal = goal
        obs, info = self.env.reset(goal=goal)
        return obs, info

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        info['episode_goal'] = self._episode_goal
        return obs, reward, terminated, truncated, info

    def close(self):
        self.env.close()
