# -*- coding: utf-8 -*-
"""Parse the bilingual abstract docx text dumps into per-paper records (v2)."""
import json
import re
import sys

CJK = re.compile(r"[\u4e00-\u9fff]")
LATIN = re.compile(r"[A-Za-z]")
DASH = re.compile(r"\s*[-–—]\s*")


def ascii_ratio(s):
    letters = len(LATIN.findall(s))
    return letters / max(1, len(s))


def is_cjk(s):
    return len(CJK.findall(s)) >= 2


def is_title_en(s):
    return (
        8 <= len(s) <= 260
        and ascii_ratio(s) > 0.8
        and (" - " in s or " -" in s or "- " in s)
        and not s.endswith(".")
        and not s.startswith("http")
    )


def split_title(line):
    if " - " in line:
        t, inst = line.rsplit(" - ", 1)
        return t.strip(), inst.strip()
    return line.strip(), ""


def parse(path):
    lines = [l.strip() for l in open(path, encoding="utf-8") if l.strip()]
    records = []
    i = 0
    n = len(lines)
    while i < n - 1:
        zh, en = lines[i], lines[i + 1]
        if is_cjk(zh) and is_title_en(en):
            body = []
            j = i + 2
            while j < n - 1:
                if is_cjk(lines[j]) and is_title_en(lines[j + 1]):
                    break
                body.append(lines[j])
                j += 1
            en_title, en_inst = split_title(en)
            zh_title, _ = split_title(zh)
            records.append(
                {
                    "zh_title": zh_title,
                    "en_title": en_title,
                    "zh_inst": zh.split("-")[-1].strip() if "-" in zh else "",
                    "en_inst": en_inst,
                    "body": "\n".join(body),
                }
            )
            i = j
        else:
            i += 1
    return records


if __name__ == "__main__":
    recs = parse(sys.argv[1])
    print("records", len(recs))
    json.dump(recs, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in recs[:3]:
        print("-", r["en_title"][:90], "|", r["en_inst"][:40], "| body", len(r["body"]))
    for r in recs[-2:]:
        print("+", r["en_title"][:90], "|", r["en_inst"][:40], "| body", len(r["body"]))
