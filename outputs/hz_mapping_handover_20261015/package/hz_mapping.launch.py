"""Native ROS 2 entry: ros2 launch "$hzLaunch" role:=lidar (etc.)."""
import atexit
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hz_launch_support as support

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, ExecuteProcess, OpaqueFunction, RegisterEventHandler
from launch.event_handlers import OnProcessIO
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration


def start_role(context):
    root = support.ROOT
    bundle = Path(__file__).resolve().parent
    support.require_robot_environment(root)
    support.verify_helpers(root, bundle)
    role = LaunchConfiguration("role").perform(context)
    helper = support.load_existing_helper(root)
    spec = support.build_spec(role, root, bundle, helper.processes())
    writer = support.LogCapture(spec.log_path, exclusive=spec.exclusive_log) if spec.log_path else None
    if writer:
        atexit.register(writer.close)

    def exited(event, launch_context):
        if writer:
            writer.close()
        if event.returncode not in (0, 130, -2):
            raise RuntimeError(f"{role} 退出码为 {event.returncode}，请保留终端输出并核对本轮日志")
        return [EmitEvent(event=Shutdown(reason=f"{role} finished"))]

    process = ExecuteProcess(
        cmd=spec.cmd,
        cwd=str(spec.cwd),
        name="hz_" + role,
        output="screen",
        emulate_tty=True,
        cached_output=False,
        respawn=False,
        sigterm_timeout="120",
        sigkill_timeout="120",
        additional_env={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1", "RCUTILS_LOGGING_BUFFERED_STREAM": "0"},
        on_exit=exited,
    )
    actions = []
    if writer:
        def copy_output(event):
            writer.write(event.text)
            return None
        actions.append(RegisterEventHandler(OnProcessIO(target_action=process, on_stdout=copy_output, on_stderr=copy_output)))
    print(f"hz_ws | {role} | 前台运行", flush=True)
    if spec.log_path:
        print(f"本轮日志：{spec.log_path}", flush=True)
    if role == "mapping":
        print("本轮仅允许启动一次；结束采集请在检查终端运行 role:=stop。", flush=True)
    actions.append(process)
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("role", default_value="status", choices=list(support.ROLES), description="个人建图操作，见建图使用说明.txt"),
        OpaqueFunction(function=start_role),
    ])
