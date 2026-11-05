"""Read-only full-model entry contract; runtime checks never start software.

Pure APIs validate manifests, installed outputs, environment, share and args.
check_entry() additionally reads personal WSL, ament and installed library files.
The sole non-installed source output is the build-time CMakeLists.txt.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'hz_hunter_full_description'
EXPECTED_SHARE = '/home/aphelios/hz_sim_ws/install/hz_hunter_full_description/share/hz_hunter_full_description'
EXPECTED_NATIVE_SOURCE = '/home/aphelios/hz_sim_ws/src/hz_hunter_full_description'
MANIFEST_REL = 'sim/tools/hunter_full_entry_manifest.json'
# Fixed reviewed files. The scene gate separately seals world/GUI/CAD.
SEALED_PATHS = (
    'sim/tools/start_hunter_full_scene.ps1',
    'sim/tools/start_hunter_full_scene.bash',
    'sim/tools/start_control_scene_logged.ps1',
    'sim/tools/start_control_scene_logged.bash',
    'sim/tools/full_scene_session.py',
    'sim/tools/check_full_entry.py',
    'sim/tools/seal_full_entry.py',
    'sim/tools/check_ros_isolation.py',
    'sim/tools/check_hunter_full_scene.py',
    'sim/tools/hunter_sensor_profile.py',
    'sim/tools/check_full_ros_interfaces.py',
    'sim/launch/hunter_full_ros.launch.py',
    'sim/config/hunter_full_bridge.yaml',
    'wsl/hz_sim_env.bash',
)
BUILD_ONLY_OUTPUTS = frozenset({'CMakeLists.txt'})
PLUGIN_DIRECTORY = Path('/usr/lib/x86_64-linux-gnu/ign-gazebo-6/plugins')
RENDER_DIRECTORY = Path('/usr/lib/x86_64-linux-gnu/ign-rendering-6/engine-plugins')
PLUGIN_NAMES = ('sensors', 'imu', 'physics', 'user-commands', 'scene-broadcaster',
                'ackermann-steering', 'joint-state-publisher')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_relative(relative):
    if (not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative
            or relative.startswith('/') or relative != PurePosixPath(relative).as_posix()
            or any(part in ('', '.', '..') for part in relative.split('/'))):
        raise ValueError('路径必须是根目录内的固定相对文件：' + str(relative))


def local_file(root, relative):
    """Reject noncanonical relative paths, traversal and symlinks outside root."""
    validate_relative(relative)
    base = Path(root).resolve()
    candidate = (base / relative).resolve()
    if not candidate.is_relative_to(base) or not candidate.is_file():
        raise ValueError('文件缺失或路径越界：' + relative)
    return candidate


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('JSON 中存在重复键：' + key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_reject_duplicate_keys)


def _output_records(records):
    if not isinstance(records, list) or not records:
        raise ValueError('文件清单必须为非空列表')
    result = {}
    for record in records:
        if not isinstance(record, dict) or set(record) != {'path', 'sha256'}:
            raise ValueError('清单文件字段不符合约定')
        relative, digest = record['path'], record['sha256']
        if not isinstance(relative, str) or relative in result:
            raise ValueError('清单存在重复或无效路径')
        if not isinstance(digest, str) or re.fullmatch('[0-9a-f]{64}', digest) is None:
            raise ValueError('SHA256 格式无效')
        result[relative] = digest
    return result


def validate_manifest(data, root):
    if (not isinstance(data, dict) or set(data) != {'schema_version', 'files'}
            or type(data['schema_version']) is not int or data['schema_version'] != 1):
        raise ValueError('入口封存清单格式无效')
    records = _output_records(data['files'])
    if set(records) != set(SEALED_PATHS):
        raise ValueError('入口封存清单漏项、多项或路径不在固定列表中')
    for relative, expected in records.items():
        if sha256(local_file(root, relative)) != expected:
            raise ValueError('入口封存 SHA256 不符：' + relative)
    return {'sealed_files': len(records), 'sealed_paths': list(SEALED_PATHS)}


def validate_installed_target(relative, target, share, native_source=EXPECTED_NATIVE_SOURCE):
    """Allow only the identical relative file in share or personal colcon src.

    This exception belongs only to installed resources. Entry seals still use
    local_file and never permit resolved paths outside their reviewed root.
    """
    validate_relative(relative)
    target = Path(target)
    allowed = (Path(share) / relative, Path(native_source) / relative)
    if target not in allowed:
        raise ValueError('安装资源指向非预期位置：' + relative + ' -> ' + str(target))
    return target


def installed_file(share, relative, native_source=EXPECTED_NATIVE_SOURCE):
    validate_relative(relative)
    base = Path(share).resolve()
    target = (base / relative).resolve()
    validate_installed_target(relative, target, base, native_source)
    if not target.is_file():
        raise ValueError('已安装资源缺失：' + relative)
    return target


def validate_installed_outputs(source, share, manifest, native_source=EXPECTED_NATIVE_SOURCE):
    """Check source, installed resources and manifest; exempt only CMakeLists.

    CMakeLists.txt remains mandatory and checked in source. Ament does not
    install this build file; every other listed output is mandatory in share.
    """
    if not isinstance(manifest, dict):
        raise ValueError('源包清单无效')
    records = _output_records(manifest.get('outputs'))
    for relative, expected in records.items():
        if sha256(local_file(source, relative)) != expected:
            raise ValueError('源包输出 SHA256 不符：' + relative)
        if relative not in BUILD_ONLY_OUTPUTS:
            if sha256(installed_file(share, relative, native_source)) != expected:
                raise ValueError('已安装包与源包不一致：' + relative)
    if sha256(local_file(source, 'source_manifest.json')) != sha256(installed_file(share, 'source_manifest.json', native_source)):
        raise ValueError('已安装 source_manifest.json 与源包不一致')
    return {'source_outputs': len(records),
            'installed_outputs': len(set(records) - BUILD_ONLY_OUTPUTS),
            'not_installed_build_files': sorted(set(records) & BUILD_ONLY_OUTPUTS),
            'source_manifest_equal': True,
            'installed_symlink_source_root': str(native_source),
            'installed_targets_require_same_relative_path': True}


def validate_environment(env, kernel, username):
    required = {'WSL_DISTRO_NAME': 'Ubuntu-22.04', 'ROS_DISTRO': 'humble',
                'ROS_DOMAIN_ID': '73', 'ROS_LOCALHOST_ONLY': '1',
                'RMW_IMPLEMENTATION': 'rmw_cyclonedds_cpp',
                'IGN_PARTITION': 'hz_sim_aphelios_73', 'IGN_IP': '127.0.0.1'}
    if username != 'aphelios' or 'microsoft' not in kernel.lower():
        raise ValueError('仅允许个人 WSL Ubuntu-22.04 的 aphelios 用户')
    for key, value in required.items():
        if env.get(key) != value:
            raise ValueError(key + ' 必须为 ' + value)
    for key in ('CYCLONEDDS_URI', 'IGN_RELAY', 'IGN_GAZEBO_SYSTEM_PLUGIN_PATH',
                'IGN_GAZEBO_RESOURCE_PATH', 'IGN_GAZEBO_SERVER_CONFIG_PATH'):
        if env.get(key):
            raise ValueError('不允许继承自定义环境变量：' + key)
    return required


def validate_share_path(path):
    actual = Path(path)
    expected = Path(EXPECTED_SHARE)
    if str(actual) != str(expected) or actual.resolve() != expected:
        raise ValueError('ament 必须解析到个人安装包：' + EXPECTED_SHARE)
    return actual


def validate_args(args, allow_check=False):
    if not args:
        return False
    if allow_check and list(args) == ['--check']:
        return True
    raise ValueError('入口只接受无参数' + ('或单个 --check' if allow_check else ''))


def check_installed_libraries():
    result = {}
    for name in PLUGIN_NAMES:
        candidates = [PLUGIN_DIRECTORY / ('libignition-gazebo6-' + name + '-system.so'),
                      PLUGIN_DIRECTORY / ('libignition-gazebo-' + name + '-system.so')]
        found = next((path for path in candidates if path.is_file()), None)
        if found is None:
            raise ValueError('缺少已安装 Fortress 系统库：' + name)
        result[name] = str(found)
    candidates = [RENDER_DIRECTORY / 'libignition-rendering6-ogre.so',
                  RENDER_DIRECTORY / 'libignition-rendering-ogre.so']
    found = next((path for path in candidates if path.is_file()), None)
    if found is None:
        raise ValueError('缺少已安装 Ogre 渲染库')
    result['ogre'] = str(found)
    return result


def check_entry():
    # Linux-only modules and ament are imported only by this explicit API.
    import pwd
    username = pwd.getpwuid(os.getuid()).pw_name
    env = validate_environment(os.environ, Path('/proc/sys/kernel/osrelease').read_text(), username)
    if ROOT != Path('/mnt/f/rob-memory'):
        raise ValueError('入口必须来自固定 F 盘工作目录')
    seal = validate_manifest(read_json(ROOT / MANIFEST_REL), ROOT)
    from check_hunter_full_scene import check_scene
    from check_full_ros_interfaces import check_interfaces
    scene, interfaces = check_scene(), check_interfaces()
    from ament_index_python.packages import get_package_share_directory
    share = validate_share_path(get_package_share_directory(PACKAGE))
    source = ROOT / 'sim' / PACKAGE
    package = validate_installed_outputs(source, share, read_json(source / 'source_manifest.json'))
    dependencies = {}
    for name in ('ros_gz_bridge', 'robot_state_publisher', 'pointcloud_to_laserscan'):
        path = Path(get_package_share_directory(name))
        if not path.is_dir():
            raise ValueError('缺少已安装 ROS 观察包：' + name)
        dependencies[name] = str(path)
    return {'status': 'PASS', 'check_only': True, 'environment': env, 'entry': seal,
            'package_share': str(share), 'package': package, 'ros_packages': dependencies,
            'installed_libraries': check_installed_libraries(), 'scene': scene,
            'interfaces': interfaces, 'started_ros_or_gazebo': False,
            'runtime_verified': False, 'motion_commands_sent': False}


def main():
    try:
        validate_args(sys.argv[1:])
        receipt = check_entry()
    except Exception as exc:
        print('完整模型入口检查未通过：' + str(exc), file=sys.stderr)
        return 1
    print('完整模型入口检查通过；仅检查环境、文件、安装包和库，未启动 ROS 或 Gazebo。')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
