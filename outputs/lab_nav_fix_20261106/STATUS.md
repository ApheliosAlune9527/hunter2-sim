# lab_nav_fix_20261106 - status of the correction round

Started 2026-11-06.  Scope is the A-F correction list in
`outputs/hunter_agent_handoff_20261105/Nav2仿真配置与评测修正接续Prompt_20261106.md`.
Reinforcement learning, reward work and research directions are out of scope this
round.

This file records what was *checked*, with the file and line that was checked, so a
later reader can repeat the check instead of trusting a summary.  Passing claims
from the old round are treated as claims until re-measured here.

## Checks run at handover (2026-11-06)

| check | command / file | result |
|---|---|---|
| frozen scene untouched | `sha256sum sim/scenes/hz_hunter_full.sdf` | `6277c17f…7504e4` matches the handover value |
| map file identity | `sha256sum outputs/lab_nav_20261105/lab_nav_map.pgm` | `98bb0c9e…6ec74f0` matches the handover value |
| old load check really passed? | `outputs/lab_nav_20261105/load_check.json` | **no**: `ok: true` coexists with `sim_time_reached: false` and `Service call to [/gazebo/worlds] timed out` |
| contact source present? | `outputs/lab_nav_20261105/lab_nav_world_drive.sdf:622` | one `ignition-gazebo-contact-system` plugin, **zero** `type="contact"` sensors |
| planner record vs config | `nav2_params.yaml:308` says `REEDS_SHEPP`; `task3_verification.json:9` says `DUBIN` | contradictory; the old record does not describe the old config |
| footprint at handover | `nav2_params.yaml:216,255` | `[[0.52,0.395],[0.52,-0.395],[-0.50,-0.395],[-0.50,0.395]]`, front 0.294 m short of the CAD envelope's 0.814 m |
| controller settings | `nav2_params.yaml:144,145,154,155,188` | `xy_goal_tolerance 0.20`, `yaw_goal_tolerance 0.35`, `use_rotate_to_heading false`, `allow_reversing false`, BT `xy_goal_tolerance 0.25` |
| drift metric correctness | `run_nav_eval.py:237` | `drift = hypot(end-start) - path_len` -- truth chord minus truth path length, not odometry drift |
| stop script safety | `stop_lab_stack.bash:41,45` | falls back to `pgrep`/`pkill -f <pattern>`; can kill processes this session does not own |
| simulation environment | `wsl/hz_sim_env.bash:23-31` | `ROS_DOMAIN_ID=73`, `ROS_LOCALHOST_ONLY=1`, `rmw_cyclonedds_cpp`, `IGN_PARTITION=hz_sim_aphelios_73`; user `aphelios` |

All six problem groups in the prompt are present at handover; none was fixed by the
previous round.  The old 9/9 and 7/9 figures are therefore historical results of
the old configuration, not evidence for the corrected one.

## What replaces the unsafe stop

`sim/experiments/lab_nav_fix_20261106/stop_fix_stack.bash` has no pattern fallback.
It reads a registry of `name, pid, kernel start time, command line`, and before
signalling checks that `/proc/<pid>/stat` field 22 still equals the recorded start
time, which is what distinguishes the process that was started from an unrelated
process that later received the same pid.  A mismatch is reported and skipped, not
killed.

## Minimal fixes done for the operating demo (2026-11-06)

The user asked for the fixes that block an operating demo first, with a short
verification, and for an explicit statement of what is fixed versus still unmeasured.

| item | what changed | evidence |
|---|---|---|
| footprint | rebuilt from the model: chassis envelope plus the steered front-wheel sweep, `[[-0.204,-0.457],[0.854,-0.457],[0.854,0.457],[-0.204,0.457]]`; nose 0.52 → 0.854 m, width ±0.373 → ±0.457 m | `footprint_polygon.json`, `footprint_sketch.png` |
| footprint is used by the planner | both costmaps in the new parameter file, read back from the running nodes | `verify_fix_config.json` (both footprints PASS) |
| the old footprint really did miss | controlled case: obstacle 0.60 m ahead is free under the old rectangle and a collision under the new polygon | `footprint_case_test.json` |
| planner and controller agree | `motion_model_for_search: DUBIN` (was REEDS_SHEPP while the controller is forward-only), `minimum_turning_radius 1.669`, `allow_reversing false`, `use_rotate_to_heading false` | `nav2_params_fix_diff.json`, `verify_fix_config.json` |
| the new config is the one loaded | launch names its own parameter file, map and behaviour trees; values read back from `/planner_server`, `/controller_server` and both costmaps | `verify_fix_config.json` (`overall true`) |
| the scene really runs | models `floor`, `walls`, `hz_hunter_full` present; `/clock` advanced 0.796 s in 0.798 s of wall time in that run | `sim_load_check.json` |
| the map is the expected one | `/map` from map_server: 241 × 465, 0.05 m, origin (-5.09, -4.89) | `verify_fix_config.json` |
| the scan is alive | `/scan` frame `laser`, 720 beams, 691 finite beams | `verify_fix_config.json` |
| the demo corridor fits the bigger footprint | straight lines spawn→each of the three goals, polygon rotated to travel heading, zero overlap with occupied cells | `corridor_check.json` |
| safe stop | registry-based, no name matching | `stop_fix_stack.bash` |

