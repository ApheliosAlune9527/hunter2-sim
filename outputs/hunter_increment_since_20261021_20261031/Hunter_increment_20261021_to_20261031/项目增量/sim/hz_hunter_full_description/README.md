# HUNTER 2.0 complete geometry description

`urdf/hunter_full.urdf` is a self-contained CAD model named `hz_hunter_full`.
The origin is the rear axle wheel-centre midpoint. X points forward, Y left and Z
up. The four independent continuous wheel joints rotate about +Y. The front
steering joints rotate about +Z with limits ±0.58 rad. Nominal wheelbase is
0.650 m, track is 0.605 m and tire contact radius is 0.165 m.

The manufacturer chassis and four separate real wheel meshes are used. Wheel
zero-pose rotations are baked into metre-unit mesh copies, then each wheel is
recentred on its rolling axis. The source CAD tires have a roughly 0.328 m visual
diameter; the simple contact cylinders use the nominal 0.330 m diameter. Two
duplicate source steering meshes that already contain wheels are omitted. The
small distinct front steering bar and rear axle fitting remain fixed details.

The local assembly and sensor appearance retain the previous exported TF chain
through `reference_base_link`, located at (0.325, 0, -0.165) m in base_link. The
whole old chassis STL and the uninstalled mechanical arm/plate are excluded.
This registration is an engineering alignment, not an extrinsic calibration.

Sensor integration interfaces, in base_link coordinates:

| Carrier | xyz (m) | rpy (rad) | Basis |
| --- | --- | --- | --- |
| hesai_lidar | 0.539, 0, 0.525 | 0, 0, 1.570796326795 | Existing XT32 mount TF |
| camera_link | 0.644, 0.015, 0.475 | 0, 0, 0 | Nominal housing moved with mapping optical origin |
| imu_link | 0.539, -0.110, 0.463 | 0, 0, 1.570796326795 | Existing CH104 mapping settings |
| camera_optical_frame | 0.644, 0.015, 0.475 | -1.570796326795, 0, -1.570796326795 | Existing lidar-to-camera mapping settings |

`camera_link` describes the visual housing mount and has +X forward. Its mount
was translated by (-0.01365, -0.0025, -0.006) m from the exported nominal TF
so the reused optical origin is not trapped inside the Ogre1 camera mesh. This
changes neither the mesh nor its internal housing geometry and is an
engineering registration, not a measured physical camera mounting.
`camera_optical_frame` describes the reused mapping optical origin and has +Z
forward. The RGBD engine is placed at that optical origin with its +X forward.
`imu_link` is the CH104 mapping data frame, rather than the D435i IMU. Its axes
follow the received publisher and mapping parameters. These settings are not
independent proof of physical calibration. These are carriers/TFs; engines belong to the
separate Fortress scene. Fixed-joint preservation hints keep carrier names
available to compatible URDF-to-SDF importers.

The bare chassis target mass is 70 kg. Additional equipment masses, finite frame
proxy masses, box/cylinder inertias, contact friction and simplified collision
shapes are engineering assumptions. Source CAD mass/zero inertias are not copied.
Every retained link has positive mass and a positive definite physically valid
inertia. Detailed allocations, extents, transforms, omitted parts and limitations
are in `geometry_report.json`. Physical dynamics have not been calibrated.

Build and test on Windows using Python only:

    python sim/tools/build_hunter_full_description.py
    python -m unittest discover -s sim/tools -p test_hunter_full_model.py -v

Add `--download` to the builder only if missing pinned source data must be
retrieved. It downloads pure data after validating pinned SHA256 values; it never
starts WSL, a simulator, ROS or hardware. Package resources are installed by the
ament_cmake data package. Licensing/source limitations are in SOURCE_NOTICE.md.
