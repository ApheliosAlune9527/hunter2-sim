"""Private FAST-LIVO2 session; no chassis or navigation commands."""
import argparse
import copy
import datetime
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import time
from pathlib import Path, PurePosixPath

from pcd_export import sha256_file, validate_pcd_dir

ROOT_TEXT = "/home/car/hz_ws"
ROOT = Path(ROOT_TEXT)
STATE = ROOT / "maps/hz_active_session.json"
MAPPER = ROOT_TEXT + "/install/fast_livo/lib/fast_livo/fastlivo_mapping"
LIDAR = ROOT_TEXT + "/install/hesai_ros_driver/lib/hesai_ros_driver/hesai_ros_driver_node"
IMU = ROOT_TEXT + "/scripts/ch104_imu_pub_legacy.py"
CAMERA = "/home/car/d435i_ws/install/realsense2_camera/lib/realsense2_camera/realsense2_camera_node"


def classify_process(argv, env, uid, expected_uid):
    if uid != expected_uid or env.get("ROS_DOMAIN_ID") != "88" or env.get("ROS_HOME", "").rstrip("/") != ROOT_TEXT + "/.ros" or not argv:
        return None
    if argv[0] == MAPPER:
        return "mapping"
    if argv[0] == LIDAR:
        return "lidar"
    if PurePosixPath(argv[0]).name.startswith("python") and IMU in argv:
        return "imu"
    if any(PurePosixPath(a).name == "ros2" for a in argv[:2]) and any(argv[i:i + 3] == ["launch", "realsense2_camera", "rs_launch.py"] for i in range(len(argv) - 2)):
        return "camera"
    if argv[0] == CAMERA:
        return "camera_child"
    if PurePosixPath(argv[0]).name == "rviz2" and "-d" in argv:
        i = argv.index("-d")
        if i + 1 < len(argv) and argv[i + 1].startswith(ROOT_TEXT + "/"):
            return "rviz"
    return None


def autosave_params(original):
    result = copy.deepcopy(original)
    params = result["/**"]["ros__parameters"]
    params["pcd_save"]["pcd_save_en"] = True
    params["pcd_save"]["interval"] = 1
    return result


def read_process(pid):
    p = Path("/proc") / str(pid)
    try:
        uid = p.stat().st_uid
        argv = [s.decode() for s in (p / "cmdline").read_bytes().split(b"\0") if s]
        env = dict(s.decode().split("=", 1) for s in (p / "environ").read_bytes().split(b"\0") if b"=" in s)
        role = classify_process(argv, env, uid, os.getuid())
        start = (p / "stat").read_text().rsplit(")", 1)[1].split()[19]
        return {"pid": int(pid), "role": role, "start": start, "argv": argv}
    except (OSError, ValueError, UnicodeError, IndexError):
        return None


def processes():
    found = {}
    for p in Path("/proc").iterdir():
        if p.name.isdecimal():
            item = read_process(p.name)
            if item and item["role"]:
                found.setdefault(item["role"], []).append(item)
    if "camera" in found:
        found.pop("camera_child", None)
    for role, items in found.items():
        if len(items) > 1:
            raise RuntimeError(f"发现多个本工作区 {role} 进程，请先人工核对：{items}")
    return {k: v[0] for k, v in found.items()}


def run_dir():
    run = Path(json.loads(STATE.read_text())["run_dir"]).resolve()
    if run.parent != (ROOT / "maps").resolve() or not run.name.startswith("lab_"):
        raise ValueError("运行目录超出私人地图目录")
    return run


def send_int(item):
    current = read_process(item["pid"])
    if not current or current["start"] != item["start"] or current["role"] != item["role"]:
        return
    print(f"发送 SIGINT：{item['role']} PID={item['pid']}", flush=True)
    try:
        if hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"):
            fd = os.pidfd_open(item["pid"])
            try:
                current = read_process(item["pid"])
                if current and current["start"] == item["start"] and current["role"] == item["role"]:
                    signal.pidfd_send_signal(fd, signal.SIGINT)
            finally:
                os.close(fd)
        else:
            os.kill(item["pid"], signal.SIGINT)
    except ProcessLookupError:
        pass


def same_process_alive(item):
    current = read_process(item["pid"])
    return bool(current and current["start"] == item["start"] and current["role"] == item["role"])


