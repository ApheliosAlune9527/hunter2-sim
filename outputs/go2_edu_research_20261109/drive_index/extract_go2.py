# -*- coding: utf-8 -*-
"""Extract Go2-related paper blocks from the bilingual abstract corpus."""
import json
import re
import sys

CJK = re.compile(r"[\u4e00-\u9fff]")
LATIN = re.compile(r"[A-Za-z]")


def cjk_n(s):
    return len(CJK.findall(s))


def latin_ratio(s):
    return len(LATIN.findall(s)) / max(1, len(s))


def looks_title(s):
    if not (15 <= len(s) <= 260):
        return False
    if cjk_n(s) > 0:
        return False
    if latin_ratio(s) < 0.75:
        return False
    if s.endswith(".") or s.endswith("。") or s.endswith(":") or s.endswith(";"):
        return False
    if s.startswith(("http", "www", "The ", "In ", "We ", "This ", "Our ", "To ")):
        return False
    words = re.findall(r"[A-Za-z][A-Za-z\-']+", s)
    return len(words) >= 3


def main(path, out_path):
    lines = [l.strip() for l in open(path, encoding="utf-8") if l.strip()]
    out = []
    seen = set()
    for i, line in enumerate(lines):
        if not re.search(r"\bGo2\b", line, re.I):
            continue
        title = None
        for j in range(i - 1, max(-1, i - 12), -1):
            if looks_title(lines[j]):
                title = lines[j]
                break
        key = (title or line[:80]).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"line": i, "title": title, "text": line[:1200]})
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("blocks", len(out))
    for b in out[:10]:
        print("-", (b["title"] or "?")[:100])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

