# Full HUNTER Fortress scene — offline implementation result

Result: **DONE_WITH_CONCERNS**. The remaining concern is the inherited engineering assumptions for mass, collision proxies and installation calibration. This offline task did not start WSL, ROS, Gazebo, physics, or hardware and did not publish a command.

The scene, GUI and provenance manifest are frozen at the hashes below. Root-coordinated static sensor/ROS evidence is a separate check under `references/full_sensors/84f73c45b8fb/`; it does not change this offline gate's `runtime_verified=false` claim.

## Delivered files

- `sim/tools/build_hunter_full_scene.py`: deterministic local assembly from the reviewed conversion; no conversion or external process is executed.
- `sim/tools/check_hunter_full_scene.py`: strict structural and resource integrity gate, Python standard library only.
- `sim/tools/test_hunter_full_scene.py`: 25 offline acceptance/mutation tests.
- `sim/scenes/hz_hunter_full.sdf`: world/model `hz_hunter_full`, dynamic vehicle at z=0.167 m, 7 physical links, 6 joints, all 7 converted inertias retained, 12 reviewed CAD visuals, primitive collisions only.
- `sim/scenes/hz_hunter_full_gui.config`: separate 8-plugin viewing GUI, OGRE and `start_paused=true`.
- `sim/scenes/hz_hunter_full_manifest.json`: scene/GUI, conversion input/original URDF, source manifest, geometry report and all 12 mesh hashes.

## API and execution

```python
from check_hunter_full_scene import check_scene
report = check_scene(
    scene_path=None,
    gui_path=None,
    manifest_path=None,
    resource_root=None,
)
```

`resource_root` means the repository root (`F:/rob-memory` on Windows or `/mnt/f/rob-memory` on WSL), not the package directory. Omitted paths resolve to the checked-in full scene, GUI and manifest under that root. Explicit paths support offline temporary-file mutation checks. Success returns a JSON-compatible `status=PASS` report. Invalid structure, missing inputs, forbidden resources or a SHA256 mismatch raise `ValueError`. This function does not read a ROS environment, spawn a process or access a network.

The scene's mesh URI prefix remains exactly `file:///mnt/f/rob-memory/sim/hz_hunter_full_description/`; `resource_root` only maps these reviewed resources to the local checkout for hashing. It never permits another URI. The builder offers the same four optional path/root arguments through `build_scene(...)` and verifies its outputs before returning the gate report.

Commands used from the repository root:

```text
python sim/tools/build_hunter_full_scene.py
python sim/tools/check_hunter_full_scene.py
python -m unittest discover -s sim/tools -p test_hunter_full_scene.py -v
```

## Evidence and checks

- `tdd_red.txt`: initial 20 tests fail with assertions explaining that the builder is missing.
- `tdd_hardening_red.txt`: three meaningful failing assertions expose acceptance of hidden world resources, moved static targets, and the missing original/conversion URDF relationship check.
- `tdd_pose_reference_red.txt`: a failing assertion exposes a top-level `relative_to` pose that changes the vehicle's world placement.
- `tdd_camera_pose_red.txt`: the camera pose assertion fails on the original distant view before applying the requested close view.
- `tdd_green.txt`: final **25 tests pass**.
- `check.json`: final machine-readable scene gate, all artifact/input/tool hashes and test result.

Mutation tests rewrite scene/GUI hashes after tampering. Rejections therefore demonstrate structural enforcement rather than rejection solely because the artifact hash changed. Coverage includes injected/duplicate/nested plugins, `/cmd_vel` and old scene topics, missing/extra/duplicate controller parameters, remote/arbitrary local/traversing mesh references, includes/hidden actor resources, missing/wrong-type/wrong-frame/wrong-pose/wrong-rate sensors, changed scan/camera ranges and sizes, zero/nonfinite/non-positive-definite inertia, CAD/invalid-size collisions, joint topology/axis/limit/pose changes, incomplete joint states, GUI engine/pause/plugin changes, shifted environment targets and changed mesh scale. A separate copied resource checkout proves actual changed mesh bytes are rejected.

Sensor poses come from `geometry_report.sensor_carriers` and are independently recomputed through the unchanged original 19-link URDF. RGB-D uses the `camera_link` +X forward pose and explicitly labels messages `hz_sim/full/camera_optical_frame`. The conversion URDF is checked to differ from the original only by removing `preserveFixedJoint` tags. Converted physical links, inertias, joints, collision offsets, CAD placements and fixed frames are compared semantically after independent structural checks.

## GUI framing adjustment

After the root paused-GUI preview, only the viewing camera was brought closer to `1.35 -1.3 1.05 0 0.347 2.238` (front-right view, roughly 1.8 m from the body). GUI and manifest were regenerated. The SDF was generated only into a temporary file, compared byte-for-byte to the frozen scene, and never rewritten. Its original scene hash and the full static sensor evidence therefore still match. All 25 offline tests passed after this update.

## Frozen SHA256

| Artifact/input | SHA256 |
|---|---|
| Scene | `c280d908e20224eea0a52ba9b2d4116fe9c484c8df05c502d1bd113ea9aaa991` |
| GUI | `b4de5b399156c8188458c7c0f7d54cba5d2416a88515a99eb36e7f33f52a66bc` |
| Manifest | `9e1947afb3409a1e293b7e2192d5d8bf506d2980209e594773e8641f0fbe8c89` |
| Converted SDF | `84ac4ef56988c8bedef64bb49c5b37ee8ebe0920104747773e60142856d44734` |
| Conversion URDF copy | `b77e8cff67c4deb3105e4dcb00a731f618f859b2be95455f67b28ea0aa5511d7` |
| Original RSP URDF | `2010c1874b0c2bf1b35696394b4f90f8c7488f3eaade649d7cda19fb196310fe` |
| Source manifest | `ed25683ac9c8acbf42222476afe89cf9fa6f4be984ade673f3dd40563b6fd7f8` |
| Geometry report | `a0f973a6dd0dc88d288863c3aa45592c0dea88ea783e54730e07af5be5cf0e5d` |

No geometry package file or old scene/entry point was edited. No Git commit was created.
