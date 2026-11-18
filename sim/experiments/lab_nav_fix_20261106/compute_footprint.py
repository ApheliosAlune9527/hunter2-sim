"""Derive the footprint from the model instead of inheriting a rectangle.

The old parameters used `x in [-0.50, 0.52], y in [-0.395, 0.395]`, copied from the
senior's vehicle.  `base_link` sits at the rear-axle wheel-centre midpoint, and the
model's own bounds reach x = 0.814 m, so that rectangle leaves 0.294 m of the nose
outside the collision footprint -- a costmap can plan a path that puts the nose
into a wall.

This script rebuilds the polygon from geometry_report.json:

  * chassis: the bare envelope, x in [-0.164, 0.814], y in +/-0.373;
  * front wheels: each tyre is a 0.328 x 0.142 m rectangle centred on the wheel
    centre (x = 0.650, y = +/-0.3025).  Steering turns that rectangle about the
    kingpin, so the swept outline is the union over the steering range.  The
    plugin allows 0.4 rad; the inner wheel reaches atan(L / (R - w/2)) = 0.444 rad
    at full lock, which is the wider of the two, so 0.444 is used;
  * a 0.02 m safety margin is added to the union, which keeps the margin in the
    footprint instead of hiding it inside a 0.20 m inflation radius.

The result is the convex hull of the two rectangles: a hexagon that reaches
forward and sideways only where the steered wheels actually do.

Writes footprint_polygon.json and footprint_sketch.png next to the other records.
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / 'outputs/lab_nav_fix_20261106'
GEOM = REPO / 'sim/hz_hunter_full_description/geometry_report.json'

MARGIN = 0.02
STEER_MAX = 0.444          # inner wheel angle at full lock, rad
WHEEL_HALF_LEN = 0.1641    # tyre radius, from the link bounds
WHEEL_HALF_WID = 0.0708    # half tyre width
FRONT_AXLE_X = 0.650       # wheelbase
HALF_TRACK = 0.3025        # track / 2


def wheel_corners(cx, cy, angle):
    """Corners of one tyre rectangle, rotated by `angle` about its centre."""
    ca, sa = math.cos(angle), math.sin(angle)
    pts = []
    for dx in (-WHEEL_HALF_LEN, WHEEL_HALF_LEN):
        for dy in (-WHEEL_HALF_WID, WHEEL_HALF_WID):
            pts.append((cx + dx * ca - dy * sa, cy + dx * sa + dy * ca))
    return pts


def convex_hull(points):
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def main():
    geom = json.loads(GEOM.read_text(encoding='utf-8'))
    bare = geom['bare_chassis_bounds_m']

    sweep = []
    for side in (+1, -1):
        for step in range(-100, 101):
            angle = STEER_MAX * step / 100.0
            sweep += wheel_corners(FRONT_AXLE_X, side * HALF_TRACK, angle)
    xs = [p[0] for p in sweep]
    ys = [p[1] for p in sweep]
    wheel_env = {'min': [min(xs), min(ys)], 'max': [max(xs), max(ys)]}

    # Chassis rectangle, grown by the margin.
    x0 = bare['min'][0] - MARGIN
    x1 = bare['max'][0] + MARGIN
    y0 = bare['min'][1] - MARGIN
    y1 = bare['max'][1] + MARGIN
    chassis = {'min': [x0, y0], 'max': [x1, y1]}

    # The steered wheels reach past the chassis both forward and sideways; the
    # polygon has to include them, so take the hull of the chassis rectangle and the
    # wheel envelope rectangle.
    wx0 = min(wheel_env['min'][0], x0) - MARGIN
    wx1 = max(wheel_env['max'][0], x1) + MARGIN
    wy0 = min(wheel_env['min'][1], y0) - MARGIN
    wy1 = max(wheel_env['max'][1], y1) + MARGIN

    hull = convex_hull([
        (x0, y0), (x1, y0), (x1, y1), (x0, y1),
        (wx0, wy0), (wx1, wy0), (wx1, wy1), (wx0, wy1),
    ])
    # Order the hull clockwise starting from the rear-left corner for a readable
    # footprint string.
    hull = [(round(x, 3), round(y, 3)) for x, y in hull]
    start = min(range(len(hull)), key=lambda i: (hull[i][0], hull[i][1]))
    hull = hull[start:] + hull[:start]

    doc = {
        'source': 'sim/hz_hunter_full_description/geometry_report.json',
        'base_link': 'rear-axle wheel-centre midpoint, X forward, Y left',
        'inputs': {
            'bare_chassis_bounds_m': bare,
            'front_wheel_rectangle_m': {'length': 2 * WHEEL_HALF_LEN,
                                        'width': 2 * WHEEL_HALF_WID,
                                        'centre_x': FRONT_AXLE_X,
                                        'centre_y': [-HALF_TRACK, HALF_TRACK]},
            'steering_swept_rad': [-STEER_MAX, STEER_MAX],
            'margin_m': MARGIN,
        },
        'swept_wheel_envelope_m': wheel_env,
        'chassis_with_margin_m': chassis,
        'footprint_polygon_m': [[x, y] for x, y in hull],
        'footprint_string': '[' + ', '.join(f'[{x}, {y}]' for x, y in hull) + ']',
        'old_footprint_m': {'min': [-0.50, -0.395], 'max': [0.52, 0.395],
                            'source': 'senior nav2_params.yaml, copied verbatim'},
        'nose_gain_m': round(hull_max_x(hull) - 0.52, 3),
        'why_a_rectangle': ('the steered wheels sweep to y = +/-0.437 m, wider than the '
                            'chassis at every x, so the convex hull of chassis and wheel '
                            'envelope closes into a single rectangle'),
        'concave_alternative_m': [[round(x0, 3), round(y0, 3)],
                                  [0.452, round(y0, 3)],
                                  [0.452, round(wy0, 3)],
                                  [round(wx1, 3), round(wy0, 3)],
                                  [round(wx1, 3), round(wy1, 3)],
                                  [0.452, round(wy1, 3)],
                                  [0.452, round(y1, 3)],
                                  [round(x0, 3), round(y1, 3)]],
        'concave_note': ('keeps the rear at +/-0.393 instead of +/-0.457 and saves about '
                         '0.13 m of width behind the front axle, at the cost of a concave '
                         'footprint; not used until a corridor needs it'),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'footprint_polygon.json').write_text(json.dumps(doc, indent=1), encoding='utf-8')
    draw(doc)
    print(json.dumps({'polygon': doc['footprint_polygon_m'],
                      'nose_gain_m': doc['nose_gain_m'],
                      'swept_y_m': round(max(abs(wheel_env['min'][1]), wheel_env['max'][1]), 3)},
                     indent=1))


def hull_max_x(hull):
    return max(x for x, _ in hull)


def draw(doc):
    """Sketch old and new outlines over the chassis and swept wheels."""
    scale = 220  # px per metre
    pad = 60
    pts_new = doc['footprint_polygon_m']
    xs = [p[0] for p in pts_new] + [-0.50, 0.52]
    ys = [p[1] for p in pts_new] + [-0.395, 0.395]
    xmin, xmax = min(xs) - 0.15, max(xs) + 0.15
    ymin, ymax = min(ys) - 0.15, max(ys) + 0.15
    w = int((xmax - xmin) * scale) + 2 * pad
    h = int((ymax - ymin) * scale) + 2 * pad
    img = Image.new('RGB', (w, h), 'white')
    d = ImageDraw.Draw(img)

    def to_px(x, y):
        return (pad + (x - xmin) * scale, pad + (ymax - y) * scale)

    # 1 m grid.
    gx = math.ceil(xmin)
    while gx <= xmax:
        d.line([to_px(gx, ymin), to_px(gx, ymax)], fill=(235, 235, 235))
        gx += 1
    gy = math.ceil(ymin)
    while gy <= ymax:
        d.line([to_px(xmin, gy), to_px(xmax, gy)], fill=(235, 235, 235))
        gy += 1

    old = doc['old_footprint_m']
    d.rectangle([to_px(old['min'][0], old['max'][1]), to_px(old['max'][0], old['min'][1])],
                outline=(200, 60, 60), width=2)

    bare = doc['inputs']['bare_chassis_bounds_m']
    d.rectangle([to_px(bare['min'][0], bare['max'][1]), to_px(bare['max'][0], bare['min'][1])],
                outline=(60, 60, 60), width=1)

    d.polygon([to_px(x, y) for x, y in pts_new], outline=(30, 120, 220))
    for x, y in pts_new:
        px = to_px(x, y)
        d.ellipse([px[0] - 3, px[1] - 3, px[0] + 3, px[1] + 3], fill=(30, 120, 220))

    # Rear axle origin and the steered wheels at full lock.
    ox, oy = to_px(0.0, 0.0)
    d.line([ox - 8, oy, ox + 8, oy], fill=(0, 150, 0), width=2)
    d.line([ox, oy - 8, ox, oy + 8], fill=(0, 150, 0), width=2)
    for side in (+1, -1):
        for ang in (-STEER_MAX, STEER_MAX):
            pts = [to_px(x, y) for x, y in wheel_corners(FRONT_AXLE_X, side * HALF_TRACK, ang)]
            d.polygon(pts, outline=(240, 170, 30))

    d.text((pad, 12), 'red = old footprint, blue = new, grey = chassis, orange = wheels at lock',
           fill=(40, 40, 40))
    d.text((pad, 30), f"nose gain {doc['nose_gain_m']} m", fill=(40, 40, 40))
    img.save(OUT / 'footprint_sketch.png')


if __name__ == '__main__':
    main()
