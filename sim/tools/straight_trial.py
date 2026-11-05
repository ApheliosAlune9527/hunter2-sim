"""Coordinate one fixed virtual straight trial; no ROS libraries are used."""
from datetime import datetime
import fcntl
import json
import math
import os
from pathlib import Path
import pwd
import signal
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

from check_control_scene import validate_world
from check_ros_isolation import validate_environment


WORKSPACE = Path("/home/aphelios/hz_sim_ws")
BINARY = WORKSPACE / "tools/gz_trial_transport"


def sim_seconds(snapshot):
    value = snapshot["stats"].get("sim_time", {})
    return int(value.get("sec", 0)) + int(value.get("nsec", 0)) * 1e-9


def inspect_snapshot(snapshot):
    if snapshot["stats"].get("paused") is not True:
        raise ValueError("世界未暂停；本次测试尚未发送速度")
    for name, request_type, response_type in [
        ("control_providers", "ignition.msgs.WorldControl", "ignition.msgs.Boolean"),
        ("sdf_providers", "ignition.msgs.SdfGeneratorConfig", "ignition.msgs.StringMsg"),
    ]:
        providers = snapshot[name]
        if len(providers) != 1:
            raise ValueError("世界服务不存在或提供者不唯一")
        provider = providers[0]
        if (not provider["address"].startswith("tcp://127.0.0.1:") or
                provider["request_type"] != request_type or
                provider["response_type"] != response_type):
            raise ValueError("世界服务地址或消息类型不符合个人仿真要求")
    if (snapshot["control_providers"][0]["process_uuid"] !=
            snapshot["sdf_providers"][0]["process_uuid"]):
        raise ValueError("读取场景和控制服务不是同一仿真进程")
    if snapshot["command_publishers"] != 0:
        raise ValueError("已有速度发布者；不叠加另一个测试")
    root = ET.fromstring(snapshot["sdf"]["data"])
    validate_world(root)
    if not math.isclose(float(root.findtext("world/physics/max_step_size")),
                        0.001, rel_tol=0, abs_tol=1e-12):
        raise ValueError("实际仿真步长不是0.001秒")
    model = root.find("world/model[@name='hz_hunter_core']")
    pose = [float(value) for value in model.findtext("pose", "0 0 0 0 0 0").split()]
    if len(pose) != 6 or not all(math.isfinite(value) for value in pose):
        raise ValueError("未获得有效的车体位姿")
    return pose


def run_trial(client, run=False, previous_report=None):
    before = client.call("snapshot")
    initial_pose = inspect_snapshot(before)
    # Checks must report the same restart requirement as the motion entry.
    if previous_report and previous_report.get("restart_required_after_failure"):
        previous_server = previous_report.get("before", {}).get("control_providers", [{}])[0].get("process_uuid")
        if previous_server == before["control_providers"][0]["process_uuid"]:
            raise ValueError("上次运动测试中断，需先结束你自己的仿真并重新打开，再开始新测试")
    report = {"mode": "straight" if run else "check", "ok": True,
              "before": before, "velocity_published": False,
              "target_speed_m_s": 0.10, "drive_sim_s": 2.0, "stop_sim_s": 1.0}
    if not run:
        return report
    try:
        # These operations have no selectable speed, topic, world or step count.
        # First clear any old target while the world is paused.
        client.call("stop")
        report["velocity_published"] = True
        client.call("speed")
        client.call("step-drive")
        client.call("stop")
        stop_result = client.call("step-stop")
        after = client.call("snapshot")
        final_pose = inspect_snapshot(after)
        report["after"] = after
        dx, dy = final_pose[0] - initial_pose[0], final_pose[1] - initial_pose[1]
        report["longitudinal_distance_m"] = dx * math.cos(initial_pose[5]) + dy * math.sin(initial_pose[5])
        report["lateral_distance_m"] = -dx * math.sin(initial_pose[5]) + dy * math.cos(initial_pose[5])
        report["yaw_change_rad"] = math.atan2(math.sin(final_pose[5] - initial_pose[5]),
                                               math.cos(final_pose[5] - initial_pose[5]))
        report["advanced_sim_s"] = sim_seconds(after) - sim_seconds(before)
        report["final_speed_from_wheel_odom_m_s"] = float(stop_result["odom"]["twist"]["linear"].get("x", 0.0))
        report["final_pose_world_xyz_rpy"] = final_pose
        report["ok"] = (
            math.isclose(report["advanced_sim_s"], 3.0, abs_tol=1e-6) and
            0.15 <= report["longitudinal_distance_m"] <= 0.25 and
            abs(report["lateral_distance_m"]) <= 0.02 and
            abs(report["yaw_change_rad"]) <= 0.03 and
            abs(final_pose[3]) <= 0.05 and abs(final_pose[4]) <= 0.05 and
            abs(report["final_speed_from_wheel_odom_m_s"]) <= 0.01)
        report["restart_required_after_failure"] = False
    except BaseException as error:
        report["ok"] = False
        report["error"] = type(error).__name__ + ": " + str(error)
        # A timed-out multi_step request is never resent. Pending steps may
        # remain after an early pause; require a fresh scene before a retry.
        report["restart_required_after_failure"] = True
    finally:
        cleanup_errors = []
        for operation in ["stop", "pause"]:
            try:
                client.call(operation)
            except BaseException as error:
                cleanup_errors.append(operation + ": " + str(error))
        report["cleanup_errors"] = cleanup_errors
        report["zero_and_pause_requests_succeeded"] = not cleanup_errors
        if cleanup_errors:
            report["ok"] = False
            report["restart_required_after_failure"] = True
    return report


