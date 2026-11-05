"""Preflight only: imports/checks files, does not open a sensor or start nodes."""
import inspect
import json
import os
from pathlib import Path
import shutil
import socket
import sys

sys.dont_write_bytecode = True
import hz_launch_support as support


def environment_paths():
    root = support.private_root()
    if sys.platform != "linux" or socket.gethostname() != support.HOSTNAME or os.getuid() != root.stat().st_uid:
        raise support.SafetyError("请以 car 身份在指定小车的 Ubuntu 上使用")
    for part in (".ros", "logs", "logs/ros", "maps"):
        support.private_path(root, root / part)
    for part in (".ros", "logs/ros"):
        (root / part).mkdir(parents=True, exist_ok=True)
    return root


def diagnose():
    root = environment_paths()
    bundle = Path(__file__).resolve().parent
    support.require_robot_environment(root)
    support.verify_helpers(root, bundle)
    from ament_index_python.packages import get_package_prefix
    from launch.actions.execute_local import ExecuteLocal
    from launch.event_handlers import OnProcessIO
    import yaml
    for package, expected in (
        ("fast_livo", root / "install/fast_livo"),
        ("hesai_ros_driver", root / "install/hesai_ros_driver"),
        ("realsense2_camera", Path("/home/car/d435i_ws/install/realsense2_camera")),
    ):
        actual = Path(get_package_prefix(package))
        if actual != expected:
            raise support.SafetyError(f"{package} 来源不符：{actual}；预期 {expected}")
        print(f"包路径：{package} -> {actual}", flush=True)
    for command in ("python3", "ros2", "rviz2", "pcl_viewer", "fuser"):
        if not shutil.which(command):
            raise support.SafetyError(f"缺少现有命令：{command}")
    for relative in (
        "config/xt32_ch104_d435i.yaml", "config/camera_d435i_640x480.yaml",
        "config/config.yaml", "config/xt32_firetime.csv", "config/hz_mapping.rviz",
        "scripts/ch104_imu_pub_legacy.py",
    ):
        path = support.private_path(root, root / relative, exists=True)
        if not path.is_file():
            raise support.SafetyError(f"需要常规文件：{path}")
    for relative in ("install/fast_livo/lib/fast_livo/fastlivo_mapping", "install/hesai_ros_driver/lib/hesai_ros_driver/hesai_ros_driver_node"):
        path = support.private_path(root, root / relative, exists=True)
        if not os.access(path, os.X_OK):
            raise support.SafetyError(f"现有节点没有执行权限：{path}")
    api = inspect.signature(ExecuteLocal.__init__).parameters
    if any(name not in api for name in ("output", "emulate_tty", "cached_output", "on_exit")) or "on_stdout" not in inspect.signature(OnProcessIO.__init__).parameters:
        raise support.SafetyError("当前 ROS launch API 与本版不兼容")
    camera_params = yaml.safe_load((root / "config/camera_d435i_640x480.yaml").read_text(encoding="utf-8"))["/**"]["ros__parameters"]["camera"]
    if (camera_params.get("width"), camera_params.get("height")) != (640, 480):
        raise support.SafetyError("相机内参配置分辨率不是 640×480，请核对原配置")
    device = Path("/dev/ch104")
    if not device.exists() or not os.access(device, os.R_OK | os.W_OK):
        raise support.SafetyError("/dev/ch104 缺失或 car 无读写权限；仅报告，不修改设备权限")
    print("已有会话工具 SHA256：一致。ROS launch API：兼容。", flush=True)
    state = root / "maps/hz_active_session.json"
    if state.exists():
        run = support.active_run(root)
        output = root / "src/FAST-LIVO2/Log/PCD"
        if not output.is_symlink() or output.resolve() != (run / "pcd").resolve():
            raise support.SafetyError("活动目录与 PCD 输出链接不一致")
        print(f"当前轮：{run}", flush=True)
        count = sum(1 for _ in (run / "pcd").glob("*.pcd"))
        print(f"当前轮已有 PCD：{count}；下次采集执行一次 prepare 建立新轮次。", flush=True)
    else:
        print("尚无活动轮次；首次采集执行一次 prepare。", flush=True)
    helper = support.load_existing_helper(root)
    print("个人会话状态：" + json.dumps(helper.processes(), ensure_ascii=False), flush=True)
    print("预检通过。后续按最终清单检查 10Hz / 100Hz / 15Hz 数据流及静止建图落盘。", flush=True)


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--env-only"]:
            environment_paths()
        elif not sys.argv[1:]:
            diagnose()
        else:
            raise support.SafetyError("未知诊断选项")
    except Exception as exc:
        print(f"预检停止：{exc}", file=sys.stderr)
        sys.exit(1)
