"""Update only the notebook GPU selection in the recovered user's shell."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import stat

REPORT = Path('/mnt/d/rob-memory/outputs/hunter_desktop_restore_20261031')
TARGET = Path('/home/aphelios/.bashrc')


def main():
    if pwd.getpwuid(os.getuid()).pw_name != 'aphelios' or os.environ.get('WSL_DISTRO_NAME') != 'Ubuntu-22.04':
        raise RuntimeError('Only the recovered personal Ubuntu user may update this profile.')
    if TARGET.is_symlink():
        raise RuntimeError('Refusing to modify a redirected shell profile.')
    old = TARGET.read_bytes()
    before = b'export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA'
    after = b"export MESA_D3D12_DEFAULT_ADAPTER_NAME='Radeon RX 9070 XT'"
    if old.count(before) != 1:
        raise RuntimeError('Expected exactly one original notebook GPU selection.')
    backup = REPORT / 'linux-dotfiles/bashrc.before-desktop-gpu'
    backup.parent.mkdir(exist_ok=True)
    if backup.exists():
        raise RuntimeError('Shell profile backup already exists.')
    shutil.copy2(TARGET, backup)
    new = old.replace(before, after)
    temporary = TARGET.with_name('.bashrc.desktop-gpu.tmp')
    with temporary.open('xb') as stream:
        stream.write(new)
    os.chmod(temporary, stat.S_IMODE(TARGET.stat().st_mode))
    if TARGET.read_bytes() != old:
        raise RuntimeError('Shell profile changed during the update.')
    temporary.replace(TARGET)
    result = {'profile':str(TARGET),'backup':str(backup),'before_sha256':hashlib.sha256(old).hexdigest(),
              'after_sha256':hashlib.sha256(new).hexdigest(),'only_gpu_selection_changed':True}
    (REPORT/'linux-graphics-profile.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__': main()
