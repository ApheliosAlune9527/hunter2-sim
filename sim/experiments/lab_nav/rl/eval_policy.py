"""Judge a trained policy the way the navigation baseline was judged.

A policy that reaches three goals it trained on has shown recall, not
navigation.  This runs

* the three fixed evaluation goals, which the baseline also ran, and
* the held-out goals, which no training episode used,

and reports the same quantities the baseline reported: success, wall-clock and
simulated time, path length, final distance, and how the episode ended.

The policy input is scan plus odometry.  Ground truth is used only to teleport,
to score success and to detect being blocked; that is written into the output so
a policy tested this way is never confused with one that sees truth.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / 'outputs/lab_nav_20261105/rl'
sys.path.insert(0, str(HERE))


def run_episode(env, goal, policy=None, max_steps=650):
    obs, info = env.reset(goal=goal)
    start_truth = list(env._node.truth)
    path = 0.0
    prev = start_truth[:2]
    total = 0.0
    t0 = time.time()
    steps = 0
    while steps < max_steps:
        if policy is None:
            # Not a no-op: action 0 in this space is half speed, straight ahead.
            # A blind constant-speed driver is the honest floor for a policy that
            # is judged on reaching goals.
            action = np.array([0.0, 0.0])
        else:
            action, _ = policy.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        total += reward
        now = env._node.truth
        path += float(np.hypot(now[0] - prev[0], now[1] - prev[1]))
        prev = now[:2]
        steps += 1
        if terminated or truncated:
            break
    end_truth = list(env._node.truth)
    return {
        'goal': list(goal),
        'start': [round(v, 3) for v in start_truth],
        'end': [round(v, 3) for v in end_truth],
        'success': info.get('reason') == 'goal',
        'end_reason': info.get('reason'),
        'final_distance_m': info.get('distance_m'),
        'path_length_m': round(path, 3),
        'sim_seconds': info.get('sim_seconds'),
        'wall_seconds': round(time.time() - t0, 1),
        'steps': steps,
        'return': round(total, 3),
        'contact_proxy': info.get('contact_proxy'),
    }


def main():
    model_path = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / 'ppo_seed0.zip'
    repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    near = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    policy = PPO.load(str(model_path), device='cpu')
    goals = json.loads((HERE / 'goals.json').read_text())

    from hz_nav_env import HzLabNavEnv
    env = HzLabNavEnv(seed=99, episode_s=60.0)
    env.start()
    result = {'model': str(model_path), 'repeats': repeats,
              'policy_input': 'scan + odometry', 'truth_used_for':
              ['teleport', 'success_check', 'contact_proxy'],
              'eval_goals': [], 'held_out_goals': [], 'train_near_goals': [],
              'constant_forward_control': []}
    try:
        for name_goal in goals['eval']:
            for r in range(repeats):
                rec = run_episode(env, (name_goal['x'], name_goal['y']), policy)
                rec['name'] = name_goal['name']
                rec['round'] = r + 1
                result['eval_goals'].append(rec)
        for i, g in enumerate(goals['held_out'][:6]):
            rec = run_episode(env, (g[0], g[1]), policy)
            rec['name'] = f'held_out_{i}'
            result['held_out_goals'].append(rec)
        # Goals the policy was trained on: in-distribution, not a generalisation test.
        near_goals = sorted(goals['train'], key=lambda g: g[2])[:near] if near else []
        for i, g in enumerate(near_goals):
            rec = run_episode(env, (g[0], g[1]), policy)
            rec['name'] = f'train_near_{i}'
            result['train_near_goals'].append(rec)
        # A blind constant-speed driver on one goal: the floor any policy must beat.
        for name_goal in goals['eval'][:1]:
            rec = run_episode(env, (name_goal['x'], name_goal['y']), None, max_steps=300)
            rec['name'] = name_goal['name']
            result['constant_forward_control'].append(rec)
    finally:
        env.close()

    def summarise(rows):
        if not rows:
            return {}
        return {
            'attempts': len(rows),
            'successes': sum(1 for r in rows if r['success']),
            'mean_final_distance_m': round(float(np.mean([r['final_distance_m'] for r in rows])), 3),
            'mean_path_m': round(float(np.mean([r['path_length_m'] for r in rows])), 3),
            'mean_sim_seconds': round(float(np.mean([r['sim_seconds'] for r in rows])), 1),
            'contacts': sum(1 for r in rows if r['contact_proxy']),
        }

    result['summary'] = {
        'eval_goals': summarise(result['eval_goals']),
        'held_out': summarise(result['held_out_goals']),
        'train_near': summarise(result['train_near_goals']),
        'constant_forward': summarise(result['constant_forward_control']),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f'eval_{model_path.stem}.json'
    out.write_text(json.dumps(result, indent=1), encoding='utf-8')
    print(json.dumps(result['summary'], indent=1))
    print('written', out)


if __name__ == '__main__':
    main()
