"""Inspect the personal ROS context without motion publishers or drivers."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import uuid
from xml.sax.saxutils import escape


def validate_environment(env, kernel_release, username):
    required = {
        "WSL_DISTRO_NAME": "Ubuntu-22.04",
        "ROS_DISTRO": "humble",
        "ROS_DOMAIN_ID": "73",
        "ROS_LOCALHOST_ONLY": "1",
        "RMW_IMPLEMENTATION": "rmw_cyclonedds_cpp",
    }
    if username != "aphelios" or "microsoft" not in kernel_release.lower():
        raise ValueError("仅允许在个人 WSL 的 aphelios 用户中检查")
    for key, expected in required.items():
        if env.get(key) != expected:
            raise ValueError(f"{key} 未设置为个人仿真要求的 {expected}")
    if env.get("CYCLONEDDS_URI"):
        raise ValueError("存在自定义 DDS 配置；请先重新加载个人仿真环境文件")


def selected_addresses(trace):
    # CycloneDDS 0.10.5 q_init.c logs all selected locators on ownip lines.
    # Its earlier interfaces line lists candidates, not the selected set.
    payloads = re.findall(r"\bownip:\s*([^\r\n]+)", trace)
    if not payloads:
        raise ValueError("DDS 日志中没有实际接口选择记录")
    for payload in payloads:
        if any(part.strip() != "udp/127.0.0.1" for part in payload.split(",")):
            raise ValueError("DDS 实际接口记录包含非本机地址或未知格式")
    return ["127.0.0.1"]


def run_probe():
    import pwd  # Linux identity is needed only when the actual ROS probe is requested.
    username = pwd.getpwuid(os.getuid()).pw_name
    kernel = Path("/proc/sys/kernel/osrelease").read_text().strip()
    validate_environment(os.environ, kernel, username)

    workspace = Path("/home/aphelios/hz_sim_ws")
    reports = workspace / "reports"
    if workspace.resolve() != workspace or reports.resolve() != reports:
        raise ValueError("个人工作区或报告目录不是预期的独立路径")
    reports.mkdir(exist_ok=True)
    run_dir = reports / ("ros_isolation_" + uuid.uuid4().hex[:12])
    run_dir.mkdir(mode=0o700)
    trace_path = run_dir / "cyclonedds.log"

    # Add logging only. Interface selection still comes from Humble RMW's
    # ROS_LOCALHOST_ONLY handling; this fragment changes no interfaces/peers.
    original_uri = os.environ.get("CYCLONEDDS_URI")
    os.environ["CYCLONEDDS_URI"] = (
        "<CycloneDDS><Domain><Tracing><Verbosity>config</Verbosity>"
        f"<OutputFile>{escape(str(trace_path))}</OutputFile>"
        "</Tracing></Domain></CycloneDDS>"
    )
    context = None
    node = None
    try:
        # ROS is deliberately imported only after the refusal checks.
        import rclpy
        from rclpy.context import Context
        from rclpy.utilities import get_rmw_implementation_identifier

        context = Context()
        rclpy.init(args=[], context=context, domain_id=73)
        node = rclpy.create_node(
            "isolation_probe_" + uuid.uuid4().hex[:8],
            namespace="/hz_sim", context=context,
            use_global_arguments=False, enable_rosout=False,
            start_parameter_services=False,
        )
        actual_domain = context.get_domain_id()
        actual_rmw = get_rmw_implementation_identifier()
        node_name = node.get_fully_qualified_name()
        if actual_domain != 73 or actual_rmw != "rmw_cyclonedds_cpp":
            raise ValueError("运行中的 ROS 通信域或中间件不符合个人环境设置")
    finally:
        if node is not None:
            node.destroy_node()
        if context is not None and context.ok():
            context.shutdown()
        if original_uri is None:
            os.environ.pop("CYCLONEDDS_URI", None)
        else:
            os.environ["CYCLONEDDS_URI"] = original_uri

    addresses = selected_addresses(trace_path.read_text())
    receipt = {
        "format": "hz_personal_ros_runtime_check_v1",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "username": username,
        "wsl_distribution": os.environ["WSL_DISTRO_NAME"],
        "ros_domain_id": actual_domain,
        "rmw_implementation": actual_rmw,
        "dds_selected_addresses": addresses,
        "probe_node": node_name,
        "probe_node_destroyed": True,
        "trace_path": str(trace_path),
        "motion_commands_published": False,
        "hardware_driver_started": False,
        "os_network_sandbox_verified": False,
        "scope": "This ROS context selected domain 73 and the loopback interface; not a network firewall or a Gazebo transport test.",
    }
    text = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    (run_dir / "check.json").write_text(text)
    temporary = reports / ("ros_isolation_latest_" + uuid.uuid4().hex + ".tmp")
    temporary.write_text(text)
    temporary.replace(reports / "ros_isolation_latest.json")
    return receipt


def main():
    try:
        if len(sys.argv) != 1:
            raise ValueError("此检查程序不接受额外启动参数")
        receipt = run_probe()
    except Exception as exc:
        print(f"检查未通过：{exc}", file=sys.stderr)
        return 1
    print("通过：个人 ROS 域 73，CycloneDDS 实际选择 127.0.0.1。")
    print("检查节点已退出；未发布运动指令，未启动底盘驱动。")
    print("记录：/home/aphelios/hz_sim_ws/reports/ros_isolation_latest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
