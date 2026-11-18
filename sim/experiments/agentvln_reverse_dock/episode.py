"""Run and audit one isolated AgentVLN episode with reversible terminal docking."""

import base64
import json
import math
import os
from pathlib import Path
import shutil
import sys
from threading import Thread
import time
from types import SimpleNamespace

import numpy as np
import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, Twist
from lifecycle_msgs.msg import State, Transition
from lifecycle_msgs.srv import ChangeState, GetState
from nav2_msgs.action import ComputePathToPose, FollowPath
from nav_msgs.msg import Path as PathMsg
from rcl_interfaces.srv import GetParameters
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor
from rclpy.parameter import parameter_value_to_python
from rclpy.signals import SignalHandlerOptions
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformException, TransformListener

from clearance import FOOTPRINT, SceneClearance, angle
from parking import (BRAKE_GAP, PLAN_GAP, STANDOFF, axes, direction_parts, dock_from_face,
                     docking_path, execute_parking, straight_finish)
from prepare import BRIDGE, FIX, MAP, VLN, WORLD

sys.path[:0] = [str(VLN / "tools"), str(FIX)]
from run_nav_eval_fix import EvalNode, SPAWN, yaw_of
from run_spawn_observation import VIEW_POSES, save_observation
from run_spawn_vln import check_idle, fit_face, visible_pair
from run_straight_dock import LAYOUT, snapshot
from target_dock import DockLocalizer, detect_blue
from vlm_smoke import ask, measure, truth_map


SUCCEEDED = GoalStatus.STATUS_SUCCEEDED
POSE_LIMIT_M = .15
POSE_LIMIT_RAD = .12
# Verified approach checkpoint for this room. It is used after visual selection.
APPROACH = (2.0117, 1.4058, 1.0341)


def guard_session(out):
    expected = {"ROS_DOMAIN_ID": "74", "ROS_LOCALHOST_ONLY": "1",
                "RMW_IMPLEMENTATION": "rmw_cyclonedds_cpp", "IGN_IP": "127.0.0.1", "LOCALIZER": "amcl"}
    partition = os.environ.get("IGN_PARTITION", "")
    if (any(os.environ.get(k) != v for k, v in expected.items())
            or not partition.startswith("hz_agentvln_reverse_")):
        raise RuntimeError("dedicated simulation environment required")
    session = dict(line.split("=", 1) for line in (out / "session.txt").read_text().splitlines())
    if (session["partition"] != partition or session["domain"] != "74" or session["localhost_only"] != "1"
            or session["world"] != str(WORLD) or session["bridge"] != str(BRIDGE)):
        raise RuntimeError("simulator identity did not match this episode")


def pose_message(node, pose):
    x, y, yaw = map(float, pose)
    msg = PoseStamped()
    msg.header.frame_id = "map"
    msg.header.stamp = node.get_clock().now().to_msg()
    msg.pose.position.x, msg.pose.position.y = x, y
    msg.pose.orientation.z, msg.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
    return msg


def displacement(track):
    poses = np.array([row["truth"] for row in track])
    if len(poses) < 2:
        return 0., 0.
    dxy = np.diff(poses[:, :2], axis=0)
    yaw = poses[:-1, 2]
    longitudinal = np.sum(dxy * np.column_stack((np.cos(yaw), np.sin(yaw))), axis=1)
    return float(np.maximum(longitudinal, 0).sum()), float(np.maximum(-longitudinal, 0).sum())


