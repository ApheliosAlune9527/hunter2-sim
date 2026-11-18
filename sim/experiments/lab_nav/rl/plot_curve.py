"""Draw the learning curve of one PPO run with Pillow (no matplotlib in this venv).

Usage: python3 plot_curve.py [path/to/curve.jsonl] [out.png]

The curve is written as JSON lines by train_ppo.py, one row per finished episode.
Two series are drawn: the episode return and a 10-episode moving average, because
a single episode's return swings by several units and the average is what shows a
trend.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[3] / "outputs/lab_nav_20261105/rl"

W, H = 900, 480
PAD_L, PAD_R, PAD_T, PAD_B = 64, 24, 40, 48


def load(path):
    rows = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def moving_average(values, window=10):
    out = []
    for i in range(len(values)):
        lo = max(0, i - window + 1)
        chunk = values[lo:i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "curve_seed0.jsonl"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else OUT / "learning_curve.png"
    rows = load(path)
    if not rows:
        raise SystemExit(f"no episodes in {path}")
    xs = [r["t"] for r in rows]
    ys = [r["return"] for r in rows]
    ma = moving_average(ys)

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    lo, hi = min(min(ys), min(ma)), max(max(ys), max(ma))
    span = max(hi - lo, 1e-6)
    lo, hi = lo - span * 0.1, hi + span * 0.1

    def px(x):
        return PAD_L + (x - min(xs)) / max(max(xs) - min(xs), 1) * (W - PAD_L - PAD_R)

    def py(y):
        return H - PAD_B - (y - lo) / (hi - lo) * (H - PAD_T - PAD_B)

    d.rectangle([PAD_L, PAD_T, W - PAD_R, H - PAD_B], outline="#cccccc")
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        val = lo + (hi - lo) * frac
        y = py(val)
        d.line([PAD_L, y, W - PAD_R, y], fill="#f0f0f0")
        d.text((6, y - 6), f"{val:+.1f}", fill="#666666")
    for frac in (0.0, 0.5, 1.0):
        val = min(xs) + (max(xs) - min(xs)) * frac
        x = px(val)
        d.line([x, PAD_T, x, H - PAD_B], fill="#f0f0f0")
        d.text((x - 20, H - PAD_B + 8), f"{int(val)}", fill="#666666")

    for i in range(1, len(xs)):
        d.line([px(xs[i - 1]), py(ys[i - 1]), px(xs[i]), py(ys[i])],
               fill="#9ec5e8", width=1)
    pts = [(px(x), py(y)) for x, y in zip(xs, ma)]
    for i in range(1, len(pts)):
        d.line([pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1]],
               fill="#1f5f8f", width=2)
    for x, y in zip(xs, ys):
        d.ellipse([px(x) - 2, py(y) - 2, px(x) + 2, py(y) + 2], fill="#7fb3d5")

    d.text((PAD_L, 12), f"return per episode ({len(rows)} episodes), "
                        f"dark line = 10-episode mean", fill="#222222")
    d.text((PAD_L, H - 24), "timesteps", fill="#666666")
    d.text((6, PAD_T - 18), "return", fill="#666666")
    img.save(dst)
    print(json.dumps({"episodes": len(rows), "last_return": ys[-1],
                      "last_mean": round(ma[-1], 3), "best_mean": round(max(ma), 3),
                      "out": str(dst)}))


if __name__ == "__main__":
    main()
