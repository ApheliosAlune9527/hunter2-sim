# Data source notice

Manufacturer split CAD and its original URDF/package metadata come from
https://github.com/agilexrobotics/ugv_gazebo_sim/tree/9d7888affce35321c657c1c8528307f3115b9d41/hunter/hunter2_base . The upstream package.xml license
field is literally `TODO`. No mesh license is invented or asserted here. The
unmodified original package.xml and all nine original STL files remain in the
geometry evidence folder; SHA256 values and exact raw URLs are in source_manifest.json.
This uncertainty remains relevant for any later redistribution.

Upper assembly, XT32, ARS548, G60, and camera appearance/TF come from the existing
local robot export, robot_assets/hunter_from_car_20261013_qjkgbbq5. Camera d435.dae is copied
byte-for-byte, has embedded material colours and has no external texture files.
The local RealSense package.xml declares Apache-2.0; that declaration is preserved
as source evidence and does not resolve the manufacturer's separate CAD license.
The local hunter_description package metadata is also hashed in the manifest.

The camera optical and CH104 data frames use the existing personal FAST-LIVO2
configuration exported on 2026-10-30. The received YAML and source files are
hashed and read as evidence only. Their physical calibration accuracy is not
verified; the source serial publisher and mapping program are never executed.

The new URDF replaces upstream physical parameters and joint conventions. It
does not use or install upstream launch files, Classic plugins, CAN code, drivers,
or the local robot control packages. PIPER and its mounting plate are excluded.
