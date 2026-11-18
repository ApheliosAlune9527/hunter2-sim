#!/usr/bin/env bash
set -u
R=/mnt/d/rob-memory
S=$R/outputs/agentvln_hunter_20261109_slides
mkdir -p "$S"
cp -v "$R/outputs/agentvln_hunter_20261108_step1/camera_verify3/annotated.png"      "$S/p3_camera_verify.png"
cp -v "$R/outputs/agentvln_hunter_20261108_step2/candidate_view/annotated.png"        "$S/p4_candidates.png"
cp -v "$R/outputs/agentvln_hunter_20261108_step3/pipeline_v10/initial.png"            "$S/p6_before_reobserve.png"
cp -v "$R/outputs/agentvln_hunter_20261108_step3/pipeline_v10/reobserve_1.png"        "$S/p6_after_reobserve.png"
cp -v "$R/outputs/agentvln_hunter_20261108_step3/pipeline_v10/annotated.png"          "$S/p5_depth_dock.png"
cp -v "$R/outputs/agentvln_hunter_20261108_vlm_deploy/straight_frame/rgb.png"         "$S/p2_first_view.png"
cp -v "$R/outputs/agentvln_hunter_20261108_vlm_deploy/straight_frame/annotated.png"   "$S/p8_numbered_example.png"
cp -v "$R/outputs/agentvln_reverse_record_20261110_050133/observation_rgb.png"        "$S/p9_observation_rgb.png"
cp -v "$R/outputs/agentvln_reverse_record_20261110_050133/observation_numbered.png"   "$S/p9_observation_numbered.png"
ls -la "$S"
