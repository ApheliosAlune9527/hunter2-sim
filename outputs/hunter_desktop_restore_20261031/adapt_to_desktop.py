"""Reviewed desktop-only path changes; preserve source assets and old evidence."""
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT = Path(r'D:\rob-memory')
REPORT = ROOT / 'outputs/hunter_desktop_restore_20261031'
BACKUP = REPORT / 'before_d_drive_adaptation'
TEXT_FILES = (
    'sim/tools/start_hunter_full_scene.ps1',
    'sim/tools/start_hunter_full_scene.bash',
    'sim/tools/start_control_scene_logged.bash',
    'sim/tools/full_scene_session.py',
    'sim/tools/check_full_entry.py',
    'sim/tools/check_hunter_full_scene.py',
    'sim/launch/hunter_full_ros.launch.py',
    'sim/tools/test_hunter_full_scene.py',
    'sim/tools/test_full_entry.py',
    'wsl/hz_sim_env.bash',
    'sim/README.md',
    'sim/tools/check_ros_isolation.py',
)
GENERATED = ('sim/scenes/hz_hunter_full.sdf', 'sim/scenes/hz_hunter_full_gui.config',
             'sim/scenes/hz_hunter_full_manifest.json', 'sim/tools/hunter_full_entry_manifest.json')


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def canonical_scene(data):
    tree = ET.fromstring(data)
    for uri in tree.findall('.//mesh/uri'):
        uri.text = uri.text.replace('/mnt/f/rob-memory', '/mnt/d/rob-memory')
    return ET.canonicalize(ET.tostring(tree, encoding='unicode'), strip_text=True)


def main():
    if ROOT.resolve() != ROOT or BACKUP.exists():
        raise RuntimeError('Unexpected project path or an existing adaptation backup.')
    sys.path.insert(0, str(ROOT / 'sim/tools'))
    import check_full_entry as entry
    import check_hunter_full_scene as scene
    entry.validate_manifest(entry.read_json(ROOT / entry.MANIFEST_REL), ROOT)
    scene.check_scene()
    package = ROOT / 'sim/hz_hunter_full_description'
    package_hashes = {str(p.relative_to(ROOT)):sha(p) for p in package.rglob('*') if p.is_file()}
    original = {}
    for rel in (*TEXT_FILES, *GENERATED):
        file = ROOT / rel
        backup = BACKUP / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, backup)
        original[rel] = sha(file)
    for rel in TEXT_FILES:
        file = ROOT / rel
        text = file.read_bytes().decode('utf-8')
        text = text.replace('/mnt/f/rob-memory', '/mnt/d/rob-memory')
        text = text.replace('F:\\rob-memory', 'D:\\rob-memory').replace('F:/rob-memory', 'D:/rob-memory')
        if rel.endswith('check_full_entry.py'):
            text = text.replace('固定 F 盘工作目录', '固定 D 盘工作目录')
        if rel.endswith('full_scene_session.py'):
            text = text.replace("'outputs/hunter_model_upgrade_20261030/references/user_logs'",
                                "'outputs/hunter_desktop_restore_20261031/sessions'")
        if rel == 'sim/README.md':
            text = text.replace('outputs\\hunter_model_upgrade_20261030\\references\\user_logs',
                                'outputs\\hunter_desktop_restore_20261031\\sessions')
            text = ('> 台式机适配：运行根目录为 D:\\rob-memory；旧来源与历史验证记录仍保留笔记本原路径。'
                    'Windows 检测到 Radeon RX 9070 XT，WSL 图形渲染及 Linux 包构建尚待实际验收。\n\n' + text)
        if rel == 'wsl/hz_sim_env.bash':
            text = text.replace('export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA',
                                "# Desktop adapter selection; verify the actual WSL renderer before GUI use.\n"
                                "export MESA_D3D12_DEFAULT_ADAPTER_NAME='Radeon RX 9070 XT'")
            text = text.replace('/ 本机通信 / NVIDIA', '/ 本机通信 / Radeon RX 9070 XT（WSL 渲染待核验）')
        if rel.endswith('check_ros_isolation.py'):
            text = text.replace('import pwd\n', '').replace('import pwd\r\n', '')
            text = text.replace('def run_probe():', 'def run_probe():\n    import pwd  # Linux identity is needed only when the actual ROS probe is requested.')
        file.write_bytes(text.encode('utf-8'))
    # Reload the changed strict checker before regenerating only the current scene.
    for name in ('check_hunter_full_scene', 'build_hunter_full_scene'):
        sys.modules.pop(name, None)
    import build_hunter_full_scene as builder
    report = builder.build_scene()
    old_scene = (BACKUP / 'sim/scenes/hz_hunter_full.sdf').read_bytes()
    if canonical_scene(old_scene) != canonical_scene((ROOT / 'sim/scenes/hz_hunter_full.sdf').read_bytes()):
        raise RuntimeError('Generated desktop scene changed semantics beyond resource paths.')
    for name in ('check_full_entry', 'seal_full_entry'):
        sys.modules.pop(name, None)
    import seal_full_entry as seal
    manifest = seal.build_manifest()
    (ROOT / seal.MANIFEST_REL).write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    import check_full_entry as current_entry
    checked_seal = current_entry.validate_manifest(manifest, ROOT)
    for rel, expected in package_hashes.items():
        if sha(ROOT / rel) != expected:
            raise RuntimeError('Original model source changed unexpectedly: ' + rel)
    changes = [{'path':rel,'before_sha256':old,'after_sha256':sha(ROOT/rel)} for rel,old in original.items() if sha(ROOT/rel)!=old]
    record = {'completed_at':datetime.datetime.now().astimezone().isoformat(),
              'target_windows_root':str(ROOT),'target_linux_root':'/mnt/d/rob-memory',
              'backup':str(BACKUP),'changes':changes,'strict_scene_check':report,'entry_seal':checked_seal,
              'model_source_files_unchanged':len(package_hashes),'scene_semantics_unchanged_except_mesh_paths':True,
              'wsl_renderer_verified':False,'runtime_verified':False,'motion_commands_sent':False}
    (REPORT/'d_drive_adaptation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'adapted','changed_files':len(changes),'scene':report['status'],
                      'sealed_files':checked_seal['sealed_files'],'original_model_files_preserved':len(package_hashes)},ensure_ascii=True))


if __name__ == '__main__': main()
