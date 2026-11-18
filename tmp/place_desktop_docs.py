"""Move the three desktop documents into their repo homes.

Rules used here:
  * a file is copied byte-for-byte (no re-encoding), hash verified after copy
  * the desktop copy is removed only after the destination hash matches
  * if the destination already holds an identical file, the desktop copy is
    removed and nothing is written
  * if the destination holds a *different* file, stop and report (no overwrite)
"""

import hashlib
import shutil
import sys
from pathlib import Path

DESKTOP = Path(r"C:\Users\ASUS\Desktop")
REPO = Path(r"D:\rob-memory")

MOVES = [
    (DESKTOP / "ros2_nav2_interactive_prompt.md",
     REPO / "outputs" / "hunter_agent_handoff_20261105" / "ros2_nav2_interactive_prompt.md"),
    (DESKTOP / "Nav2导航命令.txt",
     REPO / "outputs" / "hunter_nav2_shortcuts_20261108" / "Nav2导航命令.txt"),
    (DESKTOP / "Nav2 导航使用说明.txt",
     REPO / "outputs" / "hunter_nav2_personal_launch_20261109" / "hz_nav_launch" / "Nav2 导航使用说明.txt"),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ok = True
    for src, dst in MOVES:
        print(f"\n== {src.name}")
        if not src.exists():
            print(f"   source missing: {src}")
            ok = False
            continue
        src_hash = sha256(src)
        print(f"   source sha256 {src_hash}")
        if dst.exists():
            dst_hash = sha256(dst)
            if dst_hash == src_hash:
                src.unlink()
                print(f"   destination already identical -> removed desktop copy")
                print(f"   kept: {dst}")
                continue
            print(f"   destination exists with a DIFFERENT hash: {dst_hash}")
            print(f"   refused to overwrite: {dst}")
            ok = False
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        dst_hash = sha256(dst)
        if dst_hash != src_hash:
            print(f"   copy hash mismatch: {dst_hash}")
            ok = False
            continue
        src.unlink()
        print(f"   copied and verified -> {dst}")
        print(f"   desktop copy removed")
    print("\nRESULT:", "all done" if ok else "problems above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
