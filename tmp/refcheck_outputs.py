"""Reference check for outputs/ directories.

For every directory under outputs/, count how many *other* files in the repo
mention its name. A directory with zero references outside itself (and outside
the archived increment snapshot) is a candidate for "nothing points at it".
"""

import os
import sys
from pathlib import Path

REPO = Path(r"D:\rob-memory")
OUT = REPO / "outputs"
SKIP_PARTS = {"hunter_increment_since_20261021_20261031", ".git", "tmp"}
TEXT_EXT = {".md", ".txt", ".py", ".bash", ".sh", ".json", ".yaml", ".yml", ".csv", ".xml", ".ps1", ".rviz", ".sdf"}


def main() -> int:
    dirs = sorted([p.name for p in OUT.iterdir() if p.is_dir()])
    bodies = {}
    for dirpath, dirnames, filenames in os.walk(REPO):
        dp = Path(dirpath)
        if any(part in SKIP_PARTS for part in dp.parts):
            dirnames[:] = []
            continue
        for name in filenames:
            fp = dp / name
            if fp.suffix.lower() not in TEXT_EXT:
                continue
            if "hunter_increment_since_20261021_20261031" in str(fp):
                continue
            try:
                if fp.stat().st_size > 2_000_000:
                    continue
                bodies[fp] = fp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

    print(f"scanned {len(bodies)} text files\n")
    print(f"{'directory':52} {'refs':>5}  referrers")
    print("-" * 120)
    for d in dirs:
        hits = []
        for fp, text in bodies.items():
            if d not in text:
                continue
            # ignore references that live inside the directory itself
            if fp.is_relative_to(OUT / d):
                continue
            hits.append(fp.relative_to(REPO))
        shown = ", ".join(str(h) for h in hits[:3])
        if len(hits) > 3:
            shown += f" (+{len(hits) - 3})"
        print(f"{d:52} {len(hits):>5}  {shown[:150]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
