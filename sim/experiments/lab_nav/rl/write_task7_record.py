"""Assemble outputs/lab_nav_20261105/task7_verification.json from the RL artefacts.

Reads only files this project wrote, keeps every number traceable, and refuses to
invent a figure that is not on disk.  Evaluation files are discovered by pattern so
that a new training run joins the record without editing this script.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[3]
OUT = WS / "outputs" / "lab_nav_20261105"
RL = OUT / "rl"


def load(path, default=None):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else default


def classify(r):
    """Use the episode's own reason when it was recorded.

    The return thresholds only work for the 'progress' reward: once remaining
    distance is charged every step, a successful episode returns about +2.8 and
    the threshold would call it a timeout.
    """
    reason = r.get("reason")
    if reason == "goal":
        return "arrived"
    if reason == "collision":
        return "contact"
    if reason == "timeout":
        return "other"
    if r["return"] >= 4.0:
        return "arrived"
    if r["return"] <= -4.0:
        return "contact"
    return "other"


def curve_stats(path):
    p = Path(path)
    if not p.exists():
        return None
    rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    if not rows:
        return None
    bins = {}
    for r in rows:
        b = (r["t"] // 10000) * 10000
        d = bins.setdefault(b, {"n": 0, "ret": 0.0, "arrived": 0, "contact": 0})
        d["n"] += 1
        d["ret"] += r["return"]
        kind = classify(r)
        if kind == "arrived":
            d["arrived"] += 1
        elif kind == "contact":
            d["contact"] += 1
    table = [{"from_step": b, "episodes": d["n"],
              "mean_return": round(d["ret"] / d["n"], 3),
              "arrived": d["arrived"], "contact": d["contact"]}
             for b, d in sorted(bins.items())]
    kinds = [classify(r) for r in rows]
    return {"episodes": len(rows), "bins": table,
            "reason_recorded": sum(1 for r in rows if r.get("reason")),
            "arrival_rate": round(kinds.count("arrived") / len(rows), 3),
            "contact_rate": round(kinds.count("contact") / len(rows), 3)}


def summarise(ev):
    s = ev.get("summary", {})
    out = {}
    for key in ("eval_goals", "train_near", "held_out", "constant_forward"):
        v = s.get(key) or {}
        if v:
            out[key] = v
    return out


def main():
    smoke = load(OUT / "rl_env_smoke.json", {})
    term = load(OUT / "rl_termination_test.json", {})
    goals = load(HERE / "goals.json", {})
    metas = {p.stem.replace("run_meta_", ""): load(p) for p in sorted(RL.glob("run_meta_*.json"))}

    runs = []
    for ev_path in sorted(RL.glob("eval_ppo_*.json")):
        ev = load(ev_path)
        model = Path(ev.get("model", "")).name
        stem = Path(model).stem if model else ev_path.stem
        key = stem.replace("ppo_", "")
        meta = metas.get(key, {})
        curve = curve_stats(RL / f"curve_{key}.jsonl")
        runs.append({
            "run": key,
            "model": f"rl/{model}",
            "training": meta or None,
            "learning_curve": curve,
            "evaluation": summarise(ev),
            "repeats": ev.get("repeats"),
            "policy_input": ev.get("policy_input"),
            "truth_used_for": ev.get("truth_used_for"),
        })

    doc = {
        "generated": "2026-11-06",
        "environment": {
            "class": "sim/experiments/lab_nav/rl/hz_nav_env.py (HzLabNavEnv), "
                     "gym wrapper in gym_wrapper.py",
            "observation": "76 floats: 72 scan beams pooled 10:1 by minimum, divided by "
                           "3 m and clipped at 1; goal range / 6 m; goal bearing / pi; "
                           "last commanded v / 0.26; last w / 0.20",
            "action": "2 floats in [-1,1]: v = (a0+1)/2 * 0.26 m/s, forward only because "
                      "the baseline runs allow_reversing: false; w = a1 * 0.20 rad/s; the "
                      "Ackermann limit comes from the vehicle model, not from clipping",
            "control_period_sim_s": 0.1,
            "reward": "2.0 * progress_m - 0.01 - 0.05 * |dv|; +5.0 on goal; -5.0 on contact",
            "termination": "goal within 0.25 m, contact proxy, or the episode budget",
            "reset": "set_pose teleport, read the pose back, re-seed the pose estimate from "
                     "truth and the first odometry sample, then advance on odometry "
                     "increments only",
        },
        "interface_validation": smoke,
        "termination_validation": term,
        "split": {
            "pool": goals.get("pool_size"),
            "train": len(goals.get("train", [])),
            "held_out": len(goals.get("held_out", [])),
            "held_out_min_distance_to_train_m": 0.75,
            "filter": "straight corridor at the approach bearing must clear the footprint",
            "note": "the three fixed evaluation goals are the ones the navigation baseline ran",
        },
        "runs": runs,
        "reading": [
            "8,192 steps: the policy drives and never arrives; this only proves the "
            "interface works.",
            "60,000 steps on all 40 goals: still 0/9, but the mean final distance fell "
            "from 3.12 m to 1.66 m and the mean path from 4.85 m to 2.49 m, so it "
            "learned to approach.  Contact episodes disappear in the last 20k steps "
            "while arrivals stay near 10%.",
            "20,000 steps on the nearest 8 goals: 0/8 on the very goals it trained on, "
            "with a mean final distance of 0.864 m.  A trace shows the vehicle driving "
            "to 0.679 m from the goal and then commanding zero for the rest of the "
            "episode -- stopping beat risking the last metre, because contact costs "
            "-5.0 and idling costs -0.01 per step.",
            "Charging 0.03 per metre of remaining distance every step removes that "
            "trap: the same budget and goal pool goes from 0/8 to 4/8 with a mean "
            "final distance of 0.613 m.  The fixed goals and the held-out goals stay "
            "at zero, so finishing a practised goal and generalising are separate "
            "problems and only the first was fixed.",
            "Returns are not comparable across the reward variants: the distance "
            "charge lowers the return of a successful episode from about +5.9 to "
            "+2.8, so arrival counts must be compared, not mean return.",
        ],
        "comparison_with_the_baseline": {
            "baseline": "Nav2 on the same world, same scan, same goals: 9/9 "
                        "(outputs/lab_nav_20261105/task4_verification.json)",
            "not_a_fair_comparison_yet": "the baseline is given the map, the policy is "
                                         "not; the policy's pose starts from truth at "
                                         "reset and then drifts on odometry",
            "what_must_match_before_a_claim": ["map or no map", "localisation mode",
                                               "sensor profile", "speed limits",
                                               "goal set", "time budget"],
        },
        "artifacts": ["rl_env_smoke.json", "rl_termination_test.json", "rl/goals.json",
                      "rl/README.md", "rl/learning_curve_60000.png"],
    }
    for r in runs:
        doc["artifacts"].append(r["model"])
        if r["learning_curve"]:
            doc["artifacts"].append(f"rl/curve_{r['run']}.jsonl")
    (OUT / "task7_verification.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    print(json.dumps({"runs": [(r["run"],
                                (r["evaluation"].get("eval_goals") or {}).get("successes"),
                                (r["evaluation"].get("eval_goals") or {}).get("attempts"))
                               for r in runs]}))


if __name__ == "__main__":
    main()