## Still not measured (do not read as passing)

- **Contact events**: the world still has one Contact *system* plugin and zero contact
  *sensors*, so there is still no contact stream.  Collisions remain unmeasured; the
  RL environment's wheel-speed proxy is a proxy, not a contact measurement.
- **Odometry drift**: the old metric computed truth-chord minus truth-path; it has not
  been replaced yet, so no drift number is quoted in this round.
- **Batch evaluation**: no run of the three goals × 3 rounds on the corrected
  configuration yet.  The old 9/9 (truth) and 7/9 (AMCL) were produced by the old
  configuration and say nothing about this one.
- **AMCL on the corrected footprint**: AMCL is wired into the launch but has not been
  re-evaluated here.
- **Wall height and unknown-space geometry**: unchanged assumptions from the previous
  round (2.4 m extruded walls, unknown cells have no geometry).

## Known limits of the fix round itself

- The footprint is the convex hull of chassis and steered wheels, so it is a rectangle
  1.058 × 0.914 m.  It is up to 0.064 m wider than the rear of the vehicle on each
  side; a concave alternative that keeps the rear at ±0.393 m is stored in the JSON
  but not used, because the costmap footprint must be a simple polygon and the
  rectangle is the conservative choice.
- The wheel sweep uses the inner-wheel angle at full lock (0.444 rad), which is wider
  than the plugin's `steering_limit` of 0.4 rad, on purpose: the footprint should
  describe the mechanism, not the current configuration.

## Contact sensor: attempted, still not measured

The corrected world (`lab_nav_world_contact.sdf`) carries a `<sensor type="contact">`
named `chassis_contact` on `base_link`, built by `add_contact_sensors.py`.  It is not
counted as a working collision source, because it never published a message:

| tried | result |
|---|---|
| sensor listing the 12 chassis collisions, vehicle pressed against the wall for 5 s at 0.3 m/s | 0 messages |
| same sensor with `LIST_ALL=1` (no `<contact>` list, watches every collision on the link) | 0 messages |
| reading the Gazebo topic directly (`ign topic -e`, bypassing ROS) | 0 bytes |
| the Contact system's own topic from the previous round | 0 messages |

Two things were learned while trying.  First, Fortress ignores the `<topic>` element of
a contact sensor: the actual topic is
`/world/hz_lab_2d/model/hz_hunter_full/link/base_link/sensor/chassis_contact/contact`,
and the server log confirms the Contact system publishes there.  Second, the vehicle
stops about 3.6 cm short of the wall face at x = 5.635 (map row y = -0.765), so a run
that ends "pressed against the wall" may not have been in contact at all.

Per section D of the correction plan this stays **not_measured** -- it is not written
as 0, and the old "0 collisions" figures stay retracted.  The substitute evidence is
the proxy already used by the RL environment: wheel odometry integrating while the
truth pose does not move over several control periods.  Reproduction:
`contact_probe.py` with the contact world and `lab_bridge_contact.yaml`.

## Metric definitions, written before they are used

`sim/experiments/lab_nav_fix_20261106/metrics.py` holds the definitions this round will
use, and `test_metrics.py` checks them without a simulator (18 checks, all passing):

