#!/usr/bin/env python3
import sys
import numpy as np

d = np.load(sys.argv[1])
data = d["data"]
vals, counts = np.unique(data, return_counts=True)
print("shape", data.shape, "dtype", data.dtype)
print("values", list(zip(vals.tolist(), counts.tolist())))
for spec in sys.argv[2:]:
    name, c, r = spec.split(",")
    c, r = int(c), int(r)
    print(name, "cell", c, r, "value", int(data[r, c]))
    print(data[max(0,r-3):r+4, max(0,c-3):c+4])
