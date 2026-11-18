import json
import sys
from collections import Counter
from pathlib import Path

path = Path(sys.argv[1])
rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def classify(r):
    """Prefer the recorded reason over the return.

    The return threshold was a proxy for an episode that ended on the goal while
    the reward was 'progress'.  Once the reward also charges for remaining
    distance a successful episode returns about +2.8, so the threshold would
    report every arrival as a timeout.  The episode's own reason is the fact.
    """
    reason = r.get("reason")
    if reason == "goal":
        return "goal"
    if reason == "collision":
        return "crash"
    if reason == "timeout":
        return "other"
    if r["return"] >= 4.0:
        return "goal"
    if r["return"] <= -4.0:
        return "crash"
    return "other"


bins = {}
for r in rows:
    b = (r["t"] // 10000) * 10000
    d = bins.setdefault(b, {"n": 0, "ret": 0.0, "goal": 0, "crash": 0, "other": 0})
    d["n"] += 1
    d["ret"] += r["return"]
    d[classify(r)] += 1

print("budget".ljust(14), "episodes", "mean return", "arrived", "contact", "other")
for b in sorted(bins):
    d = bins[b]
    mean = d["ret"] / d["n"]
    print(str(b).ljust(14), str(d["n"]).rjust(8), f"{mean:+.2f}".rjust(11),
          str(d["goal"]).rjust(7), str(d["crash"]).rjust(7), str(d["other"]).rjust(5))
print()
kinds = Counter(classify(r) for r in rows)
print("episodes", len(rows), dict(Counter(r.get("reason") for r in rows)))
print("arrival rate overall", round(kinds["goal"] / len(rows), 3), f"({kinds['goal']}/{len(rows)})")
print("contact rate overall", round(kinds["crash"] / len(rows), 3), f"({kinds['crash']}/{len(rows)})")