def stop():
    found = processes()
    for role in ("rviz", "lidar", "camera", "camera_child", "imu"):
        if role in found:
            send_int(found[role])
    sensors = [v for k, v in found.items() if k != "mapping"]
    deadline = time.monotonic() + 15
    while any(same_process_alive(v) for v in sensors) and time.monotonic() < deadline:
        time.sleep(0.2)
    if any(same_process_alive(v) for v in sensors):
        raise RuntimeError("部分传感器尚未退出。保持建图终端打开，核对 status 后再处理。")
    if "mapping" in found:
        time.sleep(2)
        item = found["mapping"]
        marker = ROOT / "logs/hz_mapping_sigint.json"
        token = {"pid": item["pid"], "start": item["start"], "boot": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}
        previous = json.loads(marker.read_text()) if marker.exists() else None
        if previous != token:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps(token))
            send_int(item)
        deadline = time.monotonic() + 60
        while same_process_alive(item) and time.monotonic() < deadline:
            time.sleep(0.2)
        if same_process_alive(item):
            raise RuntimeError("建图仍未退出，继续等待；工具不会强制终止它。")
    print("相关进程已退出。已写盘的地图文件保留，下一步执行 check / pack。", flush=True)


def trim_rviz(value):
    if isinstance(value, dict):
        for k, v in value.items():
            if k == "Decay Time" and isinstance(v, (int, float)) and v > 5:
                value[k] = 5
            else:
                trim_rviz(v)
    elif isinstance(value, list):
        for v in value:
            trim_rviz(v)


