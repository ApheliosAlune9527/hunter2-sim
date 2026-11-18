# -*- coding: utf-8 -*-
"""Match Go2-related abstract blocks to folder entries and tag them."""
import csv
import json
import re
import sys

sys.path.insert(0, ".")
from analyze_papers import primary_of, tags_of


def norm(s):
    s = s.lower()
    s = re.sub(r"^\d+\.\s*", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def main():
    folders = json.load(open("quadruped_efv.json", encoding="utf-8"))
    blocks = json.load(open("go2_blocks.json", encoding="utf-8"))
    index = {}
    for it in folders:
        t = it["title"]
        m = re.match(r"^(\d+)\.\s*(.*)$", t)
        num = int(m.group(1)) if m else None
        clean = m.group(2).strip() if m else t
        index[norm(clean)] = (num, clean, it["url"])
    rows = []
    unmatched = 0
    seen = set()
    for b in blocks:
        t = (b["title"] or "").strip()
        key = norm(t)
        if not key or key in seen:
            continue
        seen.add(key)
        if key in index:
            num, clean, url = index[key]
        else:
            # try prefix match
            num, clean, url = None, re.sub(r"^\d+\.\s*", "", t), ""
            for k, v in index.items():
                if k.startswith(key) or key.startswith(k):
                    num, clean, url = v
                    break
            if not url:
                unmatched += 1
        tags = tags_of(clean)
        rows.append(
            {
                "num": num,
                "title": clean,
                "primary": primary_of(tags),
                "tags": ";".join(tags),
                "url": url,
            }
        )
    rows.sort(key=lambda r: (r["primary"], -(r["num"] or 0)))
    with open(sys.argv[1], "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["num", "title", "primary", "tags", "url"])
        w.writeheader()
        w.writerows(rows)
    print("rows", len(rows), "unmatched", unmatched)


if __name__ == "__main__":
    main()
