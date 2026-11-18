# lab_nav_fix_20261106 - corrected navigation demo

Independent copy for the A-F correction round described in
`outputs/hunter_agent_handoff_20261105/Nav2仿真配置与评测修正接续Prompt_20261106.md`.
Nothing here overwrites `outputs/lab_nav_20261105` or `sim/experiments/lab_nav`; those
remain as the previous round left them.

Status of every claim, including what is *not* measured, is in
[`../../outputs/lab_nav_fix_20261106/STATUS.md`](../../outputs/lab_nav_fix_20261106/STATUS.md).

## Entry points

```bash
# whole stack, headless (default)
bash sim/experiments/lab_nav_fix_20261106/run_fix_stack.bash

# scene + bridge only, with the Gazebo window (first step of the walkthrough)
GUI=1 STAGE=sim bash sim/experiments/lab_nav_fix_20261106/run_fix_stack.bash

# scene + bridge + localisation + Nav2 + RViz
GUI=1 bash sim/experiments/lab_nav_fix_20261106/run_fix_stack.bash

# AMCL instead of truth localisation
GUI=1 LOCALIZER=amcl bash sim/experiments/lab_nav_fix_20261106/run_fix_stack.bash

# stop exactly what this directory started
bash sim/experiments/lab_nav_fix_20261106/stop_fix_stack.bash
```

`run_fix_stack.bash` starts Gazebo on ROS domain 73 with `ROS_LOCALHOST_ONLY=1`, from
`wsl/hz_sim_env.bash`.  It never touches domain 88, the real vehicle's domain.

## Files

| file | role |
|---|---|
| `run_fix_stack.bash` | start the stack; records each pid with its kernel start time in `$LOG_DIR/processes.tsv` |
| `stop_fix_stack.bash` | stop by registry only, no name matching; reports `stopped / skipped / still_alive` |
| `run_nav2_fix.launch.py` | six Nav2 nodes; names its own parameter file, map and behaviour trees |
| `nav2_params_fix.yaml` | generated, do not hand-edit; source of every value is in the JSON diff |
| `make_nav2_params_fix.py` | derives the parameters from the senior's file and records each edit |
| `compute_footprint.py` | chassis envelope + steered front-wheel sweep -> `footprint_polygon.json` |
| `footprint_case_test.py` | shows a case the old footprint missed (0.60 m obstacle) |
| `check_corridor.py` | spawn to each goal, polygon rotated to heading, against occupied cells |
| `verify_fix_config.py` | reads parameters back from the running nodes; fails if the file was not the one loaded |
| `verify_sim_load.py` | models present and `/clock` advancing, independent of any old load check |
| `truth_localisation.py` | truth mode: `map->odom` from the odometry plugin, `odom->base_link`, `base_link->laser` |
| `odom_tf.py`, `init_pose.py` | AMCL mode: `odom->base_link` from the wheel odometry, initial pose seeding |
| `lab_bridge_fix.yaml` | Gazebo<->ROS topics, ROS side uses the vehicle's names (`/scan`, `/odom`, `/cmd_vel`) |
| `rviz_fix.rviz` | map, scan, local costmap, footprint, plan |
| `metrics.py` | every definition in one place: tolerances, stop criterion, SE(2) drift, verdicts |
| `test_metrics.py` | 18 checks on those definitions, runnable without a simulator |
| `run_nav_eval_fix.py` | repeatable evaluation: reset, goal, truth track, stop check, drift |
| `amcl_eval_fix.py` | AMCL static and 2 m straight accuracy against the truth |
| `plot_nav_eval_fix.py` | map + goals + truth tracks for a run set |
| `write_verification.py` | builds `task_verification.json` from the result files, no typed numbers |