| quantity | definition |
|---|---|
| position error | straight-line distance between truth and estimate at the final sample |
| heading error | wrapped difference of yaw |
| success | action returned `SUCCEEDED` **and** truth is within 0.25 m and 0.35 rad |
| `truth_disagrees` | the action claimed success but the truth does not agree -- the failure seen on 2026-11-06 when a spinning wheel convinced the controller it had arrived |
| `stopped_short` | inside tolerance, but the action never returned |
| stop | \|v\| < 0.01 m/s and \|w\| < 0.01 rad/s held for 1.0 simulated second; one noisy sample restarts the window |
| drift | odometry motion composed with the inverse of truth motion, aligned at the first sample, reported at the last sample **and** at the worst sample in between |

The last row matters: the old formula was `hypot(end - start) - path_len`. A test case
proves why it had to go -- a vehicle that drives a loop back to its start has
`hypot(end - start) == 0`, so a 20 % scale error reads as zero drift. With the new
definition the same track shows the error at its worst sample.

The evaluator now imports these functions rather than repeating the arithmetic:
`run_nav_eval_fix.py` writes `nav_eval_runs_<tag>.json` with one record per run
(`action_status`, `reported_success`, `success`, `reason`, `final_error_m`,
`heading_error_rad`, `stop`, `drift`, `budget`, and the truth `track`), and
`write_verification.py` composes `task_verification.json` from those files so no number
in the record is typed by hand.

## Results on the corrected configuration (2026-11-07)

Three goals from the earlier round, three rounds each, 60 simulated seconds per round,
outer tolerance 0.25 m / 0.35 rad:

| localiser | successes | short_straight | mid_offset | long_run | false successes |
|---|---|---|---|---|---|
| truth | 6/9 (earlier identical batch 7/9) | 0/3 | 3/3 | 3/3 | 0 |
| AMCL | 7/9 (earlier 6/9) | 1/3 | 3/3 | 3/3 | 0 |

Every success also stopped for a full simulated second under the stop criterion. Worst
SE(2) odometry drift sample per run: 0.14-0.27 m, growing with path length.

AMCL accuracy against the truth (observed only): static 12 s max error **0.0462 m**
(criterion < 0.05, passed); after a 2.0 m straight drive **0.0896 m** and 0.017 rad
(criterion < 0.15, passed).

`short_straight` fails in both modes although it is the closest goal: 2.4 m away but 26
degrees off the heading, and with a 1.669 m turning radius, no reversing and no
rotation in place the correction is not always available. Run-to-run variation within
one configuration is real and is reported rather than averaged away (6/9 and 7/9 for the
same truth configuration on consecutive batches).

Artifacts: `nav_eval_runs_truth3.json`, `nav_eval_runs_amcl3.json`,
`nav_eval_tracks_truth3.png`, `nav_eval_tracks_amcl3.png`, `amcl_eval_fix.json`,
`task_verification.json`.

---

## Round 2 acceptance, 2026-11-07 (four items)

### 1. A failed start exits, and only cleans up what it started

`lab_nav_fix_env.bash` now fails closed: wrong user, missing `hz_sim_env.bash`, or a
domain / localhost / RMW / partition value that is not the isolated simulator's returns
non-zero instead of leaving half an environment behind. `run_fix_stack.bash` checks every
`source`, requires `ign` and `ros2`, requires the world and bridge files to exist, and
routes `/clock` timeout, AMCL init failure and "nav2 never became active" through
`fail_start()`, which calls `stop_fix_stack.bash` (registry only, no name matching) and
then exits 1.

### 2. Footprint re-accepted against the running nodes

The costmap footprint is the chassis plus 0.02 m: `[[-0.184,-0.393],[0.834,-0.393],
[0.834,0.393],[-0.184,0.393]]`, half width **0.3933 m**. The earlier receipt had been
compared against `footprint_polygon_m`, which is the *swept-wheel* rectangle (half width
0.457 m) -- so it recorded a footprint the stack never used. The check now compares the
live value with `chassis_with_margin_m`, states the 1 mm rounding tolerance, and records
`equals_swept_rectangle: false` for both costmaps.

Wheel reach, computed in `footprint_scope.py`: the wheels stay inside the 0.393 m
polygon up to **7.18 deg** of steering and reach **0.4369 m** at the full inner-wheel
angle of 0.444 rad. The planner keeps the rigid body on purpose: a 0.437 m inscribed
radius marks the whole corridor lethal (measured 2026-11-06: start cell and every goal
cell at cost 253, Smac "exceeded maximum iterations"). The demo corridors are straight,
so nothing is left uncovered there: overlaps 0 and clearance above 1 m.

### 3. One forward-only policy

