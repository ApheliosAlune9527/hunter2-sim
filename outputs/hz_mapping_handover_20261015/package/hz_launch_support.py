"""Checks and process descriptions for the private hz_ws launch entry."""
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import sys

ROOT = Path("/home/car/hz_ws")
BUNDLE_NAME = "hz_mapping_tools"
HOSTNAME = "car-NUC15JNKU7X4"
ROLES = ("doctor", "status", "prepare", "lidar", "imu", "camera", "mapping", "rviz", "watch", "stop", "check", "pack", "merge", "preview", "raw")
NODE_ROLES = ("lidar", "imu", "camera", "mapping", "rviz")


class SafetyError(RuntimeError):
    pass


@dataclass
class ProcessSpec:
    cmd: list
    cwd: Path
    log_path: object = None
    exclusive_log: bool = False


def private_root(root=ROOT):
    root = Path(root).absolute()
    if not root.is_dir() or root.is_symlink() or root.resolve() != root:
        raise SafetyError(f"个人工作区必须是实际目录，不能是外部链接：{root}")
    return root


def private_path(root, path, *, exists=False):
    root = private_root(root)
    path = Path(path).absolute()
    if not path.resolve().is_relative_to(root):
        raise SafetyError(f"路径超出个人工作区：{path}")
    if exists and not path.exists():
        raise SafetyError(f"缺少文件或目录：{path}")
    return path


def active_run(root=ROOT):
    root = private_root(root)
    maps = private_path(root, root / "maps", exists=True)
    state = private_path(root, maps / "hz_active_session.json", exists=True)
    if maps.is_symlink() or state.is_symlink():
        raise SafetyError("地图目录或状态文件不能是链接")
    try:
        run = Path(json.loads(state.read_text(encoding="utf-8"))["run_dir"])
    except (ValueError, KeyError, TypeError) as exc:
        raise SafetyError("活动状态文件格式错误；先核对本轮目录") from exc
    if not run.is_absolute():
        raise SafetyError("本轮目录必须使用绝对路径")
    if run.parent != maps or not re.fullmatch(r"lab_\d{8}_\d{6}_\d{6}", run.name):
        raise SafetyError(f"本轮目录超出个人地图目录或名称异常：{run}")
    private_path(root, run, exists=True)
    if run.is_symlink() or run.resolve() != run or not run.is_dir():
        raise SafetyError("本轮目录不能是链接或其他文件")
    for part in ("pcd", "config"):
        path = private_path(root, run / part, exists=True)
        if path.is_symlink() or not path.is_dir():
            raise SafetyError(f"本轮 {part} 目录异常")
    return run