class MotionNode(EvalNode):
    def __init__(self, scene):
        super().__init__("amcl", amcl_init_std=.05, amcl_init_yaw_std=.05)
        self.scene = scene
        self.last_truth_rx = 0.
        self.last_odom_rx = 0.
        self.last_scan_rx = 0.
        self.last_scan_stamp = None
        self.last_tf_age = None
        self.tape = None
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.planner = ActionClient(self, ComputePathToPose, "/compute_path_to_pose")
        self.forward = ActionClient(self, ComputePathToPose, "/forward/compute_path_to_pose")
        self.follower = ActionClient(self, FollowPath, "/follow_path")
        self.create_subscription(LaserScan, "/scan", self._scan_cb, qos_profile_sensor_data)

    def _scan_cb(self, msg):
        self.last_scan_rx = time.monotonic()
        self.last_scan_stamp = msg.header.stamp.sec + msg.header.stamp.nanosec / 1e9

    def feedback_ages(self):
        now = time.monotonic()
        return dict(tf_sim_s=self.last_tf_age,
                    truth_wall_s=now - self.last_truth_rx if self.last_truth_rx else None,
                    odom_wall_s=now - self.last_odom_rx if self.last_odom_rx else None,
                    scan_wall_s=now - self.last_scan_rx if self.last_scan_rx else None,
                    scan_sim_s=self.sim_s() - self.last_scan_stamp if self.last_scan_stamp is not None else None)

    def _truth_cb(self, message):
        super()._truth_cb(message)
        self.last_truth_rx = time.monotonic()
        stamp = message.header.stamp
        seconds = stamp.sec + stamp.nanosec / 1e9
        if self.tape is not None and (not self.tape or seconds - self.tape[-1]["t"] >= .04):
            self.tape.append(dict(t=seconds, truth=self.truth,
                                  odom_v=self.odom[3] if self.odom else None))

    def _odom_cb(self, message):
        super()._odom_cb(message)
        self.last_odom_rx = time.monotonic()

    def wait_until(self, predicate, limit, error):
        deadline = time.monotonic() + limit
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=.025)
            if predicate():
                return
        raise RuntimeError(error)

    def result(self, future, limit, error):
        self.wait_until(future.done, limit, error)
        return future.result()

    def require_active(self, name):
        client = self.create_client(GetState, f"/{name}/get_state")
        if not client.wait_for_service(timeout_sec=12.):
            raise RuntimeError(f"no lifecycle service for {name}")
        deadline = time.monotonic() + 20.
        while time.monotonic() < deadline:
            response = self.result(client.call_async(GetState.Request()), 4., f"no state for {name}")
            if response.current_state.id == State.PRIMARY_STATE_ACTIVE:
                return
            self.spin_wall(.25)
        raise RuntimeError(f"{name} did not activate")

    def ready(self, report):
        self.wait_until(lambda: self.truth is not None and self.odom is not None and self.sim_s() > 0,
                        55., "simulator motion feedback not ready")
        self.require_active("amcl")
        self.seed_at_spawn(report)
        for name in ("planner_server", "controller_server", "velocity_smoother"):
            self.require_active(name)
        # The extra Dubins planner only generates routes. Its process never controls the base.
        client = self.create_client(ChangeState, "/forward/planner_server/change_state")
        if not client.wait_for_service(timeout_sec=10.):
            raise RuntimeError("no lifecycle service for the separate forward planner")
        for transition in (Transition.TRANSITION_CONFIGURE, Transition.TRANSITION_ACTIVATE):
            request = ChangeState.Request(transition=Transition(id=transition))
            if not self.result(client.call_async(request), 20., "forward planner did not respond").success:
                raise RuntimeError("could not activate forward planner")
        self.wait_until(lambda: all(c.server_is_ready() for c in (self.planner, self.forward, self.follower)),
                        10., "navigation actions not ready")
        check_idle(self)
        subs = sorted(e.node_name for e in self.get_subscriptions_info_by_topic("/cmd_vel"))
        pubs = sorted(e.node_name for e in self.get_publishers_info_by_topic("/cmd_vel"))
        report["cmd_vel_graph"] = dict(publishers=pubs, subscribers=subs)
        if (subs != ["ros_gz_bridge"] or "velocity_smoother" not in pubs
                or set(pubs) - {"nav_eval_fix", "velocity_smoother", "behavior_server"}):
            raise RuntimeError("unexpected velocity graph in simulator")
        if "truth_localisation" in self.get_node_names():
            raise RuntimeError("truth TF publisher is present in AMCL run")

    def map_pose(self):
        try:
            stamped = self.buffer.lookup_transform("map", "base_link", rclpy.time.Time())
        except TransformException:
            self.last_tf_age = None
            return None
        stamp = stamped.header.stamp.sec + stamped.header.stamp.nanosec / 1e9
        self.last_tf_age = self.sim_s() - stamp
        if self.last_tf_age > .50:
            return None
        t = stamped.transform
        return np.array([t.translation.x, t.translation.y, yaw_of(t.rotation)])

    def pose_health(self, estimate):
        truth = self.truth
        now = time.monotonic()
        if truth is None or now - self.last_truth_rx > .55:
            return "Gazebo truth feedback went stale", None
        if self.odom is None or now - self.last_odom_rx > .55:
            return "wheel odometry went stale", None
        if estimate is None:
            return "map-to-base_link TF missing or stale", None
        if not np.all(np.isfinite([*estimate, *truth, *self.odom])):
            return "pose or odometry contains a non-finite value", None
        error = dict(xy_m=math.dist(estimate[:2], truth[:2]), yaw_rad=abs(angle(estimate[2] - truth[2])))
        if error["xy_m"] > POSE_LIMIT_M or error["yaw_rad"] > POSE_LIMIT_RAD:
            return f"AMCL drift exceeded limit: {error}", error
        return None, error

    def checked_pose(self):
        self.spin_wall(.18)
        estimate = self.map_pose()
        error, _ = self.pose_health(estimate)
        if error:
            raise RuntimeError(error)
        return estimate

    def seed_at_spawn(self, report):
        self.wait_until(lambda: self.last_scan_stamp is not None
                        and self.buffer.can_transform("odom", "base_link", rclpy.time.Time()),
                        12., "odometry TF and scan not ready at spawn")
        self.spin_wall(.4)
        if math.dist(self.truth[:2], SPAWN[:2]) > .015 or abs(angle(self.truth[2] - SPAWN[2])) > .025:
            raise RuntimeError("world did not start at the original spawn")
        report["start_truth"] = self.truth
        self.reseed_amcl(*SPAWN, repeats=5)
        self.wait_until(lambda: self.map_pose() is not None, 12., "no map TF after initial pose")
        report["start_map_pose"] = self.checked_pose().tolist()
        report["stop_at_spawn"] = self.collect_stop(max_wait_s=6., wall_budget=12.)
        if not report["stop_at_spawn"]["ok"]:
            raise RuntimeError("vehicle did not settle at spawn")

    def compute_plan(self, forward, start, end):
        client = self.forward if forward else self.planner
        request = ComputePathToPose.Goal(start=pose_message(self, start),
                                         goal=pose_message(self, end), planner_id="GridBased", use_start=True)
        handle = self.result(client.send_goal_async(request), 6., "planner did not answer")
        if not handle.accepted:
            return None
        future = handle.get_result_async()
        try:
            reply = self.result(future, 9., "planner did not finish in time")
        except RuntimeError:
            handle.cancel_goal_async()
            raise
        if reply.status != SUCCEEDED or len(reply.result.path.poses) < 2:
            return None
        path = np.array([(p.pose.position.x, p.pose.position.y, yaw_of(p.pose.orientation))
                         for p in reply.result.path.poses])
        keep = np.r_[True, np.linalg.norm(np.diff(path[:, :2], axis=0), axis=1) > 1e-4]
        path = path[keep]
        if len(path) < 2 or math.dist(path[0, :2], start[:2]) > .10:
            return None
        return path

    def drive(self, path, gear, final, camera=None, on_tick=None):
        estimate = self.checked_pose()
        if math.dist(estimate[:2], path[0, :2]) > .105 or abs(angle(estimate[2] - path[0, 2])) > .16:
            raise RuntimeError("path start does not match current AMCL pose")
        message = PathMsg()
        message.poses = [pose_message(self, p) for p in path]
        message.header = message.poses[0].header
        goal = FollowPath.Goal(path=message, controller_id="FollowPath",
                               goal_checker_id="general_goal_checker" if final else "shift_goal_checker")
        handle = self.result(self.follower.send_goal_async(goal), 6., "controller did not answer")
        if not handle.accepted:
            return dict(status=None, reason="path rejected", stop=self.collect_stop(wall_budget=12.))

        result = handle.get_result_async()
        start_sim, start_wall = self.sim_s(), time.monotonic()
        budget = 15 + 22 * np.linalg.norm(np.diff(path[:, :2], axis=0), axis=1).sum()
        brake = None
        cancel = None
        max_error = dict(xy_m=0., yaw_rad=0.)
        executor = SingleThreadedExecutor()
        executor.add_node(self)
        if camera is not None:
            executor.add_node(camera)
        worker = Thread(target=executor.spin, daemon=True)
        worker.start()
        wrong_since = None
        failure_feedback = None
        try:
            while not result.done():
                now = time.monotonic()
                if self.odom[3] * gear < -.02:
                    if wrong_since is None:
                        wrong_since = now
                else:
                    wrong_since = None
                brake, error = self.pose_health(self.map_pose())
                if error:
                    for key in max_error:
                        max_error[key] = max(max_error[key], error[key])
                if brake is None and self.scene.at(self.truth)[0] < BRAKE_GAP:
                    brake = "footprint reached the geometric braking margin"
                if brake is None and wrong_since is not None and now - wrong_since > .35:
                    brake = "controller switched direction inside a segment"
                if brake is None and (self.sim_s() - start_sim > budget or now - start_wall > 2.5 * budget):
                    brake = "motion watchdog"
                if brake:
                    break
                if on_tick:
                    on_tick()
                time.sleep(.02)
        except (RuntimeError, ValueError, KeyboardInterrupt) as error:
            brake = str(error) or "episode interrupted"
        finally:
            if brake:
                failure_feedback = self.feedback_ages()
            if not result.done():
                cancel = handle.cancel_goal_async()
                deadline = time.monotonic() + 8.
                while not result.done() and time.monotonic() < deadline:
                    self.cmd.publish(Twist())
                    time.sleep(.02)
            executor.shutdown()
            worker.join()
            if camera is not None:
                executor.remove_node(camera)
            executor.remove_node(self)
        stop = self.collect_stop(hold_s=1., max_wait_s=8., wall_budget=20.)
        ack = cancel.result() if cancel is not None and cancel.done() else None
        return dict(status=result.result().status if result.done() else None,
                    reason=brake, stop=stop, final_truth=self.truth, max_localization_error=max_error,
                    failure_feedback=failure_feedback,
                    cancel_requested=cancel is not None, cancel_ack=bool(ack and ack.goals_canceling)
                    if cancel is not None else None, seconds=self.sim_s() - start_sim)

    def drive_leg(self, phase, gear, path, length, final, motions, camera=None, on_tick=None):
        print(f"[行驶] {phase} {'前进' if gear == 1 else '倒车'}，规划 {length:.2f} m", flush=True)
        self.tape = []
        try:
            motion = self.drive(path, gear, final, camera, on_tick)
        finally:
            track, self.tape = self.tape, None
        motion.update(phase=phase, gear=gear, plan_length_m=length, path=path.tolist(), track=track)
        motion["forward_m"], motion["reverse_m"] = displacement(track)
        motion["audit"] = self.scene.sweep([s["truth"] for s in track] + [self.truth])
        estimate = self.map_pose()
        motion["final_map_pose"] = estimate.tolist() if estimate is not None else None
        motions.append(motion)
        print(f"[停稳] {phase} 状态 {motion['status']}，停稳 {motion['stop']['ok']}", flush=True)
        if motion["status"] != SUCCEEDED or not motion["stop"]["ok"] or motion["reason"]:
            raise RuntimeError(f"{phase} failed: {motion['status']} {motion['reason']}")
        expected = motion["forward_m"] if gear == 1 else motion["reverse_m"]
        wrong = motion["reverse_m"] if gear == 1 else motion["forward_m"]
        if expected < .13 or wrong > .05 or motion["audit"]["clearance_m"] < BRAKE_GAP:
            raise RuntimeError(f"{phase} direction or clearance check failed")


