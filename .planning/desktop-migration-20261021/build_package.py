from __future__ import annotations

import base64
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timezone, timedelta
import zipfile
from contextlib import closing

SOURCE = Path(r'F:\rob-memory')
PROFILE = Path(r'C:\Users\Aphelios')
OUTPUT = Path(r'F:\rob-memory-migration-20261021')
ASSETS = SOURCE / '.planning' / 'desktop-migration-20261021'
WORK = OUTPUT / '_work'
ROOT = WORK / 'rob-memory-migration'
HOME = ROOT / 'user-profile' / '.codex'
ARCHIVE = OUTPUT / 'rob-memory_迁移包_20261021.zip'
CHUNK = 4 * 1024 * 1024
ZONE = timezone(timedelta(hours=8))
EXCLUDED_DIRS = {
    '.tmp', '.sandbox', '.sandbox-bin', '.sandbox-secrets', 'cache', 'tmp',
    'browser', 'computer-use', 'process_manager', 'project-metadata-locks',
    'thread-writer-locks', 'rollout-migrations',
}
EXCLUDED_FILES = {
    'auth.json', 'cap_sid', 'installation_id', 'chrome-native-hosts-v2.json',
    'models_cache.json', 'logs_2.sqlite', 'queue_1.sqlite',
}
report = {
    'created_at': datetime.now(ZONE).isoformat(),
    'source_project': str(SOURCE), 'target_project': r'D:\rob-memory',
    'source_profile': str(PROFILE), 'target_profile': r'C:\Users\ASUS',
    'excluded': [], 'directory_links': [], 'sqlite_backups': [],
    'path_adaptations': [], 'transcript_tail_truncations': [],
    'project_files_preserved_verbatim': True,
    'snapshot_limit': 'Records written after this snapshot, including later packaging messages, are not included.',
}


def emit(stage, **values):
    payload = {'stage': stage, 'time': datetime.now(ZONE).isoformat(), **values}
    print(json.dumps(payload, ensure_ascii=False), flush=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / 'packaging-status.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def file_entries(root):
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs.sort(); files.sort()
        for name in list(dirs):
            p = Path(base) / name
            if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
                report['directory_links'].append({'source': str(p), 'target': str(p.resolve()), 'reason': 'App-managed runtime link; do not recursively package its target.'})
                dirs.remove(name)
        for name in files:
            yield Path(base) / name


def exclude_codex(relative):
    parts = relative.parts
    if parts[0] in EXCLUDED_DIRS:
        return True
    name = parts[-1]
    if name in EXCLUDED_FILES or name.endswith(('-wal', '-shm', '-journal', '.lock', '.guard', '.log')):
        return True
    if name.startswith('..codex-global-state') or name.startswith('.codex-provisioning-'):
        return True
    return False


def backup_sqlite(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 90
    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise TimeoutError(f'SQLite backup deadline: {source}')
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=15)) as src:
        with closing(sqlite3.connect(target)) as dst:
            src.backup(dst, pages=256, progress=progress, sleep=0.05)
            result = [r[0] for r in dst.execute('PRAGMA integrity_check')]
            if result != ['ok']:
                raise RuntimeError(f'Invalid database snapshot: {source}: {result}')
    report['sqlite_backups'].append({'source': str(source), 'snapshot': str(target.relative_to(ROOT)), 'integrity_check': result})


def copy_snapshot_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if source.suffix.lower() == '.jsonl':
        size = target.stat().st_size
        if size:
            with target.open('r+b') as f:
                f.seek(max(0, size - 8 * 1024 * 1024))
                tail = f.read()
                if not tail.endswith(b'\n'):
                    last = tail.rfind(b'\n')
                    candidate = tail[last + 1:]
                    try:
                        json.loads(candidate)
                    except (ValueError, UnicodeDecodeError):
                        if last < 0:
                            raise RuntimeError(f'Incomplete oversized JSONL tail: {source}')
                        new_size = size - len(tail) + last + 1
                        f.truncate(new_size)
                        report['transcript_tail_truncations'].append({'source': str(source), 'discarded_incomplete_bytes': size-new_size})


PAIRS = [
    (r'F:\rob-memory', r'D:\rob-memory'), ('F:/rob-memory', 'D:/rob-memory'),
    ('/mnt/f/rob-memory', '/mnt/d/rob-memory'),
    (r'C:\Users\Aphelios', r'C:\Users\ASUS'), ('C:/Users/Aphelios', 'C:/Users/ASUS'),
]


def remap_text(value):
    for old, new in PAIRS:
        value = re.sub(re.escape(old), lambda match, n=new: n, value, flags=re.IGNORECASE)
    return value


