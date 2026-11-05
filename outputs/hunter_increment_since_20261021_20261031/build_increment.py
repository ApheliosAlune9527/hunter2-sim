"""Copy and verify project changes since the user's verified Oct 21 archive."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import zipfile


SOURCE = Path(r'F:\rob-memory')
BASE = Path(r'F:\rob-memory-migration-20261021')
OUTPUT = SOURCE / 'outputs/hunter_increment_since_20261021_20261031'
PACKAGE_NAME = 'Hunter_increment_20261021_to_20261031'
PACKAGE = OUTPUT / PACKAGE_NAME
PAYLOAD = PACKAGE / '项目增量'
ARCHIVE = OUTPUT / 'Hunter_增量_20261021至20261031.zip'
BASE_ARCHIVE = BASE / 'rob-memory_迁移包_20261021.zip'
BASE_SHA = 'd38c199fd1e5442eac2dcd707bd8eadb45d4b50fce2273e7ab2b21a89e0ce734'
BASE_PREFIX = 'rob-memory-migration/rob-memory/'
SKIP_DIR_NAMES = {'__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'node_modules', '.git'}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def emit(stage, **data):
    print(json.dumps({'stage': stage, **data}, ensure_ascii=True), flush=True)


def write_json(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def write_text(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(data)


def excluded(relative):
    parts = PurePosixPath(relative).parts
    return (any(part in SKIP_DIR_NAMES for part in parts) or
            parts[0] == 'tmp' or relative.startswith('wsl/Ubuntu22.04/') or
            relative.startswith('outputs/hunter_increment_since_20261021_20261031/') or
            PurePosixPath(relative).suffix.lower() in {'.pyc', '.pyo', '.vhdx', '.vhd', '.avhdx'})


def safe_target(relative):
    parts = PurePosixPath(relative).parts
    if (not parts or PurePosixPath(relative).is_absolute() or
            any(part in {'.', '..'} or ':' in part for part in parts)):
        raise ValueError('Invalid relative payload path')
    target = PAYLOAD.joinpath(*parts)
    if not target.resolve().is_relative_to(PAYLOAD.resolve()):
        raise ValueError('Payload path escaped the package')
    return target


def main():
    if OUTPUT.resolve() != SOURCE.resolve() / 'outputs/hunter_increment_since_20261021_20261031':
        raise ValueError('Unexpected output directory')
    if PACKAGE.exists() or ARCHIVE.exists():
        raise FileExistsError('A previous deliverable exists; refusing to replace it')
    started = datetime.now().astimezone().isoformat(timespec='seconds')
    emit('verify_baseline')
    if sha(BASE_ARCHIVE) != BASE_SHA:
        raise ValueError('Oct 21 baseline ZIP SHA256 mismatch')
    baseline_raw = (BASE / 'MANIFEST.json').read_bytes()
    with zipfile.ZipFile(BASE_ARCHIVE) as archive:
        if archive.read('rob-memory-migration/MANIFEST.json') != baseline_raw:
            raise ValueError('Sidecar baseline manifest differs from archived manifest')
    baseline = json.loads(baseline_raw)
    old = {}
    for item in baseline['files']:
        if item['path'].startswith(BASE_PREFIX):
            relative = item['path'][len(BASE_PREFIX):]
            key = relative.casefold()
            if key in old:
                raise ValueError('Case-insensitive baseline path collision')
            old[key] = {'relative_path': relative, **item}

    changes, skipped_links, current = [], [], set()
    unchanged_count, unchanged_bytes = 0, 0
    emit('compare_project', baseline_snapshot=baseline['snapshot_completed_at'])
    for parent, dirs, names in os.walk(SOURCE, followlinks=False):
        dirs.sort()
        for name in list(dirs):
            path = Path(parent) / name
            relative = path.relative_to(SOURCE).as_posix()
            if path.is_symlink() or path.is_junction():
                skipped_links.append(relative)
                dirs.remove(name)
            elif excluded(relative + '/'):
                dirs.remove(name)
        for name in sorted(names):
            path = Path(parent) / name
            relative = path.relative_to(SOURCE).as_posix()
            if excluded(relative):
                continue
            if path.is_symlink():
                skipped_links.append(relative)
                continue
            if not path.resolve().is_relative_to(SOURCE.resolve()):
                raise ValueError('Source file escaped the workspace')
            current.add(relative.casefold())
            before = path.stat()
            digest = sha(path)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError('Source changed while hashing: ' + relative)
            previous = old.get(relative.casefold())
            if previous and digest == previous['sha256']:
                unchanged_count += 1
                unchanged_bytes += before.st_size
                continue
            changes.append({'relative_path': relative,
                            'change': 'changed' if previous else 'added',
                            'previous_sha256': previous['sha256'] if previous else None,
                            'sha256': digest, 'bytes': before.st_size,
                            'source_mtime_ns': before.st_mtime_ns})
    missing = sorted(x['relative_path'] for k, x in old.items()
                     if k not in current and not excluded(x['relative_path']))
    changes.sort(key=lambda x: x['relative_path'])
    delta_bytes = sum(x['bytes'] for x in changes)
    emit('copy_delta', files=len(changes), bytes=delta_bytes, unchanged_files=unchanged_count)
    PACKAGE.mkdir(parents=True, exist_ok=False)
    PAYLOAD.mkdir()
    for item in changes:
        target = safe_target(item['relative_path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / item['relative_path'], target)
        if target.stat().st_size != item['bytes'] or sha(target) != item['sha256']:
            raise ValueError('Snapshot copy differs from scanned source: ' + item['relative_path'])

    baseline_evidence = PACKAGE / '基线核对'
    baseline_evidence.mkdir()
    (baseline_evidence / '20261021_MANIFEST.json').write_bytes(baseline_raw)
    shutil.copy2(BASE / 'VERIFICATION.json', baseline_evidence / '20261021_VERIFICATION.json')
    manifest = {
        'format': 'hunter_project_increment_v1', 'build_started_at': started,
        'snapshot_completed_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'source_project': str(SOURCE), 'original_planned_target_project': r'D:\rob-memory',
        'baseline_archive_name': BASE_ARCHIVE.name, 'baseline_archive_sha256': BASE_SHA,
        'baseline_snapshot_completed_at': baseline['snapshot_completed_at'],
        'baseline_manifest_sha256': hashlib.sha256(baseline_raw).hexdigest(),
        'user_confirmed_desktop_state': 'Only the Oct 21 package was transferred; it has not been restored. Oct 28 package was not transferred.',
        'payload_directory': '项目增量', 'project_file_count': len(changes),
        'added_files': sum(x['change'] == 'added' for x in changes),
        'changed_files': sum(x['change'] == 'changed' for x in changes),
        'project_delta_bytes': delta_bytes, 'unchanged_project_files': unchanged_count,
        'unchanged_project_bytes': unchanged_bytes, 'project_files': changes,
        'baseline_files_not_found_in_current_source': missing,
        'delete_instructions': [], 'skipped_directory_or_file_links': skipped_links,
        'excluded_scope': [
            'Live WSL virtual disks and wsl/Ubuntu22.04; restore the baseline system then check dependencies and rebuild the new model from included source.',
            'tmp, Python/tool caches, .git and node_modules; directory links are not traversed.',
            'This delivery directory, unchanged baseline project files, and files outside F:/rob-memory.',
            'No new Codex database or transcript snapshot. The included handoff and project records provide the post-baseline task context.'
        ],
        'file_paths_preserved_verbatim': True,
        'requires_baseline_project': True, 'requires_oct28_package': False,
        'desktop_restore_executed': False, 'robot_commands_sent': False,
    }
    write_json(PACKAGE / '02_增量文件清单.json', manifest)
    write_text(PACKAGE / '03_项目增量SHA256.sha256',
               ''.join(x['sha256'] + '  项目增量/' + x['relative_path'] + '\n' for x in changes))

    readme = f'''# 只需再传这份增量包

用户已确认：台式机只收到 2026-10-21 的完整迁移包，尚未恢复；没有收到 10 月 28 日包。

本包以 10 月 21 日包中 {baseline['snapshot_completed_at']} 的项目快照为唯一基线，按文件 SHA256 比较当前 `F:\\rob-memory`。新增或修改的项目文件共 {len(changes)} 份，其中新增 {manifest['added_files']} 份、修改 {manifest['changed_files']} 份，未压缩项目增量约 {delta_bytes / 2**20:.2f} MiB。相同文件不重复放入。

## 传送与恢复顺序

1. 旧的 10 月 21 日完整包已经在台式机上，不需要重新传。
2. 将本次 `Hunter_增量_20261021至20261031.zip` 和旁边的 `.sha256` 校验文件传过去；不需要另传 10 月 28 日包。
3. 台式机先核对旧包并恢复项目基线，再核对本包，把 `项目增量` 中的文件按相对目录合并到恢复后的项目。不要把 `项目增量` 这一层本身当作项目根目录。
4. 把 `01_给台式机Agent的恢复说明.md` 交给台式机 Agent，先检查实际目录、旧环境和同名文件，再处理路径和新模型构建。原计划项目位置是 `D:\\rob-memory`，以台式机实际情况为准。

## 包含什么

- 10 月 21 日之后的项目记录、导航资料、二维地图候选及相关输出。
- 10 月 30～31 日的完整 HUNTER 2.0 CAD 模型、场景、启动/检查工具、传感器配置、外参来源和验证记录。
- 当前仿真进度说明、模型重建所用的新增网格和来源数据。
- 每个增量文件的旧哈希（若存在）、新哈希和大小，以及旧包基线清单。

## 环境与资料的边界

旧包已有当时的地图、知识库和 Ubuntu 虚拟磁盘。未改变的地图和知识库本次不重复放入。新包不重新复制整个 WSL 磁盘；旧环境恢复后，需要重新构建本次新增的 `hz_hunter_full_description`，并核对软件和图形依赖。当前磁盘与旧包磁盘之间的内部变化未做块级增量备份。

本包只包含项目文件更新及交接记录，没有新做 Codex 聊天数据库快照；不要把新包当成自动恢复所有近期聊天的工具。旧包内含当时的 Codex 备份，是否恢复到台式机现有应用应单独核对，不能直接覆盖正在使用的数据库。

本次仅本地打包、校验，没有执行台式机恢复，也没有启动实车或发布运动命令。默认静态/暂停及实车运动授权限制继续有效。更详细的配置见合并后的 `outputs/hunter_sim_handover_20261031/仿真进度与台式机交接.md`。
'''
    write_text(PACKAGE / '00_先读我.md', readme)
    write_text(PACKAGE / '01_给台式机Agent的恢复说明.md', '''# 给台式机 Agent 的恢复说明

用户只传过 2026-10-21 的旧完整包，尚未恢复；本次增量直接以该包为基线，不能假设台式机已经有 10 月 28 日更新或当前完整模型。

## 先核对，再恢复与合并

- 检查旧 ZIP 的 SHA256，应为 `d38c199fd1e5442eac2dcd707bd8eadb45d4b50fce2273e7ab2b21a89e0ce734`；核对本增量 ZIP 的旁置 `.sha256` 及包内清单。
- 阅读旧包恢复说明，确认台式机实际目标项目目录、已有文件和 WSL 状态。原计划为 `D:\\rob-memory`。先恢复旧项目基线，再按本包 `项目增量` 的相对路径合并；不要先合并后运行旧整包恢复，避免把新版本回退。
- 对修改文件：目标等于 `previous_sha256` 时才能视为匹配旧基线；目标已等于新哈希则跳过。目标另有变化时保留两版后比较，不直接覆盖。新增文件遇到同名不同内容时同样保留两版。本包没有任何自动删除要求。
- 本包不提供自动覆盖程序。旧包中的 Codex 备份与项目资料分开处理；不要在 Agent 正在运行时覆盖应用数据库，也不要未经用户确认丢弃台式机现有聊天。

## 本次最新任务状态

主仿真已经升级到 HUNTER 2.0 分体 CAD 和本车传感器上装，包含四个滚动关节、两个前轮转向关节；主入口默认暂停。相机和 CH104 的坐标关系已按小车导出的配置与源码核对并应用。70 项离线检查和独立静态传感器采样通过；完整模型动态驾驶、动态建图和新实验室地图接入尚未验收。仿真 IMU 当前 50 Hz，与车端 YAML 注释的 100 Hz 假设尚未对齐。

以 `项目增量/outputs/hunter_sim_handover_20261031/仿真进度与台式机交接.md` 和 `项目增量/outputs/hunter_sensor_parameters_20261030/README.md` 的当前说明为准。较早的模型升级、验证 JSON 和日志保留各自的历史状态，不能据其旧哈希或旧计数覆盖当前模型。

## WSL 与路径适配

- 10 月 21 日包包含当时的 Ubuntu 虚拟磁盘；本增量没有整盘更新。恢复后检查 WSL2 / Ubuntu 22.04 / ROS Humble / Fortress 6.18、Ogre1、CycloneDDS、ros_gz_bridge、robot_state_publisher、pointcloud_to_laserscan、colcon 等是否可用。
- 当前源文件保留本机原字节，很多运行路径是 `F:\\rob-memory` / `/mnt/f/rob-memory`，发行版 `Ubuntu-22.04`、用户 `aphelios`、工作区 `/home/aphelios/hz_sim_ws`。目标使用 D 盘时，需要按实际目录修改运行入口、场景网格 URI、检查器和有关封存清单；不要无差别替换历史证据或简单关闭检查。
- 旧 WSL 快照没有本次新模型的安装状态。先核对 `sim/hz_hunter_full_description` 的完整源码和清单，再在目标 Linux 工作区安装构建这个数据包。不要直接搬另一台机器的 build/install 符号链接，也不要盲目运行假设已安装某个过渡版本的 `sync_personal_package.py`。
- 完成目标路径适配后，再做相应离线测试和入口只读检查，保留 ROS 域 73、本机通信、仅 Gazebo→ROS 观察桥和默认暂停设置；重新核对台式机显卡，不能照搬笔记本 GPU 检查结论。

## 用户运动限制

小车共用工作区只读。没有用户明确下令实车移动，不提供或执行可能使实车移动的命令；涉及移动先提醒并等授权。此前只授权过虚拟车低速测试，不表示允许实车移动。本次交接不启动底盘、CAN、导航或运动程序。
''')

    package_files = sorted(p for p in PACKAGE.rglob('*') if p.is_file())
    records = [{'path': p.relative_to(PACKAGE).as_posix(), 'bytes': p.stat().st_size,
                'sha256': sha(p)} for p in package_files]
    package_manifest_path = PACKAGE / '04_包内文件校验.json'
    write_json(package_manifest_path, {'format': 'hunter_increment_content_hashes_v1',
                                     'files': records, 'manifest_self_hash_in_external_verification': True})
    records.append({'path': package_manifest_path.name, 'bytes': package_manifest_path.stat().st_size,
                    'sha256': sha(package_manifest_path)})
    expected = {PACKAGE_NAME + '/' + x['path']: x for x in records}
    emit('zip', package_files=len(expected))
    with zipfile.ZipFile(ARCHIVE, 'x', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True, strict_timestamps=False) as archive:
        for relative in sorted(expected):
            path = PACKAGE / relative[len(PACKAGE_NAME) + 1:]
            archive.write(path, relative)
    emit('verify_archive')
    with zipfile.ZipFile(ARCHIVE) as archive:
        members = archive.namelist()
        if len(members) != len(expected) or set(members) != set(expected):
            raise ValueError('ZIP member list mismatch or duplicate member')
        for relative in members:
            item = expected[relative]
            info = archive.getinfo(relative)
            if info.file_size != item['bytes']:
                raise ValueError('ZIP member size mismatch')
            with archive.open(info) as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != item['sha256']:
                    raise ValueError('ZIP member SHA256 mismatch: ' + relative)
    archive_sha = sha(ARCHIVE)
    write_text(Path(str(ARCHIVE) + '.sha256'), archive_sha + '  ' + ARCHIVE.name + '\n')
    proof = {'ok': True, 'baseline_archive_sha256': BASE_SHA,
             'baseline_manifest_matches_archive': True, 'archive': str(ARCHIVE),
             'archive_bytes': ARCHIVE.stat().st_size, 'archive_sha256': archive_sha,
             'verified_zip_files': len(expected), 'project_delta_files': len(changes),
             'project_delta_bytes': delta_bytes, 'added_files': manifest['added_files'],
             'changed_files': manifest['changed_files'], 'unchanged_project_files': unchanged_count,
             'baseline_missing_files_recorded_without_delete': len(missing),
             'wsl_virtual_disk_included': False, 'new_codex_database_included': False,
             'requires_oct28_package': False, 'source_files_modified_by_packager': False,
             'desktop_restore_executed': False, 'robot_commands_sent': False,
             'completed_at': datetime.now().astimezone().isoformat(timespec='seconds')}
    write_json(OUTPUT / 'verification.json', proof)
    emit('complete', **proof)


if __name__ == '__main__':
    main()
