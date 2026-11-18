# -*- coding: utf-8 -*-
"""Print abstract blocks whose title contains one of the given substrings."""
import json
import sys

blocks = json.load(open("go2_blocks.json", encoding="utf-8"))
seen = set()
for q in sys.argv[1:]:
    q = q.lower()
    for b in blocks:
        t = (b["title"] or "")
        if q in t.lower() and t not in seen:
            seen.add(t)
            print("=" * 90)
            print("TITLE:", t)
            print(b["text"][:1800])
            break
