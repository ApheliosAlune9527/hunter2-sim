# -*- coding: utf-8 -*-
"""Parse a Google Drive public folder listing into [{id,name,mime,size,modified,url}]."""
import json
import re
import sys


def parse_items(path):
    data = json.load(open(path, encoding="utf-8"))
    items = data[0]
    out = []
    for it in items:
        name = it[2]
        mime = it[3]
        url = it[114] if len(it) > 114 else None
        size = it[13] if len(it) > 13 else None
        modified = it[10] if len(it) > 10 else None
        if not isinstance(name, str):
            continue
        out.append(
            {
                "id": it[0],
                "name": name,
                "mime": mime,
                "size": size if isinstance(size, (int, float)) else None,
                "modified_ms": modified if isinstance(modified, (int, float)) else None,
                "url": url,
            }
        )
    return out


if __name__ == "__main__":
    items = parse_items(sys.argv[1])
    json.dump(items, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("items:", len(items))
    for x in items[:3]:
        print(x["name"], "|", x["mime"], "|", x["size"])