def runtime_parameters(node):
    expected = {
        "planner_server": {"GridBased.motion_model_for_search": "REEDS_SHEPP",
                           "GridBased.minimum_turning_radius": 1.669, "GridBased.allow_unknown": False},
        "forward/planner_server": {"GridBased.motion_model_for_search": "DUBIN",
                                   "GridBased.minimum_turning_radius": 1.669},
        "controller_server": {"FollowPath.allow_reversing": True, "FollowPath.use_rotate_to_heading": False,
                              "FollowPath.use_collision_detection": True, "FollowPath.desired_linear_vel": .12,
                              "general_goal_checker.xy_goal_tolerance": .085,
                              "shift_goal_checker.xy_goal_tolerance": .105},
        "velocity_smoother": {"max_velocity": [.12, 0., 1.], "min_velocity": [-.12, 0., -1.]},
        "global_costmap/global_costmap": {"footprint_padding": .075, "inflation_layer.inflation_radius": .68},
        "map_server": {"yaml_filename": str(MAP)},
        "amcl": {"use_sim_time": True, "tf_broadcast": True, "first_map_only": True},
    }
    observed = {}
    for name, values in expected.items():
        client = node.create_client(GetParameters, f"/{name}/get_parameters")
        if not client.wait_for_service(timeout_sec=5.):
            raise RuntimeError(f"no parameter service for {name}")
        response = node.result(client.call_async(GetParameters.Request(names=list(values))), 5.,
                               f"no parameter reply from {name}")
        observed[name] = dict(zip(values, (parameter_value_to_python(value) for value in response.values)))
        if observed[name] != values:
            raise RuntimeError(f"runtime parameters for {name} did not match: {observed[name]}")
    return observed


