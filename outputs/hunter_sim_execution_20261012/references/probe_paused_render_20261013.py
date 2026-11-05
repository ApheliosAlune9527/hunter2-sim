"""One-time paused GUI check; never publish velocity or advance physics."""
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid

sys.path.insert(0, "/mnt/f/rob-memory/sim/tools")
from check_ros_isolation import validate_environment

validate_environment(os.environ, Path("/proc/sys/kernel/osrelease").read_text(),
                     pwd.getpwuid(os.getuid()).pw_name)
processes = subprocess.run(["ps", "-u", "aphelios", "-o", "comm=,args="],
                           capture_output=True, text=True, check=True).stdout
for line in processes.splitlines():
    command = line.split(maxsplit=1)[0]
    if command == "ruby" and "ign" in line and "gazebo" in line:
        raise SystemExit("已有个人Gazebo进程；本诊断不启动第二个世界，也不停止已有进程")

token = uuid.uuid4().hex[:10]
report_dir = Path("/mnt/f/rob-memory/outputs/hunter_sim_execution_20261012/"
                  "references/render_checks") / token
report_dir.mkdir(parents=True)
pictures = Path("/home/aphelios/hz_sim_ws/reports") / ("render_check_" + token)
pictures.mkdir()
log = report_dir / "startup.log"
report = {"world": "hz_hunter_control", "gui_engine": "ogre",
          "physics_play_requested": False, "velocity_published": False}

def query(name, arguments):
    result = subprocess.run(["/usr/bin/ign", *arguments], capture_output=True,
                            text=True, timeout=6)
    (report_dir / (name + ".txt")).write_text(result.stdout + result.stderr)
    return result

with log.open("wb") as output:
    process = subprocess.Popen(["bash", "/mnt/f/rob-memory/sim/tools/start_control_scene.bash"],
                               stdout=output, stderr=subprocess.STDOUT,
                               start_new_session=True)
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("兼容渲染启动期间退出；请查看startup.log")
            try:
                stats = query("paused_stats", ["topic", "-e", "-t",
                              "/world/hz_hunter_control/stats", "-n", "1"])
            except subprocess.TimeoutExpired:
                continue
            if re.search(r"paused:\s*true", stats.stdout):
                break
            time.sleep(0.2)
        else:
            raise TimeoutError("未收到世界暂停状态")
        time.sleep(4)
        if process.poll() is not None:
            raise RuntimeError("兼容渲染器加载后进程退出")
        report["paused_stat_received"] = bool(re.search(r"paused:\s*true", stats.stdout))
        if not report["paused_stat_received"]:
            raise RuntimeError("未确认世界暂停；诊断不继续")
        query("screenshot_service_info", ["service", "-i", "-s", "/gui/screenshot"])
        response = query("screenshot_request", ["service", "-s", "/gui/screenshot",
                         "--reqtype", "ignition.msgs.StringMsg",
                         "--reptype", "ignition.msgs.Boolean", "--timeout", "4000",
                         "--req", 'data: "' + str(pictures) + '"'])
        report["screenshot_request_returncode"] = response.returncode
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not list(pictures.glob("*.png")):
            if process.poll() is not None:
                raise RuntimeError("截图期间进程退出")
            time.sleep(0.2)
        images = list(pictures.glob("*.png"))
        report["screenshot_created"] = bool(images)
        if images:
            destination = report_dir / "render.png"
            shutil.copyfile(images[0], destination)
            report["screenshot"] = str(destination)
        report["alive_at_check_end"] = process.poll() is None
    except Exception as error:
        report["error"] = str(error)
    finally:
        # This process group was created here; no existing processes are touched.
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGINT)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
        report["owned_launcher_exit_code"] = process.returncode
        report["owned_test_process_closed"] = process.poll() is not None
        final_log = re.sub(r"\x1b\[[0-9;]*m", "", log.read_text(errors="replace"))
        report["controller_subscription_logged"] = (
            "AckermannSteering subscribing to twist messages on [/hz_sim/cmd_vel]" in final_log)
        report["ogre_renderer_load_logged"] = "Loading plugin [ignition-rendering-ogre]" in final_log
        driver_log = Path("/home/aphelios/.ignition/rendering/ogre.log")
        if driver_log.is_file():
            shutil.copyfile(driver_log, report_dir / "ogre.log")
        report["report_directory"] = str(report_dir)
        (report_dir / "check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False))

if report.get("error"):
    raise SystemExit(1)