Both trees had `<BackUp backup_dist="0.30" backup_speed="0.05"/>` in the recovery round
robin; both are removed by `make_nav2_params_fix.py` at copy time, with an assertion that
catches a re-copy. `behavior_server.behavior_plugins` no longer advertises `backup` or
`spin` (it is now `["wait", "drive_on_heading"]`), so the behaviour cannot be invoked by
a stale tree or by hand. Runtime read-back confirms the loaded tree paths, the plugin
list, `allow_reversing: false`, `use_rotate_to_heading: false` and DUBIN.

### 4. Timeout that cancels, and proves the stop

`run_nav_eval_fix.py` now has both limits: `--budget-sim` (simulated seconds) and
`--wall-budget` (wall seconds). Whichever fires first, the round cancels the goal, waits
for the action to end, and records `cancel.ended` and the final status; if the goal
cannot be ended the script writes the partial record, stops the session and returns 3
instead of resetting on top of a vehicle that may still be driving. Stop is verified from
both sources: odometry speeds below 0.01 m/s and 0.01 rad/s for a full simulated second,
and the truth displacement measured over that same last second (a coasting tail is not a
failure to stop -- that is the stop happening).

Measured on `mid_offset`:

| case | verdict | action status | cancel | stop |
|---|---|---|---|---|
| normal, 60 s budget | succeeded, error 0.156 m | 4 SUCCEEDED | not used | ok: v 0.00995, w 0.00191, truth 0.0002 m over 1.0 s |
| 6 s budget | timeout_sim_budget, error 2.581 m | 5 CANCELED | requested, 1 goal, ended | ok: v 0.0068, w 0.0005, truth 0.0001 m over 1.0 s |

`test_watchdog.py` (7 cases, all pass) proves the decision logic for the case the
simulator cannot be asked to produce on demand: a frozen simulated clock, where only the
wall limit can fire, plus the inclusive boundary and the note that names which limit hit.

### Still open

Collision contacts remain `not_measured` (this build publishes nothing on the contact
sensor; the proxy stays labelled as a proxy). `short_straight` stays a diagnostic case.

---

## Map load defect found while teaching, 2026-11-07

The walkthrough asked `/map` for its metadata and the numbers did not match the image.
With `free_thresh: 0.25` in the 2026-11-01 YAML, every grey pixel (value 205) has
p = (255-205)/255 = **0.196 < 0.25**, so `mode: trinary` loaded it as **free**:

| source | unknown | free | occupied |
|---|---|---|---|
| PGM pixels | 64,691 | 41,446 | 5,928 |
| `/map` before the fix | **0** | 106,137 | 5,928 |
| `/map` after the fix | 64,691 | 41,446 | 5,928 |

So `allow_unknown: false` was protecting nothing: 57.7 % of the map was advertised as
drivable. The paths we had validated only ever crossed white cells (the corridor audit
says so), which is why the runs succeeded -- but the safety claim was wrong.

Fix: `outputs/lab_nav_fix_20261106/lab_nav_map_fix.yaml` keeps the same image
(sha256 98bb0c9e...6ec74f0) and sets `free_thresh: 0.10`; `run_nav2_fix.launch.py` now
points at it, with the reason written next to the constant. Re-checked on the running
stack: `verify_fix_config.py` 16/16 PASS, and `mid_offset` still reaches the goal
(0.159 m, 16.4 simulated seconds, stopped).

Note for whoever reads the old numbers: 6/9 and 7/9 were measured with the map loaded
without unknown cells. They remain valid as "the planner can do the task", but they are
not evidence that unknown space was respected -- that property only exists after this fix.

---

## Batches re-run on the corrected map, 2026-11-07

The 2026-11-06 batches were measured while `map_server` loaded the grey cells as free
(see the map defect above). These are the same three goals and the same parameters with
the unknown cells actually blocked. Record: `fixmap_eval.json`.

| goal | truth | AMCL | truth mean error | AMCL mean error |
|---|---|---|---|---|
| short_straight (2.42 m, +26 deg) | 0/3 | 1/3 | 0.360 m | 0.116 m |
| mid_offset (3.94 m, +18 deg) | 3/3 | 3/3 | 0.157 m | 0.093 m |
| long_run (5.58 m, +15 deg) | 3/3 | 3/3 | 0.167 m | 0.128 m |
| **totals** | **6/9** | **7/9** | | |