def forward_route(node, start, goal):
    path = node.compute_plan(True, start, goal)
    if path is None or math.dist(path[-1, :2], goal[:2]) > .08:
        return None, None
    parts = direction_parts(path)
    audit = node.scene.sweep([start, *path])
    if len(parts) != 1 or parts[0][0] != 1 or audit["clearance_m"] < PLAN_GAP:
        return None, None
    return parts[0], audit


def observe(node, camera, out, report):
    _, initial = snapshot(camera)
    report["initial_view"] = initial
    print(f"[视觉] 出生点蓝箱候选 {len(initial['candidates'])} 个", flush=True)
    if not visible_pair(initial["candidates"]):
        start = node.checked_pose()
        for view_pose in VIEW_POSES:
            part, audit = forward_route(node, start, view_pose)
            if part:
                break
        else:
            raise RuntimeError("no clear forward observation route")
        report["observation_plan"] = dict(goal=list(view_pose), audit=audit)

        def watch_view():
            frame = camera.frame
            if frame is None or frame["stamp_ns"] <= initial["stamp_ns"] or "first_pair" in report:
                return
            boxes = [{"bbox_xywh": c["bbox"]} for c in detect_blue(frame["rgb"])]
            if visible_pair(boxes):
                report["first_pair"] = dict(stamp_ns=frame["stamp_ns"], truth=node.truth)
                print("[视觉] 驶近时检测到两个蓝箱", flush=True)

        node.drive_leg("观察", *part, False, report["legs"], camera, watch_view)
    frame, view = save_observation(camera, out, report)
    if not visible_pair(view["candidates"]):
        raise RuntimeError("the observation frame does not contain two distinct visible blue boxes")
    node.checked_pose()
    # This pose is retained for the offline label check at the stationary exposure.
    report["observation_truth"] = node.truth
    print("[视觉] 已保存带编号的同步 RGB-D 观测", flush=True)
    return frame, view


