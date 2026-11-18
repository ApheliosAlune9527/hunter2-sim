# -*- coding: utf-8 -*-
"""Parse Google Drive embeddedfolderview HTML into a JSON index."""
import json
import re
import sys

ENTRY = re.compile(
    r'<div class="flip-entry" id="entry-(?P<id>[^"]+)"[^>]*>.*?'
    r'<a href="(?P<href>[^"]+)"[^>]*>.*?'
    r'<div aria-label="(?P<kind>[^"]*)"[^>]*></div>.*?</div>.*?</div>.*?'
    r'<div class="flip-entry-title">(?P<title>.*?)</div>',
    re.S,
)


def main(html_path, out_path):
    html = open(html_path, encoding="utf-8", errors="replace").read()
    items = []
    for m in ENTRY.finditer(html):
        items.append(
            {
                "id": m.group("id"),
                "url": m.group("href"),
                "kind": m.group("kind"),
                "title": m.group("title").strip(),
            }
        )
    json.dump(items, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    kinds = {}
    for x in items:
        kinds[x["kind"]] = kinds.get(x["kind"], 0) + 1
    print("total", len(items), kinds)
    # numeric prefix stats
    nums = []
    for x in items:
        mm = re.match(r"(\d+)\.", x["title"])
        if mm:
            nums.append(int(mm.group(1)))
    if nums:
        print("numbered", len(nums), "min", min(nums), "max", max(nums), "unique", len(set(nums)))
        dup = {n: nums.count(n) for n in set(nums) if nums.count(n) > 1}
        print("dup prefixes", dict(list(dup.items())[:20]), "count", len(dup))
    for x in items[:3]:
        print(x["title"][:80], "|", x["kind"], "|", x["url"])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
