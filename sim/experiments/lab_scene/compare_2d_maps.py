"""Compare two 2-D occupancy maps of the same lab.

The two slam_toolbox maps were produced by separate runs, so each has its own
map frame; absolute coordinates are not comparable. Occupied cells are aligned
by centroid + principal axis (sign ambiguity resolved by best overlap) before
overlap is measured. This is a shape comparison, not a metric re-registration.
"""
import json
import math
from pathlib import Path
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'outputs/lab_map_compare_20261105'
OLD = ROOT / 'outputs/senior_mapping_method_20261016/reference_assets/lab_odom_06.pgm'
OLD_YAML = ROOT / 'robot_assets/hunter_from_car_20261013_qjkgbbq5/hunter_nav_odom/maps/lab_odom_06.yaml'
NEW = SRC / 'lab_odom_06_new.pgm'
NEW_YAML = SRC / 'lab_odom_06_new.yaml'
RES = 0.05


def load(pgm, yaml):
    pixels = np.array(Image.open(pgm).convert('L'))
    text = Path(yaml).read_text(encoding='utf-8')
    origin = [float(v) for v in re.search(r'origin:\s*\[([^\]]+)\]', text).group(1).split(',')]
    return pixels, origin


def components(mask):
    """Largest 4-connected component size, using iterative flood fill."""
    seen = np.zeros_like(mask)
    best = 0
    h, w = mask.shape
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        stack = [(int(y), int(x))]
        seen[y, x] = True
        size = 0
        while stack:
            cy, cx = stack.pop()
            size += 1
            for yy, xx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    stack.append((yy, xx))
        best = max(best, size)
    return best


def dilate(mask, rounds=1):
    out = mask.copy()
    for _ in range(rounds):
        padded = np.pad(out, 1)
        out = (padded[1:-1, 1:-1] | padded[:-2, 1:-1] | padded[2:, 1:-1]
               | padded[1:-1, :-2] | padded[1:-1, 2:])
    return out


def describe(pixels, name):
    occ = pixels == 0
    unk = pixels == 205
    free = pixels == 254
    h, w = pixels.shape
    return {
        'name': name,
        'width_cells': int(w), 'height_cells': int(h),
        'extent_m': [round(w * RES, 2), round(h * RES, 2)],
        'occupied': int(occ.sum()), 'free': int(free.sum()), 'unknown': int(unk.sum()),
        'occupied_fraction_of_known': round(float(occ.sum()) / max(1, occ.sum() + free.sum()), 4),
        'largest_free_component_m2': round(components(free) * RES * RES, 2),
        'occupied_density_per_m2': round(float(occ.sum()) * RES * RES, 2),
    }


def principal_axis(points):
    centre = points.mean(axis=0)
    shifted = points - centre
    cov = np.cov(shifted.T)
    values, vectors = np.linalg.eigh(cov)
    major = vectors[:, int(np.argmax(values))]
    return centre, major


