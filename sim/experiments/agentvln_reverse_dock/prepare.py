"""Derive the isolated reversible navigation configuration from the frozen one."""

import copy
import hashlib
import json
import sys
from pathlib import Path

import yaml


HERE = Path(__file__).resolve().parent
VLN = HERE.parent / "agentvln_hunter"
FIX = HERE.parent / "lab_nav_fix_20261106"
WORLD = VLN / "scenes/lab_agentvln_bigfar_straight.sdf"
BRIDGE = VLN / "config/agentvln_bridge.yaml"
MAP = VLN / "config/straight_nav_map/lab_nav_map_fix.yaml"
BASE = FIX / "nav2_params_fix.yaml"


def prepare(out):
    topics = yaml.safe_load(BRIDGE.read_text(encoding="utf-8"))
    outbound = [(t["ros_topic_name"], t["gz_topic_name"], t["direction"]) for t in topics
                if t["direction"] != "GZ_TO_ROS"]
    if outbound != [("/cmd_vel", "/hz_sim/lab/cmd_vel", "ROS_TO_GZ")]:
        raise ValueError("unexpected outbound bridge")
    required = {"/clock", "/scan", "/odom", "/ground_truth",
                *("/hz_sim/agentvln/camera/" + name for name in ("image", "depth_image", "camera_info"))}
    if not required.issubset(t["ros_topic_name"] for t in topics if t["direction"] == "GZ_TO_ROS"):
        raise ValueError("missing camera or motion feedback in bridge")

    params = yaml.safe_load(BASE.read_text(encoding="utf-8"))
    # This episode uses a fixed map. A duplicate delivery must not rebuild AMCL's laser model.
    params["amcl"]["ros__parameters"]["first_map_only"] = True
    costmap = params["global_costmap"]["global_costmap"]
    cost = costmap["ros__parameters"]
    cost["footprint_padding"] = 0.075
    cost["inflation_layer"].update(inflation_radius=0.68, cost_scaling_factor=5.0)
    # Separate process keeps the two Hybrid A* motion models independent.
    forward_costmap = copy.deepcopy(costmap)
    forward_costmap["ros__parameters"]["static_layer"]["map_topic"] = "/map"
    (out / "forward.yaml").write_text(yaml.safe_dump({
        "/forward/planner_server": params["planner_server"],
        "/forward/global_costmap/global_costmap": forward_costmap,
    }, sort_keys=False), encoding="utf-8")

    planner = params["planner_server"]["ros__parameters"]["GridBased"]
    planner.update(motion_model_for_search="REEDS_SHEPP", reverse_penalty=1.0,
                   non_straight_penalty=1.10, tolerance=0.05)
    control = params["controller_server"]["ros__parameters"]
    control["FollowPath"].update(allow_reversing=True, desired_linear_vel=0.12,
                                 min_lookahead_dist=0.24, max_lookahead_dist=0.40,
                                 min_approach_linear_velocity=0.045,
                                 regulated_linear_scaling_min_speed=0.055)
    control["general_goal_checker"].update(xy_goal_tolerance=0.085, yaw_goal_tolerance=0.14)
    control["goal_checker_plugins"].append("shift_goal_checker")
    control["shift_goal_checker"] = dict(plugin="nav2_controller::SimpleGoalChecker",
                                         stateful=False, xy_goal_tolerance=0.105,
                                         yaw_goal_tolerance=3.142)
    smoother = params["velocity_smoother"]["ros__parameters"]
    smoother.update(max_velocity=[0.12, 0.0, 1.0], min_velocity=[-0.12, 0.0, -1.0])
    reverse = out / "nav2_reverse.yaml"
    reverse.write_text(yaml.safe_dump(params, sort_keys=False), encoding="utf-8")
    files = (WORLD, BRIDGE, BASE, MAP, MAP.parent / "lab_nav_map.pgm",
             VLN / "config/target_layout_straight.json", reverse, out / "forward.yaml")
    entry_points = (HERE / "run_episode.bash", *sorted(HERE.glob("*.py")),
                    FIX / "run_nav2_fix.launch.py", FIX / "odom_tf.py", FIX / "run_nav_eval_fix.py",
                    *(VLN / "tools" / name for name in (
                        "run_spawn_vln.py", "run_spawn_observation.py", "run_straight_dock.py",
                        "target_dock.py", "candidate_builder.py", "vlm_smoke.py", "step5_agent.py")))
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (*files, *entry_points)}
    (out / "inputs.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")


if __name__ == "__main__":
    prepare(Path(sys.argv[1]))
