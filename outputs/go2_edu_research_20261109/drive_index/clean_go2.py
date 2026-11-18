# -*- coding: utf-8 -*-
"""Clean go2_papers.csv: fill known links, drop sentence-like / unmatched rows."""
import csv
import json
import re

ROOT = "."
rows = list(csv.DictReader(open(f"{ROOT}/data/go2_papers.csv", encoding="utf-8-sig")))
folders = json.load(open(f"{ROOT}/drive_index/quadruped_efv.json", encoding="utf-8"))


def norm(s):
    s = re.sub(r"^\d+\.\s*", "", s.lower())
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


by_norm = {}
for it in folders:
    by_norm[norm(it["title"])] = it["url"]

manual = {
    "Control the ARmada: LMM Coordination for Multi-Robot AR-HRC": "373.",
    "McARL:Morphology-Control-Aware Reinforcement Learning": "220.",
    "SemGeoNav:A Safety-Guided Visual Navigation Approach": "478.",
    "Milo, a Fully Autonomous Indoor/Outdoor Robotic Guide Dog": "521.",
}
by_num = {}
for it in folders:
    m = re.match(r"^(\d+)\.", it["title"])
    if m:
        by_num[m.group(1)] = it["url"]

out, dropped = [], []
for r in rows:
    t = r["title"].strip()
    if not r["url"]:
        nt = norm(t)
        for k, num in manual.items():
            nk = norm(k)
            if nt.startswith(nk[:40]) or nk.startswith(nt[:40]):
                r["url"] = by_num.get(num.rstrip("."), "")
                break
    if not r["url"]:
        r["url"] = by_norm.get(norm(t), "")
    # drop sentence-like fragments and still-unmatched rows
    words = t.split()
    suspicious = (
        t[:1].islower()
        or t.endswith(",")
        or "github.com" in t
        or (len(words) > 12 and t.count(" ") > 10 and not re.match(r"^[A-Z0-9]", t))
    )
    if suspicious or not r["url"]:
        dropped.append(t[:80])
        continue
    out.append(r)

# dedup by url
seen, dedup = set(), []
for r in out:
    if r["url"] in seen:
        continue
    seen.add(r["url"])
    dedup.append(r)

with open(f"{ROOT}/data/go2_papers.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["num", "title", "primary", "tags", "url"])
    w.writeheader()
    w.writerows(dedup)

print("kept", len(dedup), "dropped", len(dropped))
for d in dropped:
    print(" -", d)
