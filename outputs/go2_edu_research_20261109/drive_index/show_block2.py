# -*- coding: utf-8 -*-
"""Print the abstract lines surrounding each Go2 mention for selected titles."""
import json
import re
import sys

LINES = [l.strip() for l in open("quad_abstracts.txt", encoding="utf-8") if l.strip()]
BLOCKS = json.load(open("go2_blocks.json", encoding="utf-8"))

for q in sys.argv[1:]:
    q = q.lower()
    for b in BLOCKS:
        if q in (b["title"] or "").lower():
            i = b["line"]
            print("=" * 100)
            print("NEAR:", b["title"])
            # print 4 lines before through 1 line after the mention line
            for j in range(max(0, i - 4), min(len(LINES), i + 2)):
                print(f"[{j}] {LINES[j][:900]}")
            break
