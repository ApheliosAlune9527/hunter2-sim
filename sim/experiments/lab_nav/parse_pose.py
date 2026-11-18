#!/usr/bin/env python3
"""Print the world pose of a named model from an ignition pose/info dump on stdin."""
import re
import sys

name = sys.argv[1] if len(sys.argv) > 1 else "hz_hunter_full"
text = sys.stdin.read()

# Each entity block looks like:  name: "hz_hunter_full"\n  id: 12\n  position { x: .. y: .. z: .. }
for match in re.finditer(r'name: "([^"]*)"(.*?)(?=name: "|\Z)', text, re.S):
    if match.group(1) != name:
        continue
    body = match.group(2)
    pos = re.search(r'position \{(.*?)\}', body, re.S)
    rot = re.search(r'orientation \{(.*?)\}', body, re.S)
    if not pos:
        continue
    vals = dict(re.findall(r'([xyz]):\s*(-?[\d.eE+]+)', pos.group(1)))
    print(f"{name} x={float(vals.get('x', 0)):.4f} y={float(vals.get('y', 0)):.4f} "
          f"z={float(vals.get('z', 0)):.4f}")
    break
else:
    print(f"{name} NOT FOUND")
