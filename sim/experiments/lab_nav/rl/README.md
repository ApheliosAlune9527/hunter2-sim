# RL environment on the lab navigation scene

A reinforcement-learning interface on the *same* lean stack the navigation
baseline was measured in: same world, same 720-beam scan, same Ackermann model,
same `/cmd_vel` entry point.  A policy that only wins in a different simulator
has not been compared to anything.

## Interface

```
env = HzLabNavEnv(seed=0, goal=(x, y), episode_s=30.0)
env.start()                      # attaches to the running lean stack
obs, info = env.reset(goal=(x, y))
obs, reward, terminated, truncated, info = env.step(action)
env.close()
```

`gym_wrapper.LabNavGym` adds gymnasium spaces for a learning library; the core
environment depends on numpy and rclpy only.

| | |
|---|---|
| observation | 76 floats, all in [-1, 1] |
| action | 2 floats in [-1, 1] |
| control period | 0.1 simulated seconds |
| episode | 30 s while training, 60 s while evaluating |
| success | within 0.25 m of the goal |
| failure | contact, or the time budget |

**Observation.** Beams 0–71 are the scan reduced 10:1 by taking the *minimum* of
each group, so a thin obstacle cannot be averaged away, divided by 3 m and
clipped.  72 is the goal range over 6 m, 73 the goal bearing over pi, 74 and 75
the last commanded velocity and yaw rate.  The scan is the only exteroceptive
input.

**Action.** `v = (a0 + 1) / 2 * 0.26` m/s, so forward only, matching the
baseline's `allow_reversing: false`; `w = a1 * 0.20` rad/s.  The Ackermann
steering limit (0.4 rad, radius 1.669 m) is enforced by the vehicle model, not by
clipping the action, so a policy that asks for a tighter turn simply does not get
one.

**Reward.** `2.0 * progress_metres - 0.01 - 0.05 * |Δv|`, plus `+5.0` on success
and `-5.0` on contact.  Progress is the only dense term, so the policy is paid
for getting closer rather than for looking busy.  The per-step cost makes
dawdling expensive; the smoothness term discourages bang-bang commands the real
vehicle cannot follow.  The weights are a first choice, recorded so a later run
can be compared against them.

## What the policy sees and what it does not

The policy sees the scan and the wheel odometry.  The goal is a fixed map
coordinate; it is turned into an observation using a pose estimate that starts at
the pose read back during reset and then advances on odometry *increments* only.
Odometry drift after that is the policy's problem, exactly as it would be on a
robot that localised once and drove.

Ground truth is used for three things: teleporting, scoring success, and the
contact proxy.  Every step's `info` records that list.  A policy trained or
evaluated this way must never be tabulated next to an AMCL-only run as if the two
saw the same information.

## Contact detection

The Gazebo Contact topic is not published in this build, so contact is inferred
from a disagreement between wheel odometry and the simulated pose: wheels turning
while the vehicle does not move.  Four consecutive control periods of that end
the episode.  The detector was validated by driving into a wall on purpose
(`test_terminations.py`).

## Goals

`goals.py` samples goals from the placeable region, keeping only those with a
free straight corridor at the approach bearing.  The train split and the held-out
split come from the same pool and the same filter; held-out points are at least
0.75 m from every training point, so evaluating on them measures generalisation.
The three fixed evaluation goals are the ones the navigation baseline ran, which
is what makes a comparison possible at all.

## Scripts

| script | what it does |
|---|---|
| `goals.py` | sample train / held-out goals from the placeable region |
| `smoke_env.py` | interface checks: shapes, range, control period, reset readback |
| `test_terminations.py` | prove success and contact actually terminate an episode |
| `probe_contacts.py` | drive into a wall and print what the contact path sees |
| `train_ppo.py` | train PPO, write curve, checkpoints and run metadata |
| `eval_policy.py` | score a policy on the fixed and held-out goals |

## Running it

The lean stack must be up first; the environment does not start it, so that a
crashed experiment cannot silently rebuild the world underneath a comparison.

```
LOCALIZER=truth NAV2=0 bash sim/experiments/lab_nav/run_lab_stack.bash
source sim/experiments/lab_nav/lab_nav_env.bash
source /opt/ros/humble/setup.bash
~/hz_rl_venv/bin/python sim/experiments/lab_nav/rl/train_ppo.py 8192 0
```

The learning stack lives in an isolated virtualenv (`~/hz_rl_venv`) because the
system Python on this machine has no pip and the ROS packages must not be
disturbed: torch 2.14.1+cpu, gymnasium 1.4.0, stable-baselines3 2.9.2.

## What this is not

Three training runs of a few thousand steps each are a functional check, not a
research result.  Any claim about the policy needs many independent seeds and
reported variance; the scripts record seeds and curves so that work can be done
later without re-instrumenting anything.