def best_align(old_mask, new_points):
    """Search rotation + FFT translation for the alignment maximising overlap."""
    height, width = old_mask.shape
    ch, cw = height + 80, width + 80
    old_canvas = np.zeros((ch, cw), dtype=np.float32)
    old_canvas[40:40 + height, 40:40 + width] = old_mask.astype(np.float32)
    old_fft = np.fft.rfft2(old_canvas)
    old_total = old_canvas.sum()
    oc = np.argwhere(old_mask).astype(float).mean(axis=0)
    nc = new_points.mean(axis=0)
    best = None
    for degrees in range(-15, 16):
        angle = math.radians(degrees)
        cos, sin = math.cos(angle), math.sin(angle)
        rot = np.array([[cos, -sin], [sin, cos]])
        moved = (new_points - nc) @ rot.T + oc + 40
        inside = ((moved[:, 0] >= 0) & (moved[:, 0] < ch)
                  & (moved[:, 1] >= 0) & (moved[:, 1] < cw))
        picked = moved[inside].astype(int)
        canvas = np.zeros((ch, cw), dtype=np.float32)
        canvas[picked[:, 0], picked[:, 1]] = 1.0
        total = canvas.sum()
        if total == 0:
            continue
        corr = np.fft.irfft2(old_fft * np.conj(np.fft.rfft2(canvas)), s=(ch, cw))
        offset = np.unravel_index(int(np.argmax(corr)), corr.shape)
        shift = (offset[0] - ch if offset[0] > ch // 2 else offset[0],
                 offset[1] - cw if offset[1] > cw // 2 else offset[1])
        shifted = np.roll(np.roll(canvas, shift[0], axis=0), shift[1], axis=1)
        overlap = float((old_canvas * shifted).sum())
        score = float(overlap) / max(1.0, float(min(old_total, total)))
        if best is None or score > best[0]:
            best = (score, degrees, shift, moved, picked)
    score, degrees, shift, moved, _ = best
    shifted_points = moved + np.array(shift, dtype=float)
    # Thin walls make exact overlap hypersensitive, so also report coverage as the
    # tolerance grows: fraction of new occupied cells within r cells of an old one.
    canvas = np.zeros((ch, cw), dtype=bool)
    pts = shifted_points.astype(int)
    inside = ((pts[:, 0] >= 0) & (pts[:, 0] < ch) & (pts[:, 1] >= 0) & (pts[:, 1] < cw))
    canvas[pts[inside, 0], pts[inside, 1]] = True
    tolerance = {}
    grown = old_canvas.astype(bool)
    total = max(1, int(canvas.sum()))
    for radius in range(0, 7):
        if radius:
            grown = dilate(grown, 1)
        tolerance[str(radius * 5) + 'cm'] = round(float((canvas & grown).sum()) / total, 4)
    return {
        'search': 'rotation -15..15 deg (1 deg step) + FFT translation',
        'rotation_deg': degrees,
        'translation_cells': [int(shift[0]), int(shift[1])],
        'occupied_overlap_fraction': round(score, 4),
        'translation_m': [round(shift[0] * RES, 3), round(shift[1] * RES, 3)],
        'coverage_of_new_walls_by_tolerance': tolerance,
        'caveat': ('Walls are 1-2 cells thick, so exact overlap is dominated by residual '
                   'registration error; read the tolerance table instead.'),
    }, shifted_points


def panel(pixels, title, font, small, width):
    h, w = pixels.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[pixels == 205] = [200, 200, 200]
    rgb[pixels == 254] = [255, 255, 255]
    rgb[pixels == 0] = [0, 0, 0]
    image = Image.fromarray(rgb).resize((width, int(h * width / w)), Image.Resampling.NEAREST)
    box = Image.new('RGB', (width, image.height + 34), 'white')
    box.paste(image, (0, 34))
    ImageDraw.Draw(box).text((6, 8), title, fill='black', font=small)
    return box


def main():
    old_pixels, old_origin = load(OLD, OLD_YAML)
    new_pixels, new_origin = load(NEW, NEW_YAML)
    old_info = describe(old_pixels, 'lab_odom_06 原件 (2026-09-22)')
    new_info = describe(new_pixels, 'lab_odom_06 新版 (2026-11-01)')
    old_info['origin'] = old_origin
    new_info['origin'] = new_origin
    overlap, shifted_points = best_align(old_pixels == 0,
                                         np.argwhere(new_pixels == 0).astype(float))

    # Side-by-side plus an aligned overlay in the old map's cell frame.
    height, width = old_pixels.shape
    overlay = np.zeros((height, width, 3), dtype=np.uint8)
    overlay[:, :] = [235, 235, 235]
    old_occ = old_pixels == 0
    overlay[old_occ] = [40, 40, 40]
    coords = (shifted_points - 40.0).astype(int)
    keep = ((coords[:, 0] >= 0) & (coords[:, 0] < height)
            & (coords[:, 1] >= 0) & (coords[:, 1] < width))
    coords = coords[keep]
    for a, b in coords:
        overlay[a, b] = [0, 120, 255] if old_occ[a, b] else [220, 40, 40]

    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 22)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 15)
    target = 520
    left = panel(old_pixels, 'old 2026-09-22 (baseline)', font, small, target)
    middle = panel(new_pixels, 'new 2026-11-01 (replacement)', font, small, target)
    right_img = Image.fromarray(overlay).resize((target, int(overlay.shape[0] * target / overlay.shape[1])),
                                               Image.Resampling.NEAREST)
    right = Image.new('RGB', (target, right_img.height + 34), 'white')
    right.paste(right_img, (0, 34))
    ImageDraw.Draw(right).text((6, 8), 'aligned overlay: grey=old  red=new only  blue=both',
                               fill='black', font=small)
    total_w = target * 3 + 40
    total_h = max(left.height, middle.height, right.height) + 95
    canvas = Image.new('RGB', (total_w, total_h), 'white')
    canvas.paste(left, (0, 60))
    canvas.paste(middle, (target + 20, 60))
    canvas.paste(right, (target * 2 + 40, 60))
    draw = ImageDraw.Draw(canvas)
    draw.text((6, 8), 'lab_odom_06: original vs 2026-11-01 replacement (5 cm cells)', fill='black', font=font)
    draw.text((6, total_h - 28),
              'best alignment: rotation %d deg, shift (%.2f, %.2f) m, occupied overlap %.1f%%'
              % (overlap['rotation_deg'], overlap['translation_m'][0],
                 overlap['translation_m'][1], overlap['occupied_overlap_fraction'] * 100),
              fill='black', font=small)
    out_png = SRC / 'lab_odom_06_comparison.png'
    canvas.save(out_png)

    result = {'old': old_info, 'new': new_info, 'alignment': overlap,
              'note': ('Separate slam_toolbox runs; map frames differ, so overlap is measured '
                       'after centroid + principal-axis alignment, not from absolute coordinates.'),
              'preview': str(out_png)}
    (SRC / 'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                        encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