class NativeClient:
    def __init__(self, report_dir):
        self.report_dir = report_dir
        self.calls = 0

    def call(self, operation):
        self.calls += 1
        # Allow the bounded read-only reply handshake as well as the existing
        # 6s state wait, 5s control reply and 22s completion wait. No retry of
        # a mutating request is introduced by this outer deadline.
        result = subprocess.run([str(BINARY), operation], capture_output=True,
                                text=True, timeout=50)
        name = f"{self.calls:02}_{operation}"
        (self.report_dir / (name + ".stdout.txt")).write_text(result.stdout)
        (self.report_dir / (name + ".stderr.txt")).write_text(result.stderr)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Gazebo transport call failed")
        return json.loads(result.stdout)


def main():
    if sys.argv[1:] not in [[], ["--check"]]:
        raise SystemExit("此测试不接受自选速度、话题或仿真参数")
    validate_environment(os.environ, Path("/proc/sys/kernel/osrelease").read_text(),
                         pwd.getpwuid(os.getuid()).pw_name)
    if os.environ.get("IGN_PARTITION") != "hz_sim_aphelios_73" or os.environ.get("IGN_IP") != "127.0.0.1":
        raise SystemExit("只允许个人Gazebo分区与本机公告地址")
    for proc in Path("/proc").iterdir():
        if proc.name.isdigit():
            try:
                command = (proc / "cmdline").read_bytes()
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                continue
            if b"parameter_bridge" in command:
                raise SystemExit("存在ROS/Gazebo桥接进程；本阶段不叠加运动测试")
    reports = WORKSPACE / "reports"
    if reports.resolve() != reports:
        raise SystemExit("报告目录不是预期个人路径")
    with (reports / "virtual_motion.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("已有虚拟运动检查在运行")
        run_dir = reports / (datetime.now().strftime("straight_%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8])
        run_dir.mkdir()
        last_motion = reports / "straight_last_motion.json"
        previous = json.loads(last_motion.read_text()) if last_motion.is_file() else None
        try:
            report = run_trial(NativeClient(run_dir), run=sys.argv[1:] == [], previous_report=previous)
        except (ValueError, RuntimeError, TimeoutError, KeyError) as error:
            report = {"mode": "check", "ok": False, "velocity_published": False,
                      "preflight_refused": True, "error": str(error)}
        report["report_directory"] = str(run_dir)
        (run_dir / "check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        if report["mode"] == "straight":
            last_motion.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print("记录：" + str(run_dir / "check.json"))
        if report.get("preflight_refused"):
            print("测试前检查未通过，未发送速度：" + report["error"])
            print("请先打开个人Gazebo控制场景并保持暂停，再回传结果。")
        elif report["mode"] == "check":
            print("直行测试前检查通过：世界暂停、运行场景与个人控制配置一致；未发送速度。")
        else:
            print("虚拟直行完成。" if report["ok"] else "虚拟直行未通过检查；请回传记录，不重复运行。")
            if "longitudinal_distance_m" in report:
                print(f"前进 {report['longitudinal_distance_m']:.4f} m；侧移 {report['lateral_distance_m']:.4f} m；"
                      f"偏航 {report['yaw_change_rad']:.5f} rad；仿真推进 {report['advanced_sim_s']:.3f} s；"
                      f"末端轮式里程计速度 {report['final_speed_from_wheel_odom_m_s']:.5f} m/s。")
            if report.get("zero_and_pause_requests_succeeded"):
                print("零速度和暂停收尾请求均成功；场景保持暂停。")
            if report.get("error"):
                print(report["error"])
            if report.get("cleanup_errors"):
                print("收尾请求有错误；保持场景暂停并回传：" + str(report["cleanup_errors"]))
        return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