def read_mapping_params(root, run):
    import yaml
    path = private_path(root, run / "config/mapping.yaml", exists=True)
    try:
        params = yaml.safe_load(path.read_text(encoding="utf-8"))["/**"]["ros__parameters"]
        saving = params["pcd_save"]
        if saving.get("pcd_save_en") is not True:
            raise SafetyError("本轮 pcd_save_en 必须为 true；请 prepare 新一轮")
        if type(saving.get("interval")) is not int or saving["interval"] != 1:
            raise SafetyError("本轮 pcd_save.interval 必须为整数 1；请 prepare 新一轮")
        expected = {"lid_topic": "/lidar_points", "imu_topic": "/imu/data", "img_topic": "/camera/camera/color/image_raw"}
        for key, value in expected.items():
            if params["common"].get(key) != value:
                raise SafetyError(f"本轮话题 {key} 应为 {value}")
        return params
    except (KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        raise SafetyError(f"本轮 mapping.yaml 格式异常：{path}") from exc


def build_spec(role, root=ROOT, bundle=None, active=None):
    if role not in ROLES:
        raise SafetyError(f"未知 role：{role}")
    root = private_root(root)
    bundle = private_path(root, bundle or root / BUNDLE_NAME, exists=True)
    active = active or {}
    helper = private_path(root, root / "scripts/hz_mapping_session.py", exists=True)
    if role == "doctor":
        return ProcessSpec(["python3", "-u", "-B", str(bundle / "hz_diagnose.py")], root)
    if role in ("status", "prepare", "watch", "stop", "check", "pack"):
        if role in ("prepare", "pack") and active:
            raise SafetyError("个人会话仍在运行，请先 stop 并确认退出")
        if role == "prepare":
            for part in ("maps", "logs", ".ros", "config", "src/FAST-LIVO2/Log"):
                private_path(root, root / part)
            output = root / "src/FAST-LIVO2/Log/PCD"
            if output.exists() or output.is_symlink():
                private_path(root, output)
        if role in ("watch", "check", "pack"):
            active_run(root)
        return ProcessSpec(["python3", "-u", "-B", str(helper), role], root)
    run = active_run(root)
    cfg = run / "config"
    if role in NODE_ROLES:
        if role in active or (role == "camera" and "camera_child" in active):
            raise SafetyError(f"{role} 已运行，不重复启动")
        log = private_path(root, run / (role + ".log"))
        if log.is_symlink():
            raise SafetyError(f"日志不能是链接：{log}")
        if role == "mapping":
            missing = [name for name in ("lidar", "imu", "camera") if name not in active and not (name == "camera" and "camera_child" in active)]
            if missing:
                raise SafetyError("传感器尚未启动：" + ", ".join(missing))
            output = private_path(root, root / "src/FAST-LIVO2/Log/PCD", exists=True)
            if not output.is_symlink() or output.resolve() != (run / "pcd").resolve():
                raise SafetyError("PCD 输出链接与活动目录不一致；停止后 prepare 新一轮")
            if any((run / "pcd").iterdir()):
                raise SafetyError("本轮已有 PCD 或其他文件，不重启建图覆盖编号；先保存并 prepare 新一轮")
            if log.exists():
                raise SafetyError("本轮已有 mapping.log，不能再次启动；请 prepare 新一轮")
            read_mapping_params(root, run)
        commands = {
            "lidar": [str(root / "install/hesai_ros_driver/lib/hesai_ros_driver/hesai_ros_driver_node"), "--ros-args", "-p", f"config_path:={cfg / 'hesai.yaml'}"],
            "imu": ["python3", "-u", "-B", str(root / "scripts/ch104_imu_pub_legacy.py"), "--ros-args", "-p", "port:=/dev/ch104", "-p", "baudrate:=115200"],
            "camera": ["ros2", "launch", "realsense2_camera", "rs_launch.py", "camera_namespace:=camera", "camera_name:=camera", "enable_color:=true", "rgb_camera.color_profile:=640x480x15", "enable_depth:=false", "enable_infra1:=false", "enable_infra2:=false", "enable_gyro:=false", "enable_accel:=false", "pointcloud.enable:=false", "align_depth.enable:=false", "initial_reset:=false"],
            "mapping": [str(root / "install/fast_livo/lib/fast_livo/fastlivo_mapping"), "--ros-args", "-r", "__node:=laserMapping", "--params-file", str(cfg / "mapping.yaml"), "--params-file", str(cfg / "camera.yaml")],
            "rviz": ["rviz2", "-d", str(cfg / "mapping.rviz")],
        }
        required = {"lidar": ("hesai.yaml",), "mapping": ("mapping.yaml", "camera.yaml"), "rviz": ("mapping.rviz",)}
        for name in required.get(role, ()):
            private_path(root, cfg / name, exists=True)
        if role in ("lidar", "mapping"):
            private_path(root, Path(commands[role][0]), exists=True)
        elif role == "imu":
            private_path(root, root / "scripts/ch104_imu_pub_legacy.py", exists=True)
        return ProcessSpec(commands[role], root, log, role == "mapping")
    if role == "merge":
        if active:
            raise SafetyError("合并前请停止个人会话（stop），确认本轮进程全部退出")
        output = private_path(root, run / "merged")
        if output.exists() or output.is_symlink():
            raise SafetyError(f"合并目录已存在，不覆盖：{output}")
        exporter = private_path(root, root / "scripts/pcd_export.py", exists=True)
        return ProcessSpec(["python3", "-u", "-B", str(exporter), "merge", str(run / "pcd"), str(output)], root)
    name = "map_preview_015m.pcd" if role == "preview" else "map_raw.pcd"
    cloud = private_path(root, run / "merged" / name, exists=True)
    return ProcessSpec(["pcl_viewer", str(cloud), "-ps", "3" if role == "preview" else "1"], root)


class LogCapture:
    """Duplicate process bytes to disk; no in-memory log accumulation."""
    def __init__(self, path, *, exclusive):
        path = Path(path)
        if path.is_symlink():
            raise SafetyError(f"日志不能是链接：{path}")
        flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        flags |= os.O_EXCL if exclusive else os.O_APPEND
        self._stream = os.fdopen(os.open(path, flags, 0o600), "wb", buffering=0)

    def write(self, data):
        if self._stream.closed:
            return
        remaining = memoryview(data)
        while remaining:
            written = self._stream.write(remaining)
            if not written:
                raise OSError("本轮日志写入失败")
            remaining = remaining[written:]

    def close(self):
        self._stream.close()


def verify_helpers(root, bundle):
    expected = json.loads((Path(bundle) / "compatibility.json").read_text(encoding="utf-8"))["files"]
    for relative, digest in expected.items():
        path = private_path(root, Path(root) / relative, exists=True)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise SafetyError(f"已有工具版本校验不一致，不替换文件：{path}")


def load_existing_helper(root=ROOT):
    sys.dont_write_bytecode = True
    scripts = private_path(root, Path(root) / "scripts", exists=True)
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("_hz_existing_session", scripts / "hz_mapping_session.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_robot_environment(root=ROOT):
    if sys.platform != "linux" or socket.gethostname() != HOSTNAME:
        raise SafetyError(f"此入口只在 {HOSTNAME} 的 Ubuntu 上运行")
    private_root(root)
    expected = {"ROS_DOMAIN_ID": "88", "RMW_IMPLEMENTATION": "rmw_fastrtps_cpp", "ROS_LOCALHOST_ONLY": "0", "ROS_HOME": str(root / ".ros"), "ROS_LOG_DIR": str(root / "logs/ros")}
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise SafetyError(f"请先 source {root / BUNDLE_NAME / 'hz_env.sh'}")
    for part in ("maps", "logs", ".ros"):
        private_path(root, root / part, exists=True)
