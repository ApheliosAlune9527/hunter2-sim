"""Install the car package at /home/car/hz_ws/nav_fix_20261107 instead of /home/car/.

The car has a personal workspace under /home/car/hz_ws and nothing may be dropped
straight into /home/car; every absolute path inside the package is rewritten here,
the checksum list is regenerated (it covers the edited files), and the tarball is
rebuilt so the user only transfers one file.
"""
import hashlib
import pathlib
import tarfile

ROOT = pathlib.Path(r'D:\rob-memory\outputs\car_nav_fix_20261107')
OLD = '/home/car/hz_ws/nav_fix_20261107'
NEW = '/home/car/hz_ws/nav_fix_20261107'
STAGE = 'hz_nav_fix_20261107'


def read_text(p):
    raw = p.read_bytes()
    for enc in ('utf-8', 'gbk'):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise SystemExit(f'cannot decode {p.name}')


def rewrite(p):
    text, enc = read_text(p)
    n = text.count(OLD)
    if not n:
        return 0
    p.write_bytes(text.replace(OLD, NEW).encode(enc))
    return n


# verify_car.py: compare against the directory the file actually lives in, so the
# check still means something if the package is unpacked somewhere else later.
v = ROOT / 'verify_car.py'
src = v.read_text(encoding='utf-8')
old_check = """        wrong_root = [v for v in bts if not v.startswith('/home/car/hz_ws/nav_fix_20261107/')]"""
new_check = """        wrong_root = [v for v in bts if os.path.dirname(v) != HERE]"""
if old_check in src:
    src = src.replace(old_check, new_check)
    v.write_text(src, encoding='utf-8')

counts = {}
for p in sorted(ROOT.iterdir()):
    if p.is_file() and p.suffix.lower() not in ('.pgm',):
        counts[p.name] = rewrite(p)
print('rewritten:', {k: c for k, c in counts.items() if c})

# SHA256SUMS covers everything except itself and the tarball.
lines = []
for p in sorted(ROOT.iterdir()):
    if p.is_file() and p.name != 'SHA256SUMS':
        lines.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}')
(ROOT / 'SHA256SUMS').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('checksummed', len(lines), 'files')

tarball = ROOT.parent / 'car_nav_fix_20261107_package.tar.gz'
with tarfile.open(tarball, 'w:gz') as tf:
    tf.add(ROOT, arcname=STAGE)
digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
print('tarball', tarball.name, tarball.stat().st_size, 'bytes')
print('sha256', digest)