Generated evidence lives in `outputs/lab_nav_fix_20261106/`: `STATUS.md`,
`task_verification.json`, `footprint_polygon.json`, `footprint_sketch.png`,
`footprint_case_test.json`, `corridor_check.json`, `nav2_params_fix_diff.json`,
`verify_fix_config.json`, `sim_load_check.json`, `nav_eval_runs_truth3.json`,
`nav_eval_runs_amcl3.json`, `nav_eval_tracks_truth3.png`, `nav_eval_tracks_amcl3.png`,
`amcl_eval_fix.json`, `仿真导航入门教程.txt` (the beginner walkthrough), and the
`stop_receipt` written by the stop script.

## Results on this configuration

Same three goals as the previous round, three rounds each, 60 simulated seconds of
budget per round, 0.25 m outer position tolerance and 0.35 rad heading tolerance:

| localiser | successes | short_straight | mid_offset | long_run | false successes |
|---|---|---|---|---|---|
| truth | 6/9 (an earlier identical batch: 7/9) | 0/3 | 3/3 | 3/3 | 0 |
| AMCL | 7/9 (earlier: 6/9) | 1/3 | 3/3 | 3/3 | 0 |

`short_straight` is the flaky one in both modes: it is only 2.4 m away but 26 degrees off
the vehicle's heading, and with a 1.669 m turning radius, no reversing and no rotation in
place there is very little room to correct. The other two goals are 3/3 in every batch.
Every successful run also stopped: zero command for a full simulated second with
|v| < 0.01 m/s and |w| < 0.01 rad/s.

Odometer drift, measured as an SE(2) residual against the truth over the whole run, has
a worst sample of 0.14-0.27 m and grows with path length.

AMCL accuracy against the truth (observed only, never fed back):

| test | value | criterion | verdict |
|---|---|---|---|
| static, 12 s | max 0.0462 m | < 0.05 m | passed |
| straight 2.0 m | 0.0896 m, heading 0.017 rad | < 0.15 m | passed |

Collisions remain **not measured** - the contact sensor is attached and bridged but this
build publishes nothing on it, with or without an explicit collision list.

## What this round changed, and why

1. **Footprint** - rebuilt from the model.  `base_link` sits at the rear axle and the
   chassis reaches x=+0.814 m, so with a 0.02 m margin the costmap polygon is
   `[[-0.184,-0.393],[0.834,-0.393],[0.834,0.393],[-0.184,0.393]]` (1.018 x 0.786 m).
   The inherited rectangle stopped at x=0.52 m and left 0.294 m of the nose outside;
   `footprint_case_test.py` keeps a case that fails under the old rectangle.
   The steered front-wheel sweep (|y| to 0.437 m) is computed and kept in
   `footprint_polygon.json` as `swept_wheel_envelope_m`, but it is **not** the costmap
   polygon: its inscribed radius of 0.437 m marked every cell within 0.437 m of a wall
   as lethal and made the 2 m corridor unplannable (measured: the robot's own cell and
   the goal cell both came back as cost 253 in the published costmap).
2. **Planner/controller agreement** - the planner is DUBIN (the controller never
   reverses and never rotates in place), the search radius is 1.669 m from the plugin's
   steering limit, and `allow_unknown` is false because the map has 64,691 unknown
   cells and the task requires them impassable.
3. **Loading** - the launch names the parameter file, the map and the behaviour trees
   itself, and `verify_fix_config.py` reads the values back from the running nodes
   instead of trusting the file.
4. **Stopping** - registry with kernel start times, no `pkill -f` fallback, so a stale
   pattern cannot kill a process this round did not start.

## Round 2 changes (2026-11-07)

