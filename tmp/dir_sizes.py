"""Accurate per-directory sizes under outputs/ (long-path aware), plus .build inventory."""

import os
from pathlib import Path

ROOT = Path(r"D:\rob-memory\outputs")
LONG = "\\\\?\\" + str(ROOT)


def dir_size(path: Path):
    total = 0
    count = 0
    for dirpath, _dirnames, filenames in os.walk("\\\\?\\" + str(path)):
        for name in filenames:
            try:
                total += os.stat(os.path.join(dirpath, name)).st_size
                count += 1
            except OSError:
                pass
    return total, count


def main() -> int:
    rows = []
    for entry in sorted(ROOT.iterdir()):
        if not entry.is_dir():
            continue
        size, count = dir_size(entry)
        rows.append((size, count, entry.name))
    rows.sort(reverse=True)
    grand = sum(r[0] for r in rows)
    print(f"total {grand / 1024 / 1024:.1f} MiB in {sum(r[1] for r in rows)} files\n")
    for size, count, name in rows:
        print(f"{size / 1024 / 1024:>8.2f} MiB {count:>6}  {name}")

    print("\n--- .build trees ---")
    for entry in sorted(ROOT.iterdir()):
        build = entry / ".build"
        if build.is_dir():
            size, count = dir_size(build)
            print(f"{size / 1024 / 1024:>8.2f} MiB {count:>6}  {entry.name}\\.build")
            for sub in sorted(build.iterdir()):
                if sub.is_dir():
                    s, c = dir_size(sub)
                    print(f"           {s / 1024 / 1024:>8.2f} MiB {c:>6}    {sub.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
