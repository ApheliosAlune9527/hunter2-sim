"""Copy verified data-package sources into the recovered personal workspace."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import uuid

ROOT = Path('/mnt/d/rob-memory')
SOURCE = ROOT / 'sim/hz_hunter_full_description'
NATIVE = Path('/home/aphelios/hz_sim_ws/src/hz_hunter_full_description')
REPORT = ROOT / 'outputs/hunter_desktop_restore_20261031'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def validate(directory, expected):
    if directory.is_symlink() or directory.resolve() != directory:
        raise RuntimeError('Native source must be an independent directory, not an imported symlink.')
    files = {p.relative_to(directory).as_posix():p for p in directory.rglob('*') if p.is_file()}
    if set(files) != set(expected):
        raise RuntimeError('Package file set differs; preserve and compare it before building.')
    for rel,file in files.items():
        if file.is_symlink() or sha(file) != expected[rel]:
            raise RuntimeError('Package resource differs: ' + rel)


def main():
    if pwd.getpwuid(os.getuid()).pw_name != 'aphelios' or os.environ.get('WSL_DISTRO_NAME') != 'Ubuntu-22.04':
        raise RuntimeError('This build preparation is only for the personal recovered Ubuntu user.')
    manifest = json.loads((SOURCE/'source_manifest.json').read_text(encoding='utf-8'))
    expected = {entry['path']:entry['sha256'] for entry in manifest['outputs']}
    expected['source_manifest.json'] = sha(SOURCE/'source_manifest.json')
    validate(SOURCE, expected)
    if NATIVE.exists():
        validate(NATIVE, expected)
        action = 'already_identical'
    else:
        if NATIVE.parent.resolve() != NATIVE.parent or not NATIVE.parent.is_dir():
            raise RuntimeError('Personal workspace src directory is missing or redirects elsewhere.')
        temporary = NATIVE.parent.parent/('.desktop-full-model-staging-'+uuid.uuid4().hex)
        shutil.copytree(SOURCE, temporary, symlinks=True)
        validate(temporary, expected)
        if NATIVE.exists():
            raise RuntimeError('Native package appeared during preparation; preserve both copies.')
        temporary.rename(NATIVE)
        action = 'created_verified_native_source'
    record = {'action':action,'source':str(SOURCE),'native_source':str(NATIVE),
              'verified_files':len(expected),'copied_build_or_install_symlinks':False}
    (REPORT/'native-model-preparation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record))


if __name__ == '__main__': main()
