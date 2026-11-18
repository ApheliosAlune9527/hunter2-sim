"""Inventory helpers for the outputs/ scan.

Prints three reports:
  1. per-directory top-level listing (what a human would see first)
  2. empty directories and junk files (__pycache__, .pyc, .log, .pid, .tmp)
  3. exact duplicate files (<= 2 MB) with the bytes they waste
"""

import hashlib
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"D:\rob-memory\outputs")
JUNK_SUFFIX = {".pyc", ".pyo", ".log", ".pid", ".tmp", ".bak", ".swp"}
JUNK_DIRS = {"__pycache__", ".ipynb_checkpoints", ".pytest_cache"}


def top_level(path: Path) -> str:
    items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    names = []
    for p in items:
        names.append(p.name + ("/" if p.is_dir() else ""))
    return ", ".join(names)


def main() -> int:
    dirs = sorted([p for p in ROOT.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
    print("=" * 100)
    print("1. TOP-LEVEL LISTING")
    print("=" * 100)
    for d in dirs:
        try:
            print(f"\n[{d.name}]")
            print("   " + top_level(d)[:1200])
        except OSError as exc:
            print(f"   ERROR {exc}")

    print()
    print("=" * 100)
    print("2. EMPTY DIRS AND JUNK")
    print("=" * 100)
    empty, junk = [], []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dp = Path(dirpath)
        if not dirnames and not filenames:
            empty.append(dp)
        for name in filenames:
            fp = dp / name
            if fp.suffix.lower() in JUNK_SUFFIX or any(part in JUNK_DIRS for part in fp.parts):
                try:
                    junk.append((fp, fp.stat().st_size))
                except OSError:
                    junk.append((fp, 0))
    print(f"empty directories: {len(empty)}")
    for p in empty:
        print(f"   EMPTY {p.relative_to(ROOT)}")
    print(f"junk files: {len(junk)}  total {sum(s for _, s in junk) / 1024:.1f} KiB")
    for p, s in junk:
        print(f"   JUNK {s:>8} {p.relative_to(ROOT)}")

    print()
    print("=" * 100)
    print("3. EXACT DUPLICATES (files <= 2 MB)")
    print("=" * 100)
    by_size = defaultdict(list)
    for dirpath, dirnames, filenames in os.walk(ROOT):
        for name in filenames:
            fp = Path(dirpath) / name
            try:
                st = fp.stat()
            except OSError:
                continue
            if st.st_size and st.st_size <= 2 * 1024 * 1024:
                by_size[st.st_size].append(fp)
    groups = []
    for size, files in by_size.items():
        if len(files) < 2:
            continue
        by_hash = defaultdict(list)
        for fp in files:
            h = hashlib.sha256(fp.read_bytes()).hexdigest()
            by_hash[h].append(fp)
        for h, same in by_hash.items():
            if len(same) > 1:
                groups.append((size, h, same))
    groups.sort(key=lambda g: -g[0] * (len(g[2]) - 1))
    wasted = sum(size * (len(same) - 1) for size, _, same in groups)
    print(f"duplicate groups: {len(groups)}   reclaimable {wasted / 1024 / 1024:.2f} MiB")
    for size, h, same in groups:
        print(f"\n   {len(same)} x {size} B  sha {h[:12]}")
        for fp in same:
            print(f"      {fp.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
