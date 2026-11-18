"""Run one episode of a policy and print what it does second by second.

The evaluation only reports the final distance, which cannot tell a policy that
hovers near the goal from one that is stuck on an obstacle 0.9 m away.  This
prints the actions and the distance trace so the failure has a shape.
"""
import json
import sys
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from hz_nav_env import HzLabNavEnv  # noqa: E402

OUT = HERE.parents[3] / "outputs/lab_nav_20261105/rl"


def main():
    model_path = Path(sys.argv[1])
    goal_index = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    nearest = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    goals = json.loads((HERE / "goals.json").read_text())
    near = sorted(goals["train"], key=lambda g: g[2])[:nearest]
    goal = (near[goal_index][0], near[goal_index][1])

    policy = PPO.load(str(model_path), device="cpu")
    env = HzLabNavEnv(seed=7, episode_s=60.0)
    env.start()
    trace = []
    try:
        obs, info = env.reset(goal=goal)
        for step in range(650):
            action, _ = policy.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            if step % 5 == 0 or terminated or truncated:
                trace.append({
                    "t": round(info.get("sim_seconds", 0.0), 2),
                    "distance_m": round(float(info.get("distance_m", -1)), 3),
                    "v": round(float((action[0] + 1) / 2 * 0.26), 3),
                    "w": round(float(action[1] * 0.20), 3),
                    "reward": round(float(reward), 3),
                    "contact": bool(info.get("contact_proxy")),
                })
            if terminated or truncated:
                break
    finally:
        env.close()
    print(json.dumps({"goal": goal, "steps": len(trace), "trace": trace}, indent=1))
    (OUT / f"policy_trace_{model_path.stem}_g{goal_index}.json").write_text(
        json.dumps({"goal": goal, "trace": trace}, indent=1))


if __name__ == "__main__":
    main()