| what | where | note |
|---|---|---|
| fail-closed environment | `lab_nav_fix_env.bash` | wrong user, missing `hz_sim_env.bash`, or wrong domain / localhost / RMW / partition returns non-zero |
| fail-closed start | `run_fix_stack.bash` | checks every `source`, `ign`, `ros2`, the world and bridge files; `fail_start()` cleans only the registry then exits 1 |
| forward-only trees | `make_nav2_params_fix.py` | strips `<BackUp>` / `<Spin>` from the copied trees and asserts they are gone |
| no reversing behaviour | same generator | `behavior_plugins: ["wait", "drive_on_heading"]` |
| runtime read-back | `verify_fix_config.py` | 16 checks: planner, controller, behaviour server, both costmaps (footprint + inflation), both tree paths, tree hash, map, scan |
| wheel reach vs footprint | `footprint_scope.py` | wheels stay inside the polygon up to 7.18 deg; 0.4369 m at full lock; 0.444 rad inner-wheel angle |
| dual budget + cancel | `run_nav_eval_fix.py` | `--budget-sim` and `--wall-budget`; cancels, waits for the action to end, records `cancel.ended`; returns 3 if the goal will not end |
| stop from two sources | `run_nav_eval_fix.py` | odometry speeds for a simulated second, plus truth displacement over that same last second |
| stalled-clock proof | `test_watchdog.py` | 7 cases including a frozen simulated clock where only the wall limit can fire |
| record refuses stale receipts | `write_verification.py` | `check_receipt_is_current()` compares receipt mtime, footprint checks and tree hashes before composing the record |

Commands for this round:

```
python3 -B verify_fix_config.py                  # after the stack is up
python3 -B footprint_scope.py                    # offline, needs only the map
python3 -B test_watchdog.py                      # offline
python3 -B run_nav_eval_fix.py --tag mid_ok --goals mid_offset --rounds 1
python3 -B run_nav_eval_fix.py --tag mid_timeout --goals mid_offset --rounds 1 \
        --budget-sim 6 --wall-budget 120
python3 -B write_verification.py                 # compose task_verification.json
```

## Car-matched configuration (2026-11-08)

The user asked for the simulation to run the vehicle's own data, so the default
parameter file is now `nav2_params_carmatch.yaml`: it is
`/home/car/hz_nav_ws/config/nav2_params.yaml` exported from the car, with **seven
lines** changed, all of them listed in `outputs/lab_nav_fix_20261106/nav2_params_carmatch_diff.json`:

* six behaviour-tree paths (the car's own trees, copied next to this file -- they
  still contain the `BackUp` recovery);
* one absolute topic (`/hz_nav/odom` -> `/odom`) because the bridge here publishes
  at the root namespace.

Everything else is the car's: footprint `[[0.52,0.395],[0.52,-0.395],[-0.50,-0.395],[-0.50,0.395]]`,
`allow_unknown: true`, `REEDS_SHEPP`, `minimum_turning_radius 1.6`,
`allow_reversing: true`, `desired_linear_vel 0.10`, `behavior_plugins` with
`backup`/`spin`, and `velocity_smoother` between the controller and the base
exactly as `nav2_bringup` starts it.

Run it with the usual entry point; the earlier corrected variant is still
available via `PARAMS=.../nav2_params_fix.yaml`.

Evidence that the running stack actually loaded these values:
`outputs/lab_nav_fix_20261106/verify_carmatch_config.json` -- 16/16 checks read
back from the live nodes. `behavior_plugins` cannot be checked that way (nav2
resets the parameter to `[]` after creating the plugins), so the four
"Creating behavior plugin ..." log lines are checked instead.

First sanity runs on this configuration (1 round each):

| goal | result | error | sim time |
|---|---|---|---|
| `near_05` (0.29, -0.77) | succeeded | 0.185 m | 3.5 s |
| `mid_offset` (3.185, 1.235) | succeeded | 0.181 m | 38.9 s |

`mid_offset` took 38.9 s against 15 s on the corrected variant, which is what
0.10 m/s instead of 0.25 m/s costs.

Two defects were found and fixed while switching over, both of which silently
prevented any motion: `velocity_smoother` is a lifecycle node and has to be in the
lifecycle manager's `node_names`, and it reads `cmd_vel` while publishing
`cmd_vel_smoothed`, so it needs the same remaps `nav2_bringup` uses.

Known difference left in place on purpose: the car's `inflation_radius: 0.20` is
smaller than the inscribed radius (0.405 m) of the car's own footprint, and nav2
logs that as an error on every start. It is the car's value, so it stays; it means
the costmaps keep much less margin than the footprint implies.
