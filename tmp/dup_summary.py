"""Duplicate summary for outputs/, with the archived increment snapshot excluded."""

import hashlib
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"D:\rob-memory\outputs")
EXCLUDE = "hunter_increment_since_20261021_20261031"


def main() -> int:
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        if EXCLUDE in dirpath:
            dirnames[:] = []
            continue
        for name in filenames:
            fp = Path(dirpath) / name
            try:
                st = fp.stat()
            except OSError:
                continue
            if st.st_size:
                files.append((fp, st.st_size))

    by_size = defaultdict(list)
    for fp, size in files:
        by_size[size].append(fp)

    groups = []
    for size, same in by_size.items():
        if len(same) < 2:
            continue
        by_hash = defaultdict(list)
        for fp in same:
            by_hash[hashlib.sha256(fp.read_bytes()).hexdigest()].append(fp)
        for h, dup in by_hash.items():
            if len(dup) > 1:
                groups.append((size, h, dup))

    wasted = sum(size * (len(dup) - 1) for size, _, dup in groups)
    print(f"files scanned      : {len(files)}")
    print(f"duplicate groups   : {len(groups)}")
    print(f"duplicated files   : {sum(len(d) for _, _, d in groups)}")
    print(f"reclaimable        : {wasted / 1024 / 1024:.2f} MiB")
    print("\nlargest groups:")
    groups.sort(key=lambda g: -g[0] * (len(g[2]) - 1))
    for size, h, dup in groups[:15]:
        print(f"  {len(dup):>3} x {size / 1024:>8.1f} KiB  wasted {size * (len(dup) - 1) / 1024 / 1024:>7.2f} MiB  {dup[0].relative_to(ROOT)}")
    print("\nreclaimable by top directory:")
    per_dir = defaultdict(int)
    for size, _, dup in groups:
        for fp in dup[1:]:
            per_dir[fp.relative_to(ROOT).parts[0]] += size
    for name, total in sorted(per_dir.items(), key=lambda kv: -kv[1]):
        print(f"  {total / 1024 / 1024:>8.2f} MiB  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