Zero false successes in either mode; every recorded round stopped.

AMCL accuracy on the same map: static error **0.0418 m** (4000 samples, min = max, a
constant bias rather than jitter), and after a 2.001 m straight the estimate ends
**0.0951 m** off with **0.0069 rad** of heading error. Both criteria hold.

What changed and what did not:

- `mid_offset` and `long_run` are unaffected: every round reaches the goal, the errors
  move by millimetres. The corridors they use are white, so blocking grey costs nothing.
- `short_straight` got worse and stays the hard one: 0/3 truth (0/3 pre-fix), 1/3 AMCL.
  With the corner cells now blocked, the planner must respect the 1.669 m turning radius
  instead of cutting through cells that were previously "free", and it ends 0.36 m short.
- One truth round (`short_straight` r2) never ended after cancel; the evaluator wrote the
  partial record and stopped that round set, as designed. It is recorded as a flake in the
  cancel path, not smoothed over.
- Three rounds per goal cannot separate the two localisers; the difference of one round is
  inside the noise band. The claim these numbers support is "both modes do the long
  corridors reliably and both struggle with the near, heading-changing goal", nothing
  finer.

Still open: the drift table for these runs (the per-round values are in the run files),
and collision contacts remain `not_measured`.

---

## Round 3: the unconfirmed cancel, and the tutorial (2026-11-07)

### What the anomalous round actually recorded

`nav_eval_runs_truth_fixmap_all.json`, `short_straight` round 2:
`cancel = {reason: budget_sim, requested: true, acknowledged_goals: 0, ended: false,
final_status: null}`, `action_status = null`, `stop = null`. The cancel was *sent*, the
navigator never acknowledged a goal, no terminal state arrived, and the tool stopped the
batch (exit 3) -- correctly, because a goal that might still be executing must not have
the next reset land on top of it. What it did **not** do was leave any evidence behind:
no stop attempt, no reason for the missing status.

### What changed

| file | change |
|---|---|
| `run_nav_eval_fix.py` | cancel now records `ack_future_done` / `acknowledged` / `acknowledged_goals` / `waited_wall_s` separately, so "no answer" and "answered with no goal" are distinguishable |
| `run_nav_eval_fix.py` | the not-ended branch asks for zero speed and collects whatever stop evidence exists (`max_wait_s=5`), then writes `action_status`, `cancel`, `stop`, `missing_evidence` and the partial track before stopping |
| `run_nav_eval_fix.py` | `_stop_session()` stops the stack through the registry it was started with (`--stack-log-dir`, default `$LOG_DIR`); `--no-stop-on-abort` keeps the old behaviour |
| `run_nav_eval_fix.py` | no `/ground_truth` within 30 s is now a FATAL exit 4 instead of an infinite wait (the usual cause is a shell that never sourced `lab_nav_fix_env.bash`, which is exactly how this was found) |
| `stop_fix_stack.bash` | liveness now ignores zombies: `kill -0` answers "alive" for a process that has already died but not been reaped, which made the script report `still_alive=1` and exit 1 after successfully killing something |
| `collect_fixmap_eval.py` | stop fields are read per run: `stop_recorded` / `stop_ok` / `missing_evidence`, plus `stops_confirmed`, `stops_recorded`, `stops_missing`, `stops_recorded_but_failed`; the old `all_stopped` boolean silently conflated "failed to stop" with "never asked" |
| `test_cancel_paths.py` | new: proves the record and the teardown (below) |
| `run_fix_stack.bash` | `INIT_POSE=manual` leaves AMCL unseeded so the operator sets the starting pose; default stays `auto` |

### Regenerated summary (from the raw run files, not hand-written)

```
truth 6/9, stops confirmed 8/9   (the missing one is short_straight r2: goal_did_not_end)
amcl  7/9, stops confirmed 9/9
amcl accuracy: static 0.0418 m, 2.001 m straight ends 0.0951 m off, heading 0.0069 rad
false successes: 0
```

### The targeted test (`test_cancel_paths.py`, `cancel_path_test.json`)

* record: a synthetic round with `stop: null` is not counted as a confirmed stop and is
  listed in `stops_missing`; a normal round is counted once -- PASS;
* teardown: a registered `sleep` process is killed through the registry,
  `[stop] stopped=1 ... still_alive=0`, exit 0, process gone -- PASS;
* pid reuse: a registry entry with a wrong kernel start time is skipped, the process is
  left alone, and the script still reports it -- PASS;
