"""True size of outputs/, without following junctions/symlinks.

Earlier figures (1,111.3 MiB total, 716.6 MiB reclaimable) double-counted
C:\\Users\\ASUS\\.cache\\codex-runtimes\\...\\node_modules, because both
.build/node_modules entries are junctions pointing at that one directory.
"""
import os
import sys

ROOT = r"D:\rob-memory\outputs"
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def is_link(entry):
    try:
        if entry.is_symlink():
            return True
        return bool(entry.stat(follow_symlinks=False).st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return False


def walk(path):
    total = 0
    files = 0
    links = []
    for dirpath, dirnames, filenames in os.walk(path):
        keep = []
        for name in dirnames:
            full = os.path.join(dirpath, name)
            try:
                st = os.stat(full, follow_symlinks=False)
            except OSError:
                continue
            if st.st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT:
                links.append(full)
            else:
                keep.append(name)
        dirnames[:] = keep
        for name in filenames:
            full = os.path.join(dirpath, name)
            try:
                st = os.stat(full, follow_symlinks=False)
            except OSError:
                continue
            if st.st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT:
                links.append(full)
                continue
            total += st.st_size
            files += 1
    return total, files, links


def main():
    grand = 0
    grand_files = 0
    all_links = []
    rows = []
    for name in sorted(os.listdir(ROOT)):
        full = os.path.join(ROOT, name)
        if os.path.isdir(full):
            size, files, links = walk(full)
        else:
            size, files, links = os.path.getsize(full), 1, []
        grand += size
        grand_files += files
        all_links.extend(links)
        rows.append((size, files, name))
    for size, files, name in sorted(rows, reverse=True)[:12]:
        print(f"{size / 1048576:9.2f} MiB {files:6d}  {name}")
    print(f"---- total {grand / 1048576:.2f} MiB / {grand_files} files")
    print(f"---- reparse points skipped: {len(all_links)}")
    for p in all_links:
        print("   ", p)


if __name__ == "__main__":
    sys.exit(main())
