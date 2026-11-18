"""Personal HUNTER 2.0 Nav2 entry, based on the verified November 8 runbook."""

from hashlib import sha256
import fcntl
import json
import math
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import subprocess
import time
import uuid

from ament_index_python.packages import get_package_prefix
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import yaml


ROOT = Path('/home/car/hz_nav_ws')
TOOL = ROOT / 'hz_nav_launch'
ROS = '/opt/ros/humble'
BASE = '/home/car/hunter_nav_odom_ws/install'
LIDAR = '/home/car/hesai_xt32_ws/install'
DEFAULT_MAP = 'lab_odom_06_nav.yaml'
NS = '/hz_nav'
ENV = {'ROS_DISTRO': 'humble', 'ROS_DOMAIN_ID': '88',
       'RMW_IMPLEMENTATION': 'rmw_fastrtps_cpp', 'ROS_LOCALHOST_ONLY': '0',
       'ROS_LOG_DIR': str(ROOT / 'logs'), 'ROS_HOME': str(ROOT / '.ros'),
       'TMPDIR': str(ROOT / 'logs')}

FILES = {
    'sensors': ('launch/01_sensors.launch.py', 'config/hunter_nav.urdf', 'config/hesai_xt32.yaml'),
    'base': (),
    'nav2': ('launch/bringup_launch.py', 'launch/localization_launch.py',
             'launch/navigation_launch.py', 'config/nav2_params.yaml',
             'config/navigate_no_spin.xml', 'config/navigate_through_poses_no_spin.xml'),
    'rviz': ('rviz/lab_odom_06_map_view.rviz',),
}
PACKAGES = {
    'sensors': {'hesai_ros_driver': LIDAR, 'robot_state_publisher': ROS, 'pointcloud_to_laserscan': ROS},
    'base': {'hunter_base': BASE + '/hunter_base', 'hunter_msgs': BASE},
    'nav2': dict.fromkeys(
        ('nav2_bringup', 'nav2_common', 'nav2_map_server', 'nav2_amcl', 'nav2_controller',
         'nav2_planner', 'nav2_smoother', 'nav2_velocity_smoother', 'nav2_behaviors',
         'nav2_bt_navigator', 'nav2_lifecycle_manager', 'rclcpp_components'), ROS),
    'rviz': {'rviz2': ROS},
}
NODES = {
    'sensors': {'robot_state_publisher', 'hesai_ros_driver_node', 'xt32_to_scan'},
    'base': {'hunter_base_node'},
    'nav2': {'nav2_container', 'map_server', 'amcl', 'controller_server', 'planner_server',
             'bt_navigator', 'behavior_server', 'velocity_smoother', 'smoother_server',
             'waypoint_follower', 'lifecycle_manager_localization', 'lifecycle_manager_navigation'},
    'rviz': {'rviz2'},
}


def require_environment(role):
    profile = 'check' if role == 'doctor' else role
    if (pwd.getpwuid(os.getuid()).pw_name != 'car'
            or socket.gethostname().split('.')[0].casefold() != 'car-nuc15jnku7x4'):
        raise RuntimeError('请在小车 car@car-NUC15JNKU7X4 的 Ubuntu 终端运行。')
    if ROOT.resolve() != ROOT or ROOT.stat().st_uid != os.getuid():
        raise RuntimeError(f'个人工作区不是 car 所有的实际目录 {ROOT}')
    if Path(__file__).resolve().parent != TOOL:
        raise RuntimeError(f'请先把本版入口安装到 {TOOL}')
    if os.environ.get('HZ_NAV_PROFILE') != profile:
        raise RuntimeError(f'请在新终端 source {TOOL}/hz_env.bash {profile}')
    for name, expected in ENV.items():
        if os.environ.get(name) != expected:
            raise RuntimeError(f'{name} 当前为 {os.environ.get(name)!r}，应为 {expected!r}')
    if 'FASTRTPS_DEFAULT_PROFILES_FILE' in os.environ:
        raise RuntimeError('当前终端仍加载了共享 Fast DDS 配置，请重新加载个人环境。')
    logs = ROOT / 'logs'
    if logs.resolve() != logs or logs.stat().st_uid != os.getuid() or not os.access(logs, os.W_OK):
        raise RuntimeError(f'个人日志目录不可用 {logs}')


def require_file(relative, expected=None):
    path = ROOT / relative
    if not path.is_file() or not os.access(path, os.R_OK) or not path.resolve().is_relative_to(ROOT):
        raise RuntimeError(f'个人输入文件缺失、不可读或指向工作区外 {path}')
    if expected is not None:
        actual = sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f'{path} 与 11 月 8 日快照不同。当前 SHA256 {actual}，预期 {expected}。')
    return path


