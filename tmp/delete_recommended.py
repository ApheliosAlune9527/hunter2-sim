"""Delete the items docs/outputs-audit-20261118.md recommends removing.

Writes a manifest (path, bytes, sha256 per file) to docs/ before deleting, so the
removal is auditable even though the bytes are gone.

Deliberately NOT deleted: the two .build/node_modules entries. They are junctions
to C:\\Users\\ASUS\\.cache\\codex-runtimes\\...\\node_modules, so they occupy no
space inside the repo and are what makes the deck scripts runnable.
"""
import hashlib
import json
import os
import shutil
from pathlib import Path

ROOT = Path(r"D:\rob-memory")
OUT = ROOT / "outputs"
MANIFEST = ROOT / "docs" / "outputs-deleted-20261118.json"

TREES = [
    "outputs/agentvln_reverse_dock_20261110_013316_amcl",
    "outputs/agentvln_reverse_record_20261110_015644",
    "outputs/agentvln_reverse_record_20261110_022642",
    "outputs/agentvln_reverse_record_20261110_040254",
    "outputs/agentvln_reverse_record_20261110_040825",
    "outputs/car_nav_fix_20261108",
]
FILES = [
    "outputs/car_params_patch_20261108.tar.gz",
    "outputs/floral-ring-v01/preview-server.log",
    "outputs/floral-ring-v01/preview-server.pid",
]
EMPTY_DIRS = [
    "outputs/floral-ring-v01/__pycache__",
    "outputs/hunter_nav2_append_20261027/.build/append-render",
    "outputs/hunter_nav2_append_20261027/.build/final-render",
    "outputs/hunter_nav2_append_20261027/.build/source-render",
    "outputs/weekly_mapping_ppt_20261014/.build/final-preview",
    "outputs/weekly_mapping_ppt_20261014/.build/preview",
    "outputs/weekly_mapping_ppt_20261014/.build/preview-v2",
]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files_in(path):
    for dirpath, _dirnames, filenames in os.walk(path):
        for name in filenames:
            yield Path(dirpath) / name


def main():
    deleted = []
    total_bytes = 0
    total_files = 0

    for rel in TREES + FILES:
        path = ROOT / rel
        if not path.exists():
            print(f"skip (missing): {rel}")
            continue
        if path.is_dir():
            entries = []
            for item in files_in(path):
                size = item.stat().st_size
                entries.append({
                    "path": str(item.relative_to(ROOT)).replace("\\", "/"),
                    "bytes": size,
                    "sha256": sha256(item),
                })
            size = sum(e["bytes"] for e in entries)
            kind = "tree"
        else:
            size = path.stat().st_size
            entries = [{
                "path": rel,
                "bytes": size,
                "sha256": sha256(path),
            }]
            kind = "file"
        total_bytes += size
        total_files += len(entries)
        deleted.append({"path": rel, "kind": kind, "files": len(entries),
                        "bytes": size, "entries": entries})
        if kind == "tree":
            shutil.rmtree(path)
        else:
            path.unlink()
        print(f"deleted {rel}: {len(entries)} files, {size / 1048576:.2f} MiB")

    removed_dirs = []
    for rel in EMPTY_DIRS:
        path = ROOT / rel
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
            removed_dirs.append(rel)
            print(f"removed empty dir {rel}")

    document = {
        "date": "2026-11-18",
        "reason": "docs/outputs-audit-20261118.md A 表与 D 表",
        "not_deleted": [
            "outputs/weekly_mapping_ppt_20261014/.build/node_modules",
            "outputs/group_meeting_20261020/.build/node_modules",
        ],
        "not_deleted_reason": (
            "两者都是 junction，指向 "
            "C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules，"
            "在仓库内不占空间；删掉会让 create_deck.mjs / export_pptx.mjs 无法直接运行。"
        ),
        "deleted": deleted,
        "empty_dirs_removed": removed_dirs,
        "totals": {
            "files": total_files,
            "bytes": total_bytes,
            "mib": round(total_bytes / 1048576, 3),
        },
    }
    MANIFEST.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    print(f"---- {total_files} files, {total_bytes / 1048576:.3f} MiB")
    print(f"---- manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
