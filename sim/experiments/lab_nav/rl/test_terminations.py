"""Do the three declared end conditions actually fire?

The smoke test only ever produced timeouts, which proves the clock works but not
that success and collision are detectable.  This drives two deliberate cases:

* success    a goal 1.0 m straight ahead, driven forward until the tolerance
             trips -- the vehicle should stop with the goal reason
* collision  a goal placed beyond the wall, driven straight into it -- the
             contact bridge should report a non-wheel contact

Both use the same environment and the same stack as training.  If either case
fails to terminate, the reward is broken in a way that would silently reward
diving into furniture.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hz_nav_env import HzLabNavEnv  # noqa: E402

OUT = Path(__file__).resolve().parents[4] / 'outputs/lab_nav_20261105/rl_termination_test.json'


def find_wall_approach():
    """A free cell with a wall 1.2 m ahead along +x, and room to stand."""
    import numpy as np
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import placeable_region as P
    pixels, free, origin, res = P.load()
    rows, cols = pixels.shape
    ahead = int(round(1.6 / res))
    for row in range(rows // 2, rows):
        for col in range(30, cols - ahead - 30):
            if not free[row, col]:
                continue
            if free[row, col + ahead]:
                continue
            if not all(free[row + dy, col:col + 16].all() for dy in (-4, 0, 4)):
                continue
            x, y = P.to_world(col, row, origin, res, rows)
            return {'x': round(x, 3), 'y': round(y, 3), 'col': int(col), 'row': int(row)}
    raise RuntimeError('no wall approach found')


def drive(env, goal, action, max_steps=250, start=None):
    if start is None:
        obs, info = env.reset(goal=goal)
    else:
        obs, info = env.reset(goal=goal, pose=(start['x'], start['y'], 0.165, 0.0))
    trace = []
    for _ in range(max_steps):
        obs, reward, terminated, truncated, step_info = env.step(action)
        trace.append({'distance_m': step_info['distance_m'],
                      'truth': step_info['truth'],
                      'reason': step_info['reason']})
        if terminated or truncated:
            return step_info, trace
    return {'reason': 'ran_away'}, trace


def main():
    env = HzLabNavEnv(seed=11)
    env.start()
    result = {}
    try:
        # Success: a point 1.0 m ahead of the spawn along +x.
        goal = (-0.21 + 1.0, -0.77)
        info, trace = drive(env, goal, (0.6, 0.0))
        result['success_case'] = {
            'goal': goal, 'end': info['reason'], 'steps': len(trace),
            'final_distance_m': info['distance_m'],
            'sim_seconds': info['sim_seconds'],
            'passed': info['reason'] == 'goal',
        }
        # Collision: stand 1.2 m from a wall and drive straight at it.
        spot = find_wall_approach()
        env._node.cmd.publish(__import__('geometry_msgs.msg', fromlist=['Twist']).Twist())
        result['wall_approach_pose'] = spot
        info, trace = drive(env, (spot['x'] + 1.2, spot['y']), (1.0, 0.0),
                            start=spot)
        result['collision_case'] = {
            'goal': (spot['x'] + 1.2, spot['y']), 'end': info['reason'], 'steps': len(trace),
            'final_distance_m': info['distance_m'],
            'collisions': info['collisions'][:3],
            'contact_proxy': info.get('contact_proxy'),
            'contact_source': info.get('contact_source'),
            'passed': info['reason'] == 'collision' and bool(info.get('contact_proxy')),
        }
    finally:
        env.close()
    result['both_passed'] = result['success_case']['passed'] and result['collision_case']['passed']
    OUT.write_text(json.dumps(result, indent=1), encoding='utf-8')
    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