def select_box(instruction, frame, view, out, report):
    options = SimpleNamespace(api="llamacpp", model="qwen-vl", port=18081, curl=shutil.which("curl.exe"))
    image = base64.b64encode((out / "observation_numbered.png").read_bytes()).decode("ascii")
    measured = []
    for candidate in view["candidates"]:
        depth, valid = measure(frame["depth"], candidate)
        if depth is None or valid < 400:
            raise RuntimeError("insufficient valid depth for both candidates")
        measured.append(dict(candidate_id=candidate["id"], bbox_xywh=candidate["bbox_xywh"],
                             depth_m=depth, valid_pixels=valid))
    near, far = sorted(measured, key=lambda row: row["depth_m"])
    report["measured_candidates"] = [near, far]
    if far["depth_m"] - near["depth_m"] < .07:
        raise RuntimeError("insufficient depth separation for the selection")

    # Depth order and image side are measured separately. The model resolves the
    # instruction to an image side and candidate ID; neither value is rewritten.
    horizontal = sorted(view["candidates"], key=lambda row: row["u"])
    side = {row["id"]: label for row, label in zip(horizontal, ("left", "right"))}
    prompt = (f"Command: {instruction}\n"
              f"Nearer blue box: image {side[near['candidate_id']]}, number #{near['candidate_id']}, "
              f"measured depth {near['depth_m']:.3f} m.\n"
              f"Farther blue box: image {side[far['candidate_id']]}, number #{far['candidate_id']}, "
              f"measured depth {far['depth_m']:.3f} m.\n"
              "Identify the commanded box in the picture. Respond with its image side and yellow number.")
    ids = sorted(side)
    schema = dict(type="object", properties={"side": dict(type="string", enum=["left", "right"]),
                                             "candidate_id": dict(type="integer", enum=ids)},
                  required=["side", "candidate_id"], additionalProperties=False)
    attempts = report["model_attempts"] = []
    for attempt in range(1, 4):
        try:
            raw, elapsed, timings, model = ask(options, image, prompt, response_schema=schema)
        except RuntimeError as exc:
            attempts.append(dict(attempt=attempt, error=str(exc)))
            transient = any(f"error: {code}" in str(exc) for code in (429, 500, 502, 503, 504))
            if not transient or attempt == 3:
                raise
            print(f"[选箱] 推理服务暂时失败，车辆停稳，重试 {attempt}/2", flush=True)
            time.sleep(.8 * attempt)
        else:
            attempts.append(dict(attempt=attempt, wall_ms=elapsed))
            break
    report["model_decision"] = dict(prompt=prompt, raw=raw, wall_ms=elapsed,
                                    server_timing=timings, model=model)
    decoded = json.loads(raw)
    selected = decoded.get("candidate_id") if isinstance(decoded, dict) else None
    if type(selected) is not int or selected not in ids:
        raise RuntimeError("live VLM did not return a visible candidate ID")
    if decoded.get("side") != side[selected]:
        raise RuntimeError("model image side did not match the selected candidate ID")
    expected = (far if report["farther"] else near)["candidate_id"]
    report["selection_check"] = dict(selected=selected, side=decoded["side"],
                                     expected_by_depth=expected, passed=selected == expected)
    print(f"[选箱] VLM 返回 #{selected}，较近 #{near['candidate_id']} {near['depth_m']:.3f} m，"
          f"较远 #{far['candidate_id']} {far['depth_m']:.3f} m", flush=True)
    if selected != expected:
        raise RuntimeError("model selection disagreed with the measured depth order")
    return next(row for row in view["candidates"] if row["id"] == selected)

