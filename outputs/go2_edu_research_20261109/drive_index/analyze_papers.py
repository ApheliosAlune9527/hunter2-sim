# -*- coding: utf-8 -*-
"""Classify the Unitree paper library by title keywords and export an index."""
import csv
import json
import re
import sys

CATS = [
    ("locomotion_rl", r"\b(rl|reinforcement|policy|policies|gait|gait[s]?|locomotion|locomote|parkour|agile|jump|jumping|hopping|running|trot|gallop|bound|bounding|imitation|retarget|sim-to-real|sim2real|domain randomization|teacher-student|privileged|cpG|skill)\b"),
    ("control_mpc", r"\b(mpc|model predictive|whole-body control|wbc|controller|control|stabiliz|stabiliz|balance|dynamics|kinematic|trajectory optimization|optimal control|contact|force control|impedance|torque|estimation)\b"),
    ("navigation", r"\b(navigation|navigate|slam|mapping|localization|localisation|path planning|planner|planning|exploration|obstacle avoidance|costmap|frontier|topological|semantic map|place recognition|visual odometry|state estimation|odometry|point goal|object goal|relocalization)\b"),
    ("vln_vla", r"\b(vision-and-language|vision language|vision-language|vln|vla|language|instruction|llm|large language|vlm|foundation model|agent|agentic|gpt|multimodal|embodied|vision-language-action|dialogue|conversational)\b"),
    ("perception", r"\b(perception|detection|detector|segmentation|depth|lidar|point cloud|camera|vision|visual|recognition|pose estimation|tracking|optical flow|event camera|thermal|radar|scan)\b"),
    ("manipulation", r"\b(manipulation|manipulator|arm|grasp|grasping|dexterous|hand|mobile manipulation|loco-manipulation|object)\b"),
    ("humanoid", r"\b(humanoid|biped|bipedal|whole-body|human motion|teleoperation|teleop|exoskeleton|prosthesis|human-to-humanoid|human-to-humanoid)\b"),
    ("hri_social", r"\b(human-robot|social|interaction|following|follow|companion|voice|speech|gesture|emotion|trust|crowd|human-aware)\b"),
    ("multi_robot", r"\b(multi-robot|multi-agent|multi agent|swarm|cooperative|collaborative|formation|decentralized|team|distributed)\b"),
    ("sim_benchmark", r"\b(benchmark|dataset|simulation|simulator|sim-to-real|sim2real|isaac|mujoco|gazebo|digital twin|gym|environment|world model)\b"),
    ("safety", r"\b(safety|safe|robust|fault|failure|fall|recovery|collision|risk|certified|formal|reachability|adversarial|attack|jailbreak)\b"),
    ("hardware", r"\b(design|mechanism|actuator|motor|leg|joint|drive|transmission|lightweight|thermal|battery|sensor|prototype|fabrication|structure)\b"),
    ("application", r"\b(inspection|rescue|construction|agriculture|medical|hospital|education|entertainment|logistics|delivery|search|survey|monitoring|mining|nuclear)\b"),
]
ORDER = [c for c, _ in CATS]
PRIORITY = [
    "manipulation",
    "humanoid",
    "vln_vla",
    "navigation",
    "locomotion_rl",
    "perception",
    "control_mpc",
    "hri_social",
    "multi_robot",
    "safety",
    "sim_benchmark",
    "hardware",
    "application",
]


def tags_of(title):
    t = title.lower()
    tags = []
    for name, pat in CATS:
        if re.search(pat, t):
            tags.append(name)
    return tags


def primary_of(tags):
    for p in PRIORITY:
        if p in tags:
            return p
    return "other"


def main():
    quad = json.load(open(sys.argv[1], encoding="utf-8"))
    hum = json.load(open(sys.argv[2], encoding="utf-8"))
    rows = []
    for corpus, items in (("quadruped", quad), ("humanoid", hum)):
        for it in items:
            title = it["title"].strip()
            m = re.match(r"^(\d+)\.\s*(.*)$", title)
            num = int(m.group(1)) if m else None
            clean = m.group(2).strip() if m else title
            if not clean:
                continue
            tags = tags_of(clean)
            rows.append(
                {
                    "corpus": corpus,
                    "num": num,
                    "title": clean,
                    "tags": ";".join(tags),
                    "primary": primary_of(tags),
                    "url": it["url"],
                }
            )
    with open(sys.argv[3], "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["corpus", "num", "title", "primary", "tags", "url"])
        w.writeheader()
        w.writerows(rows)
    summary = {}
    for corpus in ("quadruped", "humanoid"):
        sub = [r for r in rows if r["corpus"] == corpus]
        summary[corpus] = {
            "total": len(sub),
            "primary": {k: sum(1 for r in sub if r["primary"] == k) for k in PRIORITY + ["other"]},
            "tags": {k: sum(1 for r in sub if k in r["tags"].split(";")) for k in ORDER},
        }
    json.dump(summary, open(sys.argv[4], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