def prepare():
    import yaml
    found = processes()
    if found:
        raise RuntimeError("旧会话仍在运行，请先执行 stop，再 prepare")
    if shutil.disk_usage(ROOT).free < 4 * 1024 ** 3:
        raise RuntimeError("工作区磁盘剩余不足 4 GiB，请先核对空间")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        udp.bind(("0.0.0.0", 2368))
    occupied = subprocess.run(["fuser", "/dev/ch104"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if occupied.returncode == 0:
        raise RuntimeError("/dev/ch104 被其他进程使用，请先核对；不会停止其他工作区进程")
    if not Path("/dev/ch104").exists():
        raise RuntimeError("没有找到 /dev/ch104")
    run = ROOT / "maps" / ("lab_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    run.mkdir(mode=0o700)
    cfg = run / "config"
    cfg.mkdir()
    params = yaml.safe_load((ROOT / "config/xt32_ch104_d435i.yaml").read_text())
    (cfg / "mapping.yaml").write_text(yaml.safe_dump(autosave_params(params), sort_keys=False), encoding="utf-8")
    for source, target in (("camera_d435i_640x480.yaml", "camera.yaml"), ("config.yaml", "hesai.yaml"), ("xt32_firetime.csv", "xt32_firetime.csv")):
        shutil.copyfile(ROOT / "config" / source, cfg / target)
    rviz = yaml.safe_load((ROOT / "config/hz_mapping.rviz").read_text())
    trim_rviz(rviz)
    (cfg / "mapping.rviz").write_text(yaml.safe_dump(rviz, sort_keys=False), encoding="utf-8")
    pcd = ROOT / "src/FAST-LIVO2/Log/PCD"
    if pcd.exists() or pcd.is_symlink():
        if not pcd.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError("旧 PCD 目录指向工作区外，停止准备")
        pcd.rename(run / "previous_PCD")
    (run / "pcd").mkdir()
    try:
        pcd.symlink_to(run / "pcd", target_is_directory=True)
    except Exception:
        if (run / "previous_PCD").exists() or (run / "previous_PCD").is_symlink():
            (run / "previous_PCD").rename(pcd)
        raise
    (ROOT / "logs/ros").mkdir(parents=True, exist_ok=True)
    (ROOT / ".ros").mkdir(exist_ok=True)
    STATE.write_text(json.dumps({"run_dir": str(run)}, indent=2), encoding="utf-8")
    latest = ROOT / "maps/latest_export.json"
    if latest.exists():
        latest.rename(run / "previous_export.json")
    print(f"新一轮目录：{run}\n原 PCD 输出目录保存在：{run / 'previous_PCD'}\n保存设置：interval=1，每次非空输出写一个编号 PCD。\n已创建新配置，原配置保持原样。")


def launch(role):
    run = run_dir()
    cfg = run / "config"
    active = processes()
    if role in active or (role == "camera" and "camera_child" in active):
        raise RuntimeError(f"{role} 已运行，不重复启动")
    commands = {
        "lidar": [LIDAR, "--ros-args", "-p", f"config_path:={cfg / 'hesai.yaml'}"],
        "imu": ["python3", IMU, "--ros-args", "-p", "port:=/dev/ch104", "-p", "baudrate:=115200"],
        "camera": ["ros2", "launch", "realsense2_camera", "rs_launch.py", "camera_namespace:=camera", "camera_name:=camera", "enable_color:=true", "rgb_camera.color_profile:=640x480x15", "enable_depth:=false", "enable_infra1:=false", "enable_infra2:=false", "enable_gyro:=false", "enable_accel:=false", "pointcloud.enable:=false", "align_depth.enable:=false", "initial_reset:=false"],
        "mapping": [MAPPER, "--ros-args", "-r", "__node:=laserMapping", "--params-file", str(cfg / "mapping.yaml"), "--params-file", str(cfg / "camera.yaml")],
        "rviz": ["rviz2", "-d", str(cfg / "mapping.rviz")],
    }
    if role == "mapping" and list((run / "pcd").glob("*.pcd")):
        raise RuntimeError("本轮已有 PCD，不能重启建图覆盖编号文件；先保存并 prepare 新一轮")
    setup_paths = [Path("/opt/ros/humble/setup.bash"), Path("/home/car/d435i_ws/install/local_setup.bash"), ROOT / "install/local_setup.bash"]
    for p in setup_paths:
        if not p.exists():
            raise FileNotFoundError(p)
    env = dict(os.environ, ROS_DOMAIN_ID="88", RMW_IMPLEMENTATION="rmw_fastrtps_cpp", ROS_LOCALHOST_ONLY="0",
               ROS_LOG_DIR=str(ROOT / "logs/ros"), ROS_HOME=str(ROOT / ".ros"), PYTHONDONTWRITEBYTECODE="1")
    print(f"\033]0;hz_ws {role}\007启动 {role}。本终端保持打开；日志：{run / (role + '.log')}。", flush=True)
    if role != "rviz":
        mode = "xb" if role == "mapping" else "ab"
        log = (run / (role + ".log")).open(mode)
        os.dup2(log.fileno(), 1)
        os.dup2(log.fileno(), 2)
        log.close()
    os.chdir(ROOT)
    setup = "\n".join("source '" + str(p) + "' || exit 1" for p in setup_paths) + '\nexec "$@"'
    os.execvpe("bash", ["bash", "-c", setup, "hz-mapping", *commands[role]], env)


def watch():
    run = run_dir()
    while True:
        found = processes()
        mem = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        available = int(mem["MemAvailable"].split()[0]) * 1024
        free_disk = shutil.disk_usage(ROOT).free
        count = sum(1 for _ in (run / "pcd").glob("*.pcd"))
        print(f"可用内存 {available / 1024 ** 3:.1f} GiB | 磁盘剩余 {free_disk / 1024 ** 3:.1f} GiB | 已落盘 PCD {count} | 建图 PID {found.get('mapping', {}).get('pid', '无')}", flush=True)
        if "mapping" not in found or available < 4 * 1024 ** 3 or free_disk < 2 * 1024 ** 3:
            print("停止本轮采集。请用手持遥控器让小车停稳；此工具不控制底盘。", flush=True)
            stop()
            return
        time.sleep(5)


def check():
    if "mapping" in processes():
        raise RuntimeError("建图仍在写文件，先执行 stop 再检查")
    result = validate_pcd_dir(run_dir() / "pcd")
    print(f"结构检查通过：{result['file_count']} 个 PCD，合计 {result['total_points']} 个点。")
    return result


def pack():
    if processes():
        raise RuntimeError("会话仍有进程运行，请先执行 stop")
    run = run_dir()
    result = check()
    (run / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    archive = run.with_name(run.name + ".tar.gz")
    if archive.exists():
        raise FileExistsError(f"归档已存在，不覆盖：{archive}")
    with archive.open("xb") as out, tarfile.open(fileobj=out, mode="w:gz") as tar:
        for part in ("pcd", "config", "validation.json"):
            tar.add(run / part, arcname=run.name + "/" + part)
        for log in run.glob("*.log"):
            tar.add(log, arcname=run.name + "/" + log.name)
    metadata = {"format": "hz_mapping_pcd_v1", "run_name": run.name, "archive_path": str(archive),
                "sha256": sha256_file(archive), "total_points": result["total_points"], "pcd_files": result["file_count"]}
    (ROOT / "maps/latest_export.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="私人建图会话：stop/prepare/启动/watch/check/pack")
    parser.add_argument("action", choices=("status", "stop", "prepare", "lidar", "imu", "camera", "mapping", "rviz", "watch", "check", "pack"))
    args = parser.parse_args()
    if sys.platform != "linux" or socket.gethostname() != "car-NUC15JNKU7X4":
        raise RuntimeError("本工具只能在 car-NUC15JNKU7X4 小车主机运行")
    if args.action == "status":
        print(json.dumps(processes(), ensure_ascii=False, indent=2))
    elif args.action in ("stop", "prepare", "watch", "check", "pack"):
        globals()[args.action]()
    else:
        launch(args.action)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("检查工具已退出。传感器和建图是否仍在运行，请用 status 核对。")
        sys.exit(130)
    except Exception as exc:
        print(f"停止：{exc}", file=sys.stderr)
        sys.exit(1)