* `trigger_reproduced_here: false` -- the trigger itself (cancel sent, never answered)
  was seen once in a real batch and is **not** reproduced on demand; the test proves the
  record and the teardown, and the record of the original round stays as evidence.

### Live cancel check

A 5-second budget on `mid_offset` against a live stack exercises the normal path end to
end: cancel acknowledged by the navigator, terminal status 5 (CANCELED), stop verified
from both odometry and truth. Result in `nav_eval_runs_cancel_smoke.json`.

### Tutorial

`outputs/lab_nav_fix_20261106/初学者Nav2仿真操作教程.txt` is now v2 and is a single
continuous run: start, read topics, check the scan, read the map metadata, localise
(truth, or AMCL with a pose the operator sets), check scan-vs-map alignment, send
`mid_offset`, cancel a goal that is still executing while watching both the action
terminal state and the stop evidence, then stop the stack and close the windows. v1's
"stop the stack, then look at topics" ordering is gone, the acceptance numbers are the
fixed-map ones, and the entry points are named.

### Still open

Collision contacts remain `not_measured`. `short_straight` stays a diagnostic case.
The remaining step of this round is the operator's own run-through, which is the
acceptance evidence for the tutorial.

## Round 4: the run-through, executed (2026-11-07)

The operator asked for the run to be carried out here rather than by hand, so the same
sequence the tutorial describes was executed from the shell, with the initial pose
published on /initialpose instead of clicked with 2D Pose Estimate. Everything else is
the tutorial path: start, seed, check the scan against the map, drive a goal, cancel a
moving goal, confirm the stop, stop the stack.

| Step | Result |
|---|---|
| scan versus map | `pose_x=0.327 pose_y=-0.832 pose_yaw=1.571 beams_used=690 on_wall=690 off_wall=0 fraction_on_wall=1.000` |
| AMCL pose (map->base_link) | `- Translation: [-0.212, -0.832, 0.000]` |
| mid_offset, 60 s budget | success=True status=4 error=0.111 m stop=True cancel={'requested': None, 'acknowledged_goals': None, 'ended': None, 'final_status': None} |
| long_run, 6 s budget then cancel | success=False status=5 error=4.507 m stop=True cancel={'requested': True, 'acknowledged_goals': 1, 'ended': True, 'final_status': 5} |

Notes that matter more than the pass marks:

* the first attempt at this same run aborted mid_offset at 0.180 m after 40.8 s with
  status 6, while the second reached it at 0.111 m in 15 s with status 4. Same map,
  same parameters, same seed. AMCL carries a roughly 5 cm offset that the controller
  cannot see, so the last few centimetres are not reproducible run to run. Two runs of
  the same goal are not a success rate; this is one abort and one arrival.
* `check_scan_map.py` first reported 13.5% of beams on walls because it compared beam
  endpoints in the scan frame directly against the map. Through TF it is 100%
  (690/690 within 5 cm of an occupied cell). The tool was wrong, not the laser.
* the cancel branch recorded requested=true, acknowledged_goals=1, ended=true,
  final_status=5, and a stop record; the stack stopped through the registry with
  `stopped=4 skipped=0 still_alive=0`.

Files: `selfrun.json`, `nav_eval_runs_selfrun_mid.json`,
`nav_eval_runs_selfrun_cancel.json`; the runner is
`sim/experiments/lab_nav_fix_20261106/self_run_through.sh`.

## Round 5: the simulation now uses the car's parameters (2026-11-08)

* Default parameter file switched to `nav2_params_carmatch.yaml`, derived from the
  file exported off the car; seven lines differ (six BT paths, one absolute topic).
* `verify_carmatch_config.json`: 16/16 checks pass against the running nodes,
  including old footprint, `allow_unknown: true`, `REEDS_SHEPP` 1.6,
  `allow_reversing: true`, 0.10 m/s and the car's BT.
* Two silent blockers fixed in the launch: velocity_smoother missing from the
  lifecycle manager, and its `cmd_vel`/`cmd_vel_smoothed` remaps.
* Sanity runs: `near_05` succeeded (0.185 m, 3.5 s), `mid_offset` succeeded
  (0.181 m, 38.9 s).
* Not changed on purpose: `inflation_radius 0.20` below the inscribed radius, and
  the 3-5 Hz scan of the physical car -- the simulator keeps its 10 Hz lidar.