def fit_face_stable(camera, frame, view, target, samples=3):
    """Fit the box face on several successive frames and average the estimate.

    A single fit is biased by the part of the face that is actually visible: on
    this scene the estimate lands 0.025-0.074 m towards the camera, which is most
    of the evaluator's lateral budget.  The robot is stationary while this runs,
    so the extra frames are free and the mean sits closer to the true centre.
    """
    fits = [fit_face(frame["rgb"], frame["depth"], view, target)]
    for _ in range(max(0, samples - 1)):
        try:
            f2, v2 = snapshot(camera)
            tf = camera.tf_buffer.lookup_transform("map", f2["info"].header.frame_id, f2["stamp"])
            t, q = tf.transform.translation, tf.transform.rotation
            v2["camera_to_map"] = {"translation": [t.x, t.y, t.z],
                                   "quaternion_xyzw": [q.x, q.y, q.z, q.w]}
            cand = min(v2["candidates"], key=lambda c: math.hypot(c["u"] - target["u"],
                                                                  c["v"] - target["v"]))
            if math.hypot(cand["u"] - target["u"], cand["v"] - target["v"]) > 25:
                continue
            fits.append(fit_face(f2["rgb"], f2["depth"], v2, cand))
        except Exception:
            continue
    centres = np.asarray([f["centre"] for f in fits], dtype=float)
    mean = centres.mean(axis=0)
    sin = sum(math.sin(f["heading"]) for f in fits)
    cos = sum(math.cos(f["heading"]) for f in fits)
    face = dict(fits[0])
    face["centre"] = mean.tolist()
    face["heading"] = math.atan2(sin, cos)
    audit = dict(samples=len(fits),
                 centres=[[round(float(v), 4) for v in c] for c in centres],
                 headings=[round(float(f["heading"]), 4) for f in fits],
                 spread_m=round(float(np.max(np.linalg.norm(centres - mean, axis=1))), 4))
    return face, audit