def remap_object(value):
    if isinstance(value, str): return remap_text(value)
    if isinstance(value, list): return [remap_object(item) for item in value]
    if isinstance(value, dict): return {remap_text(key): remap_object(item) for key, item in value.items()}
    return value


def remap_cell(value):
    if not isinstance(value, str): return value
    if value.lstrip().startswith(('{', '[')):
        try:
            data = json.loads(value)
            mapped = remap_object(data)
            return value if mapped == data else json.dumps(mapped, ensure_ascii=False, separators=(',', ':'))
        except ValueError:
            pass
    return remap_text(value)


def preserve_original(path):
    target = ROOT / 'original-codex-metadata' / path.relative_to(HOME)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def adapt_database(path, selections):
    if not path.exists(): return
    preserve_original(path)
    with closing(sqlite3.connect(path)) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table, wanted in selections.items():
            if table not in tables: continue
            existing = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
            columns = [c for c in wanted if c in existing]
            if not columns: continue
            selector = ','.join('"'+c+'"' for c in columns)
            updates = 0
            for row in conn.execute(f'SELECT rowid,{selector} FROM "{table}"').fetchall():
                values = [remap_cell(value) for value in row[1:]]
                if values != list(row[1:]):
                    setters = ','.join('"'+c+'"=?' for c in columns)
                    conn.execute(f'UPDATE "{table}" SET {setters} WHERE rowid=?', [*values, row[0]])
                    updates += 1
            if updates:
                report['path_adaptations'].append({'file': str(path.relative_to(ROOT)), 'table': table, 'rows': updates})
        conn.commit()
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError(f'Adapted database integrity failed: {path}')


def snapshot_codex():
    original_home = PROFILE / '.codex'
    files = []
    for p in file_entries(original_home):
        rel = p.relative_to(original_home)
        if exclude_codex(rel):
            report['excluded'].append({'source': str(p), 'reason': 'Authentication, disposable machine state, cache, lock/WAL or diagnostic/pending-job data.'})
        else:
            files.append((p, HOME / rel))
    # Backup indexes first. Transcripts are captured afterwards so their copied
    # bytes include at least the already-indexed prefix of the current turn.
    databases = []
    for source, target in files:
        if source.suffix.lower() in {'.db', '.sqlite', '.sqlite3'}:
            with source.open('rb') as f:
                if f.read(16) == b'SQLite format 3\0': databases.append((source, target))
    database_paths = {s for s, _ in databases}
    for source, target in databases: backup_sqlite(source, target)
    for source, target in files:
        if source not in database_paths: copy_snapshot_file(source, target)
    agents = ROOT / 'user-profile' / '.agents'
    for p in file_entries(PROFILE / '.agents'):
        copy_snapshot_file(p, agents / p.relative_to(PROFILE / '.agents'))
    roaming = PROFILE / 'AppData' / 'Roaming' / 'Codex' / 'web' / 'Codex'
    for name in ['artifact-sessions']:
        source = roaming / name
        if source.exists():
            for p in file_entries(source):
                if p.name.endswith(('.lock', '.log')): continue
                copy_snapshot_file(p, ROOT / 'app-supplement' / name / p.relative_to(source))
    for rel in ['Default/Preferences', 'browser-sidebar-page-states.json']:
        p = roaming / rel
        if p.is_file(): copy_snapshot_file(p, ROOT / 'app-supplement' / 'preferences-reference' / rel)
    report['excluded'].append({'source': str(roaming), 'reason': 'Only artifact sessions and preference references copied. Browser profiles, live LevelDB stores, cookies, login databases, caches and OS-encrypted state are not portable.'})


