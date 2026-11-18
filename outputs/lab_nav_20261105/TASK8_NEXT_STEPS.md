# Task 8 - from the platform to a research direction

Written 2026-11-06.  This file is a decision memo, not a result.  It records what
the platform can now be trusted to do, what it cannot, and what each candidate
next step would actually require.  The choice among the candidates needs the
supervisor's direction; nothing here is an instruction to start one.

Every number below comes from a record in this directory and is restated by
`RESULTS.md`, which `make_report.py` generates from those records.

## 1. What the platform is now

| piece | state | evidence |
|---|---|---|
| scene | 11-01 map extruded to 2.4 m walls, 1,589 collision boxes, 0.004 s step | `scene_manifest.json`, `load_check.json` |
| drive | Ackermann steering restored, radius 1.669 m measured from a driven arc | `task2_verification.json` |
| sensors (lean) | one planar scan, 720 beams at 10 Hz, 1.00 real-time | `task6_verification.json` |
| sensors (full) | 32-beam lidar + RGB-D + IMU, 1.00 real-time with a GUI, frames dropped headless | `profile_full_*.json` |
| navigation | Nav2 on the senior's parameters with four documented patches | `nav2_params_diff.json` |
| truth localisation | 9/9 goals, 0.25 m tolerance, collision audited from tracks | `task4_verification.json` |
| AMCL | 9/9 would be the target; measured 7/9, static error 0.0437 m | `task5_verification.json`, `amcl_eval.json` |
| RL | 76-float observation, 2-float action at 10 Hz, four runs | `task7_verification.json` |

The weakest link is not the simulator: it is that a long AMCL run fails and a
short one does not (long_run 2/3 at 5.6 m against 3/3 at 2.4 m).  Any research
that depends on precise localisation inherits that.

## 2. What is known not to work, and why it matters downstream

- **Collisions are still not measured.**  The Contact system loads but never
  advertises its topic in this build; the replacement is a read-only audit of
  stored tracks plus a wheel-odometry-versus-pose proxy inside the RL
  environment.  A paper-quality collision rate needs a source that actually
  reports contacts, which means either a different Gazebo build or a physical
  engine query, and that is a platform change with its own regression cost.
- **The point cloud has no per-point time.**  `/hz_sim/full/lidar/points` carries
  `x y z intensity ring` and nothing else, so a LiDAR-inertial odometry front end
  that de-skews by point time cannot be run honestly on it.  Filling a fake time
  field would produce a working pipeline and a meaningless result.
- **The walls are a 2D assumption.**  Height is a constant, furniture has no
  height, and the unknown region has no geometry at all.  That is adequate for
  planar navigation and not adequate for anything that reasons about vertical
  structure.
- **The RL policy is not a baseline.**  0/9 against Nav2's 9/9 on the same goals.
  The useful part of task 7 is the interface and the negative result about reward
  design, not a policy.

## 3. Candidate directions, with what each one costs

Ordered by how much of the existing platform they reuse.

### A. Localisation robustness (reuses everything)

The question is concrete: why does AMCL fail at 5.6 m and not at 2.4 m?  The
platform already records the estimate, the truth, the scan and the plan per
round.  The work is diagnosis, not construction: compare beam-model likelihood
against the map along the failing runs, check whether the failure is drift,
a stale transform, or a local costmap that has drifted out of agreement with the
scan.

- needs: nothing new to install
- cost: days
- output: either a parameter finding on the senior's configuration or a measured
  statement that the map is the limit
- risk: low, and it makes every later result more trustworthy

### B. Full perception pipeline (LiDAR-inertial odometry, then mapping)

FAST-LIVO2 is the named candidate in the handover.  Before it can run, the
simulator has to produce a point cloud with per-point time and a synchronised IMU
in the same frame conventions.  That is a change to the sensor plugin, not to the
algorithm, and it has to be validated by checking that a known motion produces a
known de-skew.

- needs: reading the FAST-LIVO2 paper and its data-format requirements, then
  checking whether the Fortress lidar plugin can emit per-point time at all
- cost: weeks, and a real chance the answer is "not with this plugin"
- output: a sensor interface, then a mapping baseline for comparisons
- risk: medium; the honest failure mode is a pipeline that runs on fabricated
  timestamps

### C. World models / Verti-WM

The handover lists these as possibilities.  Neither is a small addition to this
platform: both assume an image or video observation stream with enough fidelity
to predict futures, and neither has been read yet in this project.  The rule from
the handover applies: read the paper, the code and the data requirements before
proposing anything.

- needs: papers and their released code, plus a decision about whether the
  laboratory scene can supply the training data they assume
- cost: unknown until read
- output: a proposal, not an implementation
- risk: high if started before the reading

### D. Manipulation / mobile manipulation

Not present on this vehicle: no arm model, no calibrated camera-to-arm transform,
no grasp data.  A simulation-only arm could be added, but it would be a different
platform with a shared map, and its results would not transfer to the real
HUNTER without the hardware.

- needs: the actual arm, or an explicit decision to study a simulated one
- cost: high
- risk: high, and the least connected to what is already verified

### E. Real-vehicle deployment

Everything needed to *check* readiness is read-only and can be done now; every
step that could move the vehicle needs explicit authorisation, one step at a
time, per the handover's rules.  The read-only checklist:

1. Confirm the simulation and the vehicle share no network path: domain 73 for
   simulation, 88 for the vehicle, `ROS_LOCALHOST_ONLY` set in the simulation
   environment.
2. Diff the vehicle's `nav2_params.yaml` against the copy this work derived from,
   so a simulation result is not compared against different parameters.
3. Confirm the vehicle's map is the same file this scenario was built from
   (SHA256 `98bb0c9e…`), because a different map invalidates the goal set.
4. Check that the vehicle's IMU, scan and odometry topic names and rates still
   match the recorded values (100 Hz IMU, ~10 Hz scan).
5. Only after those four: a supervised, low-speed motion test, under separate
   authorisation.

## 4. Recommendation

Do A first.  It is the only candidate that needs no new component, it removes the
largest known weakness in the current results, and its output is a measurement
rather than a promise.  B is the natural second step but should begin with a
one-day feasibility check of the point-cloud time field, because the answer
decides whether the rest of the pipeline is honest.  C and D should not start
before the papers and the hardware question are settled.  E is a checklist until
someone authorises motion.

## 5. Open questions for the supervisor

1. Which of A-E is the intended research direction, and is a paper target already
   fixed?
2. Is the collision-measurement gap acceptable for that direction, or should the
   simulator be changed first?
3. For B: is a LiDAR-inertial odometry contribution expected, or is mapping a
   means to an end?
4. For E: is real-vehicle work in scope this term, and who authorises motion?
