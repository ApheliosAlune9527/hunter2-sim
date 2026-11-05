"""Audit supplied model references using files only; do not import robot code."""
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET


SOURCE = Path('F:/rob-memory-migration-20261028/_staging/Hunter_increment_20261028')
OUTPUT = Path('F:/rob-memory/outputs/hunter_model_update_20261030')
ARCHIVE = Path('F:/rob-memory-migration-20261028/Hunter_项目增量与聊天_20261028.zip')
REFERENCE = Path('F:/rob-memory/outputs/hunter_sim_execution_20261012/references/hunter_reference_20261013.urdf')
ASSETS = Path('F:/rob-memory/robot_assets/hunter_from_car_20261013_qjkgbbq5')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def transform(joint):
    origin = joint.find('origin')
    xyz = [float(v) for v in origin.get('xyz', '0 0 0').split()] if origin is not None else [0.0] * 3
    rpy = [float(v) for v in origin.get('rpy', '0 0 0').split()] if origin is not None else [0.0] * 3
    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return [[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr, xyz[0]],
            [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr, xyz[1]],
            [-sp, cp*sr, cp*cr, xyz[2]], [0, 0, 0, 1]]


def multiply(left, right):
    return [[sum(left[i][k] * right[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    copies = OUTPUT / 'references'
    copies.mkdir(exist_ok=True)
    checksums = {}
    for line in (SOURCE / '03_SHA256校验表.txt').read_text(encoding='utf-8-sig').splitlines():
        match = re.fullmatch(r'([a-fA-F0-9]{64})\s+(.+)', line)
        if match:
            checksums[match[2].replace('\\', '/')] = match[1].lower()
    selected = {
        '00_先读我.md': 'migration_readme.md',
        '01_给台式机Agent的交接说明.md': 'migration_handoff.md',
        '02_文件清单.json': 'migration_manifest.json',
        '聊天记录/临时侧聊摘要.md': 'side_chat_summary.md',
        '聊天记录/侧聊截图/codex-clipboard-86132566-73a0-4519-bb12-e408040be0da.jpg': 'hunter_nameplate.jpg',
        '聊天记录/截图附件/9ea5b7de158bd6bff7f59d17.jpg': 'hunter_installed_photo.jpg',
        '项目增量/findings.md': 'migration_nav_findings.md',
    }
    evidence = []
    for relative, name in selected.items():
        original = SOURCE / relative
        actual = digest(original)
        assert actual == checksums[relative], f'Checksum mismatch: {relative}'
        target = copies / name
        if target.exists():
            assert digest(target) == actual, f'Existing evidence differs: {target}'
        else:
            shutil.copyfile(original, target)
        assert digest(target) == actual
        evidence.append({'source': str(original), 'copy': str(target), 'sha256': actual})

    expected_zip = Path(str(ARCHIVE) + '.sha256').read_text(encoding='utf-8-sig').split()[0].lower()
    archive_hash = digest(ARCHIVE)
    assert archive_hash == expected_zip
    manifest = json.loads((SOURCE / '02_文件清单.json').read_text(encoding='utf-8-sig'))
    project_checks = []
    for entry in manifest['project_files']:
        path = (SOURCE / '项目增量' / entry['relative_path']).resolve()
        assert path.is_relative_to((SOURCE / '项目增量').resolve())
        assert digest(path) == entry['current_sha256'], f'Increment mismatch: {path}'
        project_checks.append(entry['relative_path'])
    geometry_extensions = {'.urdf', '.xacro', '.sdf', '.stl', '.dae', '.obj', '.glb', '.gltf', '.ply'}
    increment_geometry = [p for p in project_checks if Path(p).suffix.lower() in geometry_extensions]

    xml = REFERENCE.read_text(encoding='utf-8')
    canonical_hash = hashlib.sha256(ET.canonicalize(xml, strip_text=True).encode('utf-8')).hexdigest()
    handoff = (SOURCE / '01_给台式机Agent的交接说明.md').read_text(encoding='utf-8-sig')
    recorded_hash = re.search(r'规范化 SHA256 一致[：:]\s*([a-f0-9]{64})', handoff).group(1)
    assert canonical_hash == recorded_hash
    robot = ET.fromstring(xml)
    joints = robot.findall('joint')
    by_child = {j.find('child').get('link'): j for j in joints}
    chain = []
    current = 'hesai_lidar'
    while current != 'base_link':
        joint = by_child[current]
        assert joint.get('type') == 'fixed'
        chain.append(joint)
        current = joint.find('parent').get('link')
    tf = [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]
    for joint in reversed(chain):
        tf = multiply(tf, transform(joint))
    position = [round(tf[i][3], 9) for i in range(3)]
    yaw = round(math.degrees(math.atan2(tf[1][0], tf[0][0])), 6)
    assert position == [0.214, 0.0, 0.69] and yaw == 90.0
    resources = []
    for uri in sorted({mesh.get('filename') for mesh in robot.findall('.//mesh')}):
        assert uri.startswith('package://')
        package, relative = uri[len('package://'):].split('/', 1)
        local = (ASSETS / package / relative).resolve()
        assert local.is_relative_to(ASSETS.resolve()) and local.is_file()
        resources.append({'uri': uri, 'local': str(local), 'sha256': digest(local)})

    report = {
        'reviewed_on': '2026-10-30', 'timezone': 'Asia/Shanghai',
        'scope': 'Static source review only; no WSL, ROS, Gazebo, driver, launch, or robot program executed.',
        'migration_root': str(SOURCE), 'archive': str(ARCHIVE),
        'archive_sha256': archive_hash, 'archive_checksum_matches': True,
        'increment_files_verified': len(project_checks), 'increment_geometry_files': increment_geometry,
        'selected_evidence_checks': evidence,
        'nameplate_visual_confirmation': {'brand': 'AGILEX', 'model': 'HUNTER 2.0', 'text': '阿克曼型移动底盘'},
        'urdf': {'local': str(REFERENCE), 'raw_sha256': digest(REFERENCE),
                 'canonical_method': 'xml.etree.ElementTree.canonicalize(strip_text=True), UTF-8, SHA256',
                 'canonical_sha256': canonical_hash, 'migration_reported_sha256': recorded_hash,
                 'matches_migration_record': True, 'fresh_live_robot_comparison': False,
                 'links': len(robot.findall('link')), 'joints': len(joints),
                 'fixed_joints': sum(j.get('type') == 'fixed' for j in joints),
                 'links_with_inertial': [link.get('name') for link in robot.findall('link') if link.find('inertial') is not None],
                 'mesh_resources': resources,
                 'mesh_content_matches_live_robot': 'Not established by a URDF hash; migration has no new mesh payload.'},
        'reference_model_tf': {'parent': 'base_link', 'child': 'hesai_lidar', 'translation_m': position,
                               'yaw_deg': yaw, 'joint_chain': [j.get('name') for j in reversed(chain)],
                               'meaning': 'URDF transform; historical runtime TF agrees in migration notes; not physical calibration.'},
        'official_web_reference': {'url': 'https://www.agilex.ai/products/hunter', 'checked_on': '2026-10-30',
                                   'wheelbase_m': 0.650, 'track_m': 0.605, 'maximum_speed_m_s': 1.5,
                                   'ground_clearance_m': 0.100, 'curb_mass_kg_range': [65, 72],
                                   'meaning': 'Manufacturer nominal data; not the measured, equipped robot.'},
        'handoff_2023_manual_reference': {'chassis_dimensions_mm': [980, 745, 370],
                                          'minimum_turning_radius_m': 1.6, 'ground_clearance_m': 0.105,
                                          'original_pdf_reopened_this_review': False},
        'runtime_models_modified': False, 'motion_executed': False,
        'source_project_or_codex_database_overwritten': False,
    }
    (OUTPUT / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ['archive_checksum_matches', 'increment_files_verified',
          'increment_geometry_files', 'nameplate_visual_confirmation', 'reference_model_tf',
          'runtime_models_modified', 'motion_executed']}, ensure_ascii=False))
    print(json.dumps({'canonical_sha256': canonical_hash, 'urdf_matches_migration_record': True,
                      'links': report['urdf']['links'], 'joints': report['urdf']['joints'],
                      'fixed_joints': report['urdf']['fixed_joints'], 'mesh_files_present': len(resources),
                      'selected_evidence_verified': len(evidence)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