def verify_inputs(role, map_name):
    hashes = {}
    for line in (TOOL / 'baseline.sha256').read_text(encoding='ascii').splitlines():
        digest, relative = line.split('  ', 1)
        hashes[relative] = digest

    roles = FILES if role == 'doctor' else (role,)
    for item in roles:
        for relative in FILES[item]:
            require_file(relative, hashes[relative])
    if role not in ('nav2', 'doctor'):
        return None
    if Path(map_name).name != map_name or Path(map_name).suffix not in ('.yaml', '.yml'):
        raise RuntimeError('map:= 仅接收个人 maps 目录里的 YAML 文件名。')
    relative = f'maps/{map_name}'
    path = require_file(relative, hashes[relative] if map_name == DEFAULT_MAP else None)
    config = yaml.safe_load(path.read_text(encoding='utf-8'))
    image = config.get('image') if isinstance(config, dict) else None
    if not isinstance(image, str) or not image.strip():
        raise RuntimeError(f'{path} 缺少有效的 image 字段。')
    image_path = (path.parent / image).resolve()
    if not image_path.is_relative_to(ROOT / 'maps'):
        raise RuntimeError(f'地图图像必须位于个人 maps 目录内 {image_path}')
    image_relative = str(image_path.relative_to(ROOT))
    require_file(image_relative, hashes[image_relative] if map_name == DEFAULT_MAP else None)
    print(f'[个人 Nav2] 地图 {path}，图像 {image_path}', flush=True)
    return path


def verify_packages(role, prefixes=None):
    for package, expected in PACKAGES[role].items():
        actual = Path(get_package_prefix(package) if prefixes is None else prefixes[package])
        wanted = Path(expected)
        matches = actual == wanted if package == 'hunter_base' else actual.is_relative_to(wanted)
        if not matches:
            raise RuntimeError(f'{package} 来自 {actual}，应在 {wanted}')
        print(f'[个人 Nav2] {role} {package} → {actual}', flush=True)


def doctor():
    # Check each profile as a fresh terminal so the XT32 and chassis overlays never mix.
    env = {'HOME': '/home/car', 'USER': 'car', 'LOGNAME': 'car',
           'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}
    script = ('import json, sys\n'
              'from ament_index_python.packages import get_package_prefix\n'
              'print(json.dumps({name: get_package_prefix(name) for name in sys.argv[1:]}))')
    for profile, packages in PACKAGES.items():
        result = subprocess.run(
            ['bash', '--noprofile', '--norc', '-c',
             'source "$1" "$2" && shift 2 && python3 -B -c "$@"',
             'hz-nav-doctor', str(TOOL / 'hz_env.bash'), profile, script, *packages],
            env=env, capture_output=True, text=True, timeout=20, check=False)
        if result.returncode or not result.stdout.strip():
            raise RuntimeError(f'{profile} 包来源核对失败：{result.stderr.strip()}')
        verify_packages(profile, json.loads(result.stdout.strip().splitlines()[-1]))
    return [LogInfo(msg='预检通过。已核对个人文件、默认接线和各角色的 ROS 包来源。')]


def lock_role(role):
    path = ROOT / 'logs' / f'.hz_nav_{role}.lock'
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError(f'角色锁不是本人文件 {path}')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f'{role} 已有本版运行窗口，请复用该窗口。') from exc
        os.ftruncate(fd, 0)
        os.write(fd, (uuid.uuid4().hex + '\n').encode('ascii'))
    except BaseException:
        os.close(fd)
        raise
    return fd  # Close on process exit. Child processes do not inherit this descriptor.


def inspect_hardware(role):
    if role == 'sensors':
        result = subprocess.run(['ss', '-H', '-a', '-u', '-n', 'sport = :2368'],
                                capture_output=True, text=True, timeout=4, check=True)
        if result.stdout.strip():
            raise RuntimeError('XT32 的 UDP 2368 已被占用。请确认并复用现有雷达，保留他人进程。')
    if role == 'base':
        result = subprocess.run(['ip', '-details', 'link', 'show', 'dev', 'can0'],
                                capture_output=True, text=True, timeout=4, check=False)
        flags = re.search(r'<([^>]+)>', result.stdout)
        if (result.returncode or not flags or 'UP' not in flags.group(1).split(',')
                or not re.search(r'\bbitrate 500000\b', result.stdout)
                or not re.search(r'\bcan state (?:ERROR-ACTIVE|ERROR-WARNING)\b', result.stdout)):
            raise RuntimeError('can0 未达到可启动状态。请核对 UP、500000 和 CAN 状态。\n'
                               + (result.stdout or result.stderr).strip())
        for cmdline in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                command = cmdline.read_bytes().split(b'\0', 1)[0]
            except OSError:
                continue
            if command.rsplit(b'/', 1)[-1] == b'hunter_base_node':
                raise RuntimeError(f'已发现底盘驱动 PID {cmdline.parent.name}，请复用已有会话。')


