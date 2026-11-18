
# Next session

## Where the work stopped (2026-11-07 evening)

Round 3 (tutorial closing) is done except for the operator's own run-through.

* cancel path: the anomalous round is now fully recorded; an unconfirmed cancel asks for
  zero speed, keeps whatever stop evidence exists, names the missing pieces in
  `missing_evidence`, and stops the batch *and* the session through the process registry;
* `collect_fixmap_eval.py` regenerated the summary from the raw runs: truth 6/9 with
  8/9 stops confirmed, AMCL 7/9 with 9/9, zero false successes;
* `test_cancel_paths.py` passes: record, teardown, pid-reuse refusal; the trigger itself
  is documented as seen-once, not reproduced on demand;
* live cancel check passed end to end (`nav_eval_runs_cancel_smoke.json`: cancel
  acknowledged, status 5, stop ok, stack stopped);
* `初学者Nav2仿真操作教程.txt` is v2: one continuous run, AMCL initial pose set by the
  operator, cancel exercise on a goal that is still executing, fixed-map acceptance data;
* `run_fix_stack.bash` gained `INIT_POSE=manual`; RViz gained the `2D Pose Estimate`
  tool and a `/particle_cloud` display.

## Start here tomorrow

Guided run-through with the operator, one step at a time:

1. PowerShell:
   `wsl.exe -d Ubuntu-22.04 -u aphelios -- env GUI=1 LOCALIZER=amcl INIT_POSE=manual bash /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/run_fix_stack.bash`
2. new WSL shell, `source .../lab_nav_fix_env.bash`
3. topics, scan rate, map metadata
4. RViz 2D Pose Estimate at (-0.21,-0.77) facing +x; check `/amcl_pose` and particles
5. `mid_offset` (3.185, 1.235, yaw 0.5335 -> quaternion z 0.2636 w 0.9646)
6. `long_run` then Ctrl+C while moving; confirm CANCELED and the stop evidence
7. stop the stack, confirm `still_alive=0`, close windows

The operator's actual commands and outputs are the acceptance evidence for the tutorial.

## Still open

collision contacts (`not_measured`), drift table, long-run driving and dynamic mapping.