def evaluate(layout, report, target, truth):
    # Static scene annotations and Gazebo pose are used only by this evaluator.
    observed = dict(report["observation"], robot_pose=report["observation_truth"])
    label = truth_map(observed, layout).get(target["id"])
    if label is None:
        raise RuntimeError("selected box could not be associated in the independent audit")
    box = next(row for row in layout["blue_boxes"] if row["name"] == label)
    heading = round(report["face"]["heading"] / (math.pi / 2)) * (math.pi / 2)
    along, side = axes(heading)
    box_face = np.asarray([box["x"], box["y"]]) - along * (np.abs(along) @ np.asarray(box["size"][:2])) / 2
    offset = box_face - np.asarray(truth[:2])
    heading_error = angle(truth[2] - heading)
    car_axes = np.column_stack(axes(heading_error))
    front = (FOOTPRINT @ car_axes.T)[:, 0].max()
    return dict(box=label, target_correct=label == ("blue_far" if report["farther"] else "blue_near"),
                final_truth=truth, yaw_error_rad=abs(heading_error), lateral_m=abs(float(offset @ side)),
                front_standoff_m=float(offset @ along - front))


def episode(out, instruction, report):
    guard_session(out)
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    rclpy.init(args=["--ros-args", "-p", "use_sim_time:=true"], signal_handler_options=SignalHandlerOptions.NO)
    node = MotionNode(SceneClearance(WORLD))
    camera = DockLocalizer({})
    camera.destroy_publisher(camera.cmd)
    target = None
    try:
        node.ready(report)
        report["runtime_parameters"] = runtime_parameters(node)
        print(f"[指令] {instruction}", flush=True)
        frame, view = observe(node, camera, out, report)
        target = select_box(instruction, frame, view, out, report)
        face, face_audit = fit_face_stable(camera, frame, view, target)
        report["face"] = face
        report["face_samples"] = face_audit
        dock = dock_from_face(face)
        report["measured_dock"] = dock.tolist()
        print(f"[箱面] RGB-D 估计中心 {face['centre']}，朝向 {math.degrees(face['heading']):.2f}°", flush=True)
        start = node.checked_pose()
        if straight_finish(node, start, dock)[0] is None:
            part, audit = forward_route(node, start, APPROACH)
            if part is not None:
                report["approach_plan"] = dict(goal=list(APPROACH), audit=audit)
                node.drive_leg("驶入调整区", *part, False, report["legs"])
        _, forward = docking_path(node, node.checked_pose(), dock, forward=True)
        report["forward_control"] = dict(plan=forward, safe=bool(
            forward and forward["audit"]["clearance_m"] >= PLAN_GAP))
        execute_parking(node, dock, report)
        evaluation = report["evaluation"] = evaluate(layout, report, target, node.truth)
        report["checks"] = {
            "target": evaluation["target_correct"],
            # The face is 0.66 m wide and the car 0.79 m: 0.17 m still leaves the
            # car centred in front of the box, while the wall clearance needs the
            # docking standoff shifted at least ~0.08 m along the face tangent.
            "lateral": evaluation["lateral_m"] <= .17,
            "yaw": evaluation["yaw_error_rad"] <= .13,
            "standoff": .23 <= evaluation["front_standoff_m"] <= .50,
            "stop": report["legs"][-1]["stop"]["ok"],
        }
        if not all(report["checks"].values()):
            raise RuntimeError("final parking did not meet all independent pose checks")
        report["pass"] = True
    except (RuntimeError, ValueError, LookupError, OSError, TransformException, KeyboardInterrupt):
        if node.odom is not None and node.truth is not None:
            report["failure_stop"] = node.collect_stop(max_wait_s=6., wall_budget=12.)
            if target is not None and "face" in report and "evaluation" not in report:
                try:
                    report["stopped_pose_audit"] = evaluate(layout, report, target, node.truth)
                except (RuntimeError, ValueError, LookupError) as exc:
                    report["stopped_pose_audit_error"] = str(exc)
        raise
    finally:
        camera.destroy_node()
        node.destroy_node()
        rclpy.try_shutdown()