def adapt_metadata():
    adapt_database(HOME / 'state_5.sqlite', {
        'threads': ['cwd','rollout_path','sandbox_policy','agent_path'],
        'projects': ['metadata'], 'project_roots': ['path'],
        'thread_attachments': ['identity_key','payload'],
        'rollout_migration_skipped_rollouts': ['rollout_path'],
    })
    adapt_database(HOME / 'sqlite' / 'codex-dev.db', {
        'local_thread_catalog': ['cwd','source_detail','thread_source'],
        'automations': ['cwds','local_environment_config_path'],
        'automation_runs': ['source_cwd'],
    })
    state = HOME / '.codex-global-state.json'
    if state.exists():
        preserve_original(state)
        data = json.loads(state.read_text(encoding='utf-8'))
        data = remap_object(data)
        for key in ['electron-main-window-bounds','electron-avatar-overlay-bounds','electron-local-remote-control-installation-id']:
            data.pop(key, None)
        state.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        report['path_adaptations'].append({'file': str(state.relative_to(ROOT)), 'kind': 'Operational workspace/profile paths; reset window/device identity hints.'})
    config = HOME / 'config.toml'
    if config.exists():
        preserve_original(config)
        value = config.read_text(encoding='utf-8-sig')
        for old, new in PAIRS:
            value = re.sub(re.escape(old.replace('\\','\\\\')), lambda m,n=new.replace('\\','\\\\'): n, value, flags=re.IGNORECASE)
        config.write_text(remap_text(value), encoding='utf-8')
    header_backups = {}
    for folder in ['sessions','archived_sessions']:
        for p in (HOME / folder).rglob('*.jsonl'):
            with p.open('rb') as f:
                first = f.readline()
            changed = first
            for old in [r'F:\rob-memory', 'F:/rob-memory']:
                encoded = json.dumps(old)[1:-1].encode('ascii')
                changed = re.sub(re.escape(encoded), lambda m:b'D'+m.group(0)[1:], changed, flags=re.IGNORECASE)
            if changed != first:
                if len(changed) != len(first): raise AssertionError('Transcript offsets must remain unchanged')
                header_backups[str(p.relative_to(HOME))] = base64.b64encode(first).decode('ascii')
                with p.open('r+b') as f: f.write(changed)
    backup = ROOT / 'original-codex-metadata' / 'original-session-headers.base64.json'
    backup.write_text(json.dumps(header_backups, ensure_ascii=False, indent=2), encoding='utf-8')
    report['path_adaptations'].append({'kind': 'First session metadata line: F: to D:, byte length unchanged; conversation records and indexed offsets preserved.', 'files': len(header_backups)})
    with closing(sqlite3.connect(HOME / 'state_5.sqlite')) as c:
        report['indexed_conversations'] = c.execute('SELECT count(*) FROM threads').fetchone()[0]
        report['target_project_root_records'] = c.execute('SELECT count(*) FROM project_roots WHERE lower(path)=?', (r'd:\rob-memory',)).fetchone()[0]
        missing = []
        for thread_id, rollout in c.execute('SELECT id,rollout_path FROM threads'):
            try:
                relative = Path(rollout.removeprefix('\\\\?\\')).relative_to(Path(r'C:\Users\ASUS\.codex'))
                plain = HOME / relative
                compressed = Path(str(plain) + '.zst')
                if not plain.is_file() and not compressed.is_file(): missing.append(thread_id)
            except ValueError:
                missing.append(thread_id)
        report['indexed_rollout_files_missing'] = missing
        if missing: raise RuntimeError(f'{len(missing)} indexed conversation files missing from snapshot')
    if report['target_project_root_records'] != 1:
        raise RuntimeError('Destination project root was not adapted correctly')
    report['normal_transcript_files'] = len(list((HOME/'sessions').rglob('*.jsonl'))) + len(list((HOME/'sessions').rglob('*.jsonl.zst')))
    report['archived_transcript_files'] = len(list((HOME/'archived_sessions').rglob('*.jsonl'))) + len(list((HOME/'archived_sessions').rglob('*.jsonl.zst')))
    report['compressed_transcripts_preserved_verbatim'] = len(list(HOME.rglob('*.jsonl.zst')))
    report['attachment_files'] = sum(p.is_file() for p in (HOME/'attachments').rglob('*'))


