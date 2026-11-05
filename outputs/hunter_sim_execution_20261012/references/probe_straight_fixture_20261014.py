"""Verify the authorised virtual trial in an independent headless partition."""
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import sys
import time
import uuid

sys.path.insert(0, "/mnt/f/rob-memory/sim/tools")
from check_ros_isolation import validate_environment
from straight_trial import NativeClient, run_trial

validate_environment(os.environ, Path("/proc/sys/kernel/osrelease").read_text(),
                     pwd.getpwuid(os.getuid()).pw_name)
token = uuid.uuid4().hex[:12]
report_dir = Path("/mnt/f/rob-memory/outputs/hunter_sim_execution_20261012/"
                  "references/straight_fixtures") / token
report_dir.mkdir(parents=True)
original_partition = os.environ.get("IGN_PARTITION")
os.environ["IGN_PARTITION"] = "hz_sim_aphelios_73_test_" + token
result = {"partition": os.environ["IGN_PARTITION"], "user_window_targeted": False,
          "headless": True, "real_robot_targeted": False}
with (report_dir / "server.log").open("wb") as output:
    process = subprocess.Popen(["/usr/bin/ign", "gazebo", "-s", "-v", "3",
                                "/mnt/f/rob-memory/sim/scenes/hz_hunter_control.sdf"],
                               stdout=output, stderr=subprocess.STDOUT,
                               start_new_session=True)
    try:
        client = NativeClient(report_dir)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Independent fixture server exited")
            try:
                ready = client.call("snapshot")
                if ready["stats"]["paused"]:
                    break
            except RuntimeError:
                time.sleep(0.3)
        else:
            raise TimeoutError("Independent fixture did not become ready")
        result["trial"] = run_trial(client, run=True)
    except BaseException as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGINT)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
        result["owned_fixture_closed"] = process.poll() is not None
        if original_partition is None:
            os.environ.pop("IGN_PARTITION", None)
        else:
            os.environ["IGN_PARTITION"] = original_partition
        (report_dir / "check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        brief = {key: value for key, value in result.items() if key != "trial"}
        brief["report_directory"] = str(report_dir)
        brief["trial"] = {key: value for key, value in result.get("trial", {}).items()
                          if key not in ["before", "after"]}
        print(json.dumps(brief, ensure_ascii=False))

if result.get("error") or not result.get("trial", {}).get("ok"):
    raise SystemExit(1)
