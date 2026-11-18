# -*- coding: utf-8 -*-
"""Fetch a public Google Drive folder listing and extract the embedded JSON.

Usage: python fetch_drive.py <folder_id> <out.json>
"""
import json
import os
import re
import sys
import urllib.request

PROXY = os.environ.get("HTTPS_PROXY") or "http://127.0.0.1:7897"


def fetch(url: str) -> str:
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with opener.open(req, timeout=60) as r:
        raw = r.read()
    return raw.decode("utf-8", "replace")


ESC = re.compile(r"\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|.)", re.S)


def unescape_js(s: str) -> str:
    def rep(m):
        t = m.group(1)
        if t[0] == "x":
            return chr(int(t[1:], 16))
        if t[0] == "u":
            return chr(int(t[1:], 16))
        return {"n": "\n", "r": "\r", "t": "\t", "'": "'", '"': '"', "\\": "\\"}.get(t, t)

    return ESC.sub(rep, s)


def extract_ivd(html: str):
    marker = "_DRIVE_ivd'"
    i = html.find(marker)
    if i < 0:
        marker = '_DRIVE_ivd'
        i = html.find(marker)
    i = html.find("=", i)
    # skip  = '
    j = html.find("'", i)
    k = html.find("';", j)
    s = html[j + 1 : k]
    txt = unescape_js(s)
    return json.loads(txt)


def walk(node, out):
    """Collect dicts that look like drive items (have string id + name-ish fields)."""
    if isinstance(node, list):
        for x in node:
            walk(x, out)
    elif isinstance(node, dict):
        # a drive item usually has 'id', 'name', 'mimeType' in the AF data model
        if "id" in node and ("name" in node or "title" in node):
            out.append(node)
        for v in node.values():
            walk(v, out)


def main():
    fid = sys.argv[1]
    out = sys.argv[2]
    url = f"https://drive.google.com/drive/folders/{fid}?usp=sharing&hl=en"
    html = fetch(url)
    data = extract_ivd(html)
    with open(out + ".raw.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    items = []
    walk(data, items)
    with open(out + ".items.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    print("raw top type:", type(data).__name__, "len:", len(data) if hasattr(data, "__len__") else "?")
    print("items:", len(items))
    for it in items[:5]:
        print(json.dumps(it, ensure_ascii=False)[:400])


if __name__ == "__main__":
    main()