def summarize(out, report):
    if report["legs"]:
        report["whole_episode_audit"] = min((leg["audit"] for leg in report["legs"]),
                                            key=lambda row: row["clearance_m"])
    print("\n========== 本轮联合验收 ==========")
    print("总体结果", "通过" if report["pass"] else "未通过")
    for leg in report["legs"]:
        print(f"{leg['phase']}    前进 {leg['forward_m']:.3f} m / 倒车 {leg['reverse_m']:.3f} m / "
              f"停稳 {'通过' if leg['stop']['ok'] else '未通过'}")
    if "whole_episode_audit" in report:
        print(f"最小几何净空    {report['whole_episode_audit']['clearance_m'] * 100:.1f} cm")
    if "evaluation" in report:
        result = report["evaluation"]
        print(f"停车结果    横向 {result['lateral_m'] * 100:.1f} cm / "
              f"朝向 {math.degrees(result['yaw_error_rad']):.1f}° / 箱前 {result['front_standoff_m'] * 100:.1f} cm")
    if report.get("error"):
        print("失败原因", report["error"])
    print("报告", out / "report.json")


def main():
    out, instruction = Path(sys.argv[1]), sys.argv[2]
    farther = any(word in instruction for word in ("较远", "更远"))
    nearer = any(word in instruction for word in ("较近", "更近"))
    if farther == nearer or "蓝箱" not in instruction:
        raise ValueError("specify one distance relation for the blue boxes")
    report = dict(pass_=False, localizer="amcl", instruction=instruction, farther=farther,
                  contact="not_measured", start_from="original_spawn", pose_resets=0,
                  nominal_standoff_m=STANDOFF, planning_gap_m=PLAN_GAP, braking_gap_m=BRAKE_GAP,
                  localization_limits=dict(xy_m=POSE_LIMIT_M, yaw_rad=POSE_LIMIT_RAD),
                  legs=[], parking_plans=[])
    report["pass"] = report.pop("pass_")
    try:
        episode(out, instruction, report)
    except (RuntimeError, ValueError, LookupError, OSError, TransformException, KeyboardInterrupt) as exc:
        report["error"] = str(exc) or "episode interrupted"
    finally:
        summarize(out, report)
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
                                        encoding="utf-8")
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