def zip_and_verify(project):
    items = [(p, 'rob-memory-migration/rob-memory/' + p.relative_to(SOURCE).as_posix()) for p in project]
    items += [(p, 'rob-memory-migration/' + p.relative_to(ROOT).as_posix()) for p in file_entries(ROOT)]
    items.sort(key=lambda entry: entry[1])
    report['project_bytes'] = sum(p.stat().st_size for p in project)
    report['profile_bytes'] = sum(p.stat().st_size for p in file_entries(ROOT/'user-profile'))
    report['total_payload_bytes'] = sum(p.stat().st_size for p, _ in items)
    report['files'] = []
    copied = 0; last_update = time.monotonic()
    stored = {'.zip','.7z','.gz','.xz','.zst','.png','.jpg','.jpeg','.mp4','.pptx','.docx','.xlsx','.ico'}
    with zipfile.ZipFile(ARCHIVE, 'w', allowZip64=True, compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for index, (path, arcname) in enumerate(items, 1):
            before = path.stat()
            info = zipfile.ZipInfo.from_file(path, arcname, strict_timestamps=False)
            info.compress_type = zipfile.ZIP_STORED if path.suffix.lower() in stored else zipfile.ZIP_DEFLATED
            info._compresslevel = 1
            digest = hashlib.sha256(); written = 0
            with path.open('rb') as source, z.open(info, 'w', force_zip64=True) as dest:
                while block := source.read(CHUNK):
                    dest.write(block); digest.update(block); written += len(block); copied += len(block)
                    if time.monotonic()-last_update > 15:
                        emit('archiving', files_done=index, files_total=len(items), bytes_done=copied, bytes_total=report['total_payload_bytes'])
                        last_update = time.monotonic()
            after = path.stat()
            if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns or written != before.st_size:
                raise RuntimeError(f'Source changed while archiving: {path}')
            report['files'].append({'path':arcname,'bytes':written,'sha256':digest.hexdigest()})
        report['archive_file_count'] = len(items) + 1
        report['snapshot_completed_at'] = datetime.now(ZONE).isoformat()
        data = json.dumps(report, ensure_ascii=False, indent=2).encode('utf-8')
        z.writestr('rob-memory-migration/MANIFEST.json', data)
    (OUTPUT/'MANIFEST.json').write_bytes(data)
    emit('verifying_archive', archive_bytes=ARCHIVE.stat().st_size, files=len(items)+1)
    expected = {item['path']:item for item in report['files']}
    verified = 0; bytes_verified = 0; last_update = time.monotonic()
    with zipfile.ZipFile(ARCHIVE) as z:
        if len(z.namelist()) != len(expected)+1 or len(set(z.namelist())) != len(z.namelist()):
            raise RuntimeError('Unexpected or duplicate archive entries')
        for info in z.infolist():
            digest=hashlib.sha256(); size=0
            with z.open(info) as f:
                while block := f.read(CHUNK):
                    digest.update(block); size+=len(block); bytes_verified+=len(block)
                    if time.monotonic()-last_update>15:
                        emit('verifying_archive', files_done=verified, files_total=len(expected)+1, bytes_done=bytes_verified)
                        last_update=time.monotonic()
            if info.filename in expected:
                target=expected[info.filename]
                if size != target['bytes'] or digest.hexdigest() != target['sha256']:
                    raise RuntimeError(f'Archive hash mismatch: {info.filename}')
            elif info.filename != 'rob-memory-migration/MANIFEST.json':
                raise RuntimeError(f'Unexpected archive entry: {info.filename}')
            verified+=1
    emit('hashing_archive', verified_entries=verified)
    digest=hashlib.sha256()
    with ARCHIVE.open('rb') as f:
        while block:=f.read(CHUNK): digest.update(block)
    sha=digest.hexdigest()
    (OUTPUT/(ARCHIVE.name+'.sha256')).write_text(sha+'  '+ARCHIVE.name+'\n',encoding='utf-8-sig')
    result={'archive':str(ARCHIVE),'archive_bytes':ARCHIVE.stat().st_size,'sha256':sha,'verified_entries':verified,'verified_payload_bytes':bytes_verified,'indexed_conversations':report['indexed_conversations'],'normal_transcripts':report['normal_transcript_files'],'archived_transcripts':report['archived_transcript_files'],'attachments':report['attachment_files'],'database_snapshots':len(report['sqlite_backups']),'target_project_root_records':report['target_project_root_records'],'excluded_items':len(report['excluded']),'directory_links':len(report['directory_links']),'completed_at':datetime.now(ZONE).isoformat()}
    (OUTPUT/'VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    emit('complete',**result)


def main():
    if OUTPUT.exists(): raise FileExistsError(f'Output already exists: {OUTPUT}')
    if OUTPUT.is_relative_to(SOURCE): raise RuntimeError('Archive output must be outside source project')
    running = subprocess.run(['wsl.exe','--list','--running','--quiet'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout
    running = running.decode('utf-16le' if b'\x00' in running else 'utf-8',errors='replace')
    if 'Ubuntu-22.04' in running: raise RuntimeError('Ubuntu is running; stop it before capturing the VHDX')
    OUTPUT.mkdir(); ROOT.mkdir(parents=True)
    emit('snapshotting_codex')
    snapshot_codex(); adapt_metadata()
    for name in ['Restore-Windows.ps1','Restore-Ubuntu.ps1','README_先读我.txt']:
        text=(ASSETS/name).read_text(encoding='utf-8-sig')
        (ROOT/name).write_text(text,encoding='utf-8-sig' if name.endswith('.ps1') else 'utf-8')
    shutil.copy2(ROOT/'README_先读我.txt',OUTPUT/'README_先读我.txt')
    emit('codex_snapshot_ready',conversations=report['indexed_conversations'],databases=len(report['sqlite_backups']))
    project=list(file_entries(SOURCE))
    report['project_regular_files']=len(project)
    zip_and_verify(project)


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        if OUTPUT.exists():
            (OUTPUT/'PACKAGING_ERROR.txt').write_text(repr(exc),encoding='utf-8')
        print(json.dumps({'stage':'failed','error':str(exc)},ensure_ascii=False),flush=True)
        raise
