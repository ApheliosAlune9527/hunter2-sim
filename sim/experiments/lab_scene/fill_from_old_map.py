"""Derive the fill mask from the older map: where old free but new unknown.

Uses the rotation + FFT translation alignment from compare_2d_maps.py, inverts it,
and maps the old map's free cells into the new map's frame. Regions where the old
map says free but the new map says unknown are reported and optionally filled.
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
PAD = 40
RES = 0.05
VIEW_TOP_M = 12.0          # only report/fill above this y in the new map


def load(pgm, yaml):
    pixels = np.array(Image.open(pgm).convert('L'))
    origin = [float(v) for v in re.search(r'origin:\s*\[([^\]]+)\]',
                                          Path(yaml).read_text(encoding='utf-8')).group(1).split(',')]
    return pixels, origin


def fit_alignment(old_mask, new_points):
    """Return (angle, shift, old_centroid, new_centroid) mapping NEW -> OLD canvas."""
    height, width = old_mask.shape
    ch, cw = height + 2 * PAD, width + 2 * PAD
    old_canvas = np.zeros((ch, cw), dtype=np.float32)
    old_canvas[PAD:PAD + height, PAD:PAD + width] = old_mask.astype(np.float32)
    old_fft = np.fft.rfft2(old_canvas)
    oc = np.argwhere(old_mask).astype(float).mean(axis=0)
    nc = new_points.mean(axis=0)
    best = None
    for degrees in range(-15, 16):
        angle = math.radians(degrees)
        cos, sin = math.cos(angle), math.sin(angle)
        rot = np.array([[cos, -sin], [sin, cos]])
        moved = (new_points - nc) @ rot.T + oc + PAD
        inside = ((moved[:, 0] >= 0) & (moved[:, 0] < ch)
                  & (moved[:, 1] >= 0) & (moved[:, 1] < cw))
        picked = moved[inside].astype(int)
        canvas = np.zeros((ch, cw), dtype=np.float32)
        canvas[picked[:, 0], picked[:, 1]] = 1.0
        if canvas.sum() == 0:
            continue
        corr = np.fft.irfft2(old_fft * np.conj(np.fft.rfft2(canvas)), s=(ch, cw))
        offset = np.unravel_index(int(np.argmax(corr)), corr.shape)
        shift = np.array([offset[0] - ch if offset[0] > ch // 2 else offset[0],
                          offset[1] - cw if offset[1] > cw // 2 else offset[1]], dtype=float)
        shifted = np.roll(np.roll(canvas, int(shift[0]), axis=0), int(shift[1]), axis=1)
        score = float((old_canvas * shifted).sum()) / max(1.0, float(min(old_canvas.sum(), canvas.sum())))
        if best is None or score > best[0]:
            best = (score, degrees, shift)
    score, degrees, shift = best
    return degrees, shift, oc, nc


def main():
    old_pixels, old_origin = load(OLD, OLD_YAML)
    new_pixels, new_origin = load(NEW, NEW_YAML)
    old_free = old_pixels == 254
    new_height, new_width = new_pixels.shape
    old_height, old_width = old_pixels.shape

    degrees, shift, oc, nc = fit_alignment(old_pixels == 0,
                                           np.argwhere(new_pixels == 0).astype(float))
    angle = math.radians(degrees)
    cos, sin = math.cos(angle), math.sin(angle)
    rot = np.array([[cos, -sin], [sin, cos]])

    # Inverse of the fitted transform: old cell -> new cell.
    rows, cols = np.nonzero(old_free)
    old_pts = np.column_stack([rows, cols]).astype(float)
    new_pts = (old_pts - oc - shift) @ rot + nc

    expected = np.zeros_like(new_pixels, dtype=bool)
    pts = new_pts.astype(int)
    keep = ((pts[:, 0] >= 0) & (pts[:, 0] < new_height)
            & (pts[:, 1] >= 0) & (pts[:, 1] < new_width))
    expected[pts[keep, 0], pts[keep, 1]] = True

    # Only above VIEW_TOP_M and outside the existing free space.
    world_y = new_origin[1] + (new_height - np.arange(new_height) - 0.5) * RES
    top = world_y >= VIEW_TOP_M
    mismatch = expected & (new_pixels == 205) & top[:, None]
    # Keep only patches that touch the room's real free space, so the older map's
    # scan-ray artefacts outside the walls are not turned into floor.
    from collections import deque
    existing_free = new_pixels == 254
    keep = np.zeros_like(mismatch)
    seen = np.zeros_like(mismatch)
    for y, x in zip(*np.nonzero(mismatch)):
        if seen[y, x]:
            continue
        component = []
        queue = deque([(int(y), int(x))])
        seen[y, x] = True
        touches = False
        while queue:
            cy, cx = queue.popleft()
            component.append((cy, cx))
            for yy, xx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if not (0 <= yy < new_height and 0 <= xx < new_width):
                    continue
                if existing_free[yy, xx]:
                    touches = True
                elif mismatch[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    queue.append((yy, xx))
        if touches:
            for cy, cx in component:
                keep[cy, cx] = True
    mismatch = keep
    cells = int(mismatch.sum())

    # The unknown pocket was outlined by cells marked occupied; where the older map
    # says free, that outline is a boundary artefact, not a wall. Remove it, but only
    # next to the area just filled so genuine walls survive.
    def dilate1(mask):
        padded = np.pad(mask, 1)
        return (padded[1:-1, 1:-1] | padded[:-2, 1:-1] | padded[2:, 1:-1]
                | padded[1:-1, :-2] | padded[1:-1, 2:])

    near_fill = dilate1(mismatch)
    remove = (new_pixels == 0) & expected & top[:, None] & near_fill

    # The user confirmed this area is open floor: every occupied cell inside the
    # filled pocket that is not next to unknown space is a leftover scan fragment.
    ys, xs = np.nonzero(mismatch)
    if len(ys):
        r0, r1 = int(ys.min()), int(ys.max()) + 1
        c0, c1 = int(xs.min()), int(xs.max()) + 1
        pocket = np.zeros_like(mismatch)
        pocket[r0:r1, c0:c1] = True
        unknown = new_pixels == 205
        near_unknown = unknown.copy()
        for _ in range(2):
            near_unknown = dilate1(near_unknown)
        remove = remove | ((new_pixels == 0) & pocket & ~near_unknown)
    removed = int(remove.sum())

    overlay = np.stack([new_pixels] * 3, axis=-1).astype(np.uint8)
    overlay[mismatch] = [230, 60, 60]
    overlay[remove] = [60, 90, 230]
    out_png = SRC / 'lab_odom_06_mismatch.png'
    Image.fromarray(overlay).resize((new_width * 4, new_height * 4),
                                    Image.Resampling.NEAREST).save(out_png)

    filled = new_pixels.copy()
    filled[mismatch] = 254
    filled[remove] = 254
    Image.fromarray(filled).save(SRC / 'lab_odom_06_filled.pgm')
    (SRC / 'lab_odom_06_filled.yaml').write_text(
        NEW_YAML.read_text(encoding='utf-8').replace('lab_odom_06_new.pgm',
                                                     'lab_odom_06_filled.pgm'),
        encoding='utf-8')

    rows_top = np.nonzero(world_y >= VIEW_TOP_M)[0]
    r0 = int(rows_top.min()) if len(rows_top) else 0
    panels = []
    for title, filled_cells, removed_cells in (('before', None, None),
                                               ('after  green = filled, blue = fake wall removed',
                                                mismatch, remove)):
        crop = (filled if filled_cells is not None else new_pixels)[r0:, :]
        rgb = np.stack([crop] * 3, axis=-1).astype(np.uint8)
        if filled_cells is not None:
            rgb[filled_cells[r0:, :]] = [150, 220, 150]
            rgb[removed_cells[r0:, :]] = [120, 170, 240]
        img = Image.fromarray(rgb)
        img = img.resize((img.width * 4, img.height * 4), Image.Resampling.NEAREST)
        box = Image.new('RGB', (img.width, img.height + 30), 'white')
        box.paste(img, (0, 30))
        ImageDraw.Draw(box).text((8, 6), title, fill='black',
                                 font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18))
        panels.append(box)
    comp = Image.new('RGB', (panels[0].width + panels[1].width + 15, panels[0].height), 'white')
    comp.paste(panels[0], (0, 0))
    comp.paste(panels[1], (panels[0].width + 15, 0))
    comp.save(SRC / 'lab_odom_06_fill_before_after.png')
    (SRC / 'fill_from_old_receipt.json').write_text(json.dumps({
        'rule': 'old map free mapped into new frame, where new map is unknown',
        'alignment': {'rotation_deg': degrees, 'shift_cells': shift.tolist(),
                      'shift_m': [round(float(shift[0]) * RES, 3), round(float(shift[1]) * RES, 3)]},
        'only_above_y_m': VIEW_TOP_M,
        'cells_to_fill': cells,
        'cells_removed_fake_wall': removed,
        'outputs': {'overlay': str(out_png), 'filled': str(SRC / 'lab_odom_06_filled.pgm')},
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'rotation_deg': degrees, 'shift_cells': shift.tolist(),
                      'cells_to_fill': cells, 'cells_removed': removed,
                      'overlay': str(out_png)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