def check_graph(role):
    import rclpy
    from rclpy.context import Context
    from rclpy.qos import qos_profile_sensor_data

    context = Context()
    rclpy.init(args=[], context=context)
    node = None
    try:
        node = rclpy.create_node('hz_nav_launch_precheck', context=context,
                                 enable_rosout=False, start_parameter_services=False)
        odom = []
        if role == 'nav2':
            from nav_msgs.msg import Odometry
            node.create_subscription(Odometry, NS + '/odom', odom.append, qos_profile_sensor_data)

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
        visible = set(node.get_node_names_and_namespaces())
        conflicts = {f'{namespace.rstrip("/")}/{name}' for name, namespace in visible
                     if name in NODES[role] and (namespace == NS or role == 'base'
                                                  or name == 'hesai_ros_driver_node')}
        if conflicts:
            raise RuntimeError('已有节点，请复用原窗口 ' + ', '.join(sorted(conflicts)))
        if role == 'base' and (node.get_publishers_info_by_topic(NS + '/blocked_cmd_vel')
                               or ('nav2_container', NS) in visible):
            raise RuntimeError('已发现导航容器或底盘速度发布者。先确认本人旧会话状态。')
        if role == 'nav2':
            if ('xt32_to_scan', NS) not in visible:
                raise RuntimeError('未发现 /hz_nav/xt32_to_scan，请先启动或核对个人传感器窗口。')
            deadline = time.monotonic() + 6.0
            while not odom and time.monotonic() < deadline:
                rclpy.spin_once(node, timeout_sec=0.1)
            if not odom:
                raise RuntimeError('未收到 /hz_nav/odom，请先核对底盘窗口。')
            msg = odom[-1]
            p = msg.pose.pose.position
            v = msg.twist.twist.linear.x
            if (msg.header.frame_id != 'odom' or msg.child_frame_id != 'base_link'
                    or not all(math.isfinite(value) for value in (p.x, p.y, v))
                    or math.hypot(p.x, p.y) > 10000 or abs(v) > 20):
                raise RuntimeError(f'里程计异常：{msg.header.frame_id} → {msg.child_frame_id}，'
                                   f'x={p.x}，y={p.y}，vx={v}。请停在检查阶段。')
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown(context=context)


def include(name, arguments=None):
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(ROOT / 'launch' / name)),
        launch_arguments=(arguments or {}).items())


def startup_actions(role, map_path):
    if role == 'sensors':
        return [include('01_sensors.launch.py')]
    if role == 'nav2':
        return [include('bringup_launch.py', {
            'namespace': 'hz_nav', 'use_namespace': 'true', 'slam': 'False',
            'map': str(map_path), 'params_file': str(ROOT / 'config/nav2_params.yaml'),
            'use_sim_time': 'false', 'autostart': 'false',
        })]
    if role == 'rviz':
        return [Node(package='rviz2', executable='rviz2', output='screen', emulate_tty=True,
                     arguments=['-d', str(ROOT / 'rviz/lab_odom_06_map_view.rviz')],
                     ros_arguments=['-r', '__ns:=/hz_nav', '-r', '/initialpose:=/hz_nav/initialpose'])]
    return [Node(package='hunter_base', executable='hunter_base_node', output='screen', emulate_tty=True,
                 ros_arguments=['-r', '__ns:=/hz_nav', '-p', 'use_sim_time:=false',
                                '-p', 'port_name:=can0', '-p', 'robot_model:=hunter2',
                                '-p', 'simulated_robot:=false', '-p', 'odom_frame:=odom',
                                '-p', 'base_frame:=base_link', '-p', 'odom_topic_name:=/hz_nav/odom',
                                '-p', 'publish_odom_tf:=true', '-r', '/cmd_vel:=/hz_nav/blocked_cmd_vel',
                                '-r', '/hunter_status:=/hz_nav/hunter_status'])]


def setup_role(context):
    role = LaunchConfiguration('role').perform(context)
    require_environment(role)
    if role == 'base' and LaunchConfiguration('connect_chassis').perform(context) != 'true':
        raise RuntimeError('底盘启动需要现场接管并明确同意。确认后才可使用 connect_chassis:=true。')
    map_name = LaunchConfiguration('map').perform(context)
    if map_name != DEFAULT_MAP and role not in ('nav2', 'doctor'):
        raise RuntimeError('map:= 只用于 nav2 或 doctor。')
    map_path = verify_inputs(role, map_name)
    if role == 'doctor':
        return doctor()
    verify_packages(role)
    fd = lock_role(role)
    try:
        inspect_hardware(role)
        check_graph(role)
        if role == 'base':
            print('[个人 Nav2] 启动真实底盘，驱动会启用电脑控制并尝试释放制动。', flush=True)
        return startup_actions(role, map_path)
    except BaseException:
        os.close(fd)
        raise


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('role', default_value='doctor',
                              choices=['doctor', 'sensors', 'base', 'nav2', 'rviz']),
        DeclareLaunchArgument('connect_chassis', default_value='false', choices=['false', 'true']),
        DeclareLaunchArgument('map', default_value=DEFAULT_MAP,
                              description='Personal map YAML filename in /home/car/hz_nav_ws/maps.'),
        OpaqueFunction(function=setup_role),
    ])
