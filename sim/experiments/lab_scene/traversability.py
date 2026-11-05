"""Orientation-aware traversability precheck for the selected lab scene.

Replaces the 0.95 m all-yaw disc envelope (manifest.json) with the real CAD
footprint from sim/hz_hunter_full_description/geometry_report.json, expressed
in the base_link frame (rear-axle centre, X forward, Y left).

Scope: static geometry only. Unknown cells are treated as blocked, exactly as
in build.py. This is NOT a kinodynamic reachability check: Ackermann cannot
rotate in place, so "feasible for at least one heading" is an upper bound.
"""
from collections import deque
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
SCENE = ROOT / 'outputs/hunter_research_platform_20261031/lab_scene_candidate'
GEOMETRY = ROOT / 'sim/hz_hunter_full_description/geometry_report.json'
RES = 0.05
HEADINGS = list(range(0, 360, 5))
# Half-cell margin so a cell that only partly overlaps the body still counts.
MARGIN = RES / 2


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_free():
    manifest = json.loads((SCENE / 'manifest.json').read_text(encoding='utf-8'))
    pixels = np.array(Image.open(SCENE / 'navigation_map.pgm'))
    if sha(SCENE / 'navigation_map.pgm') != manifest['source_occupancy_sha256']:
        raise ValueError('navigation_map.pgm no longer matches the recorded manifest')
    if not set(np.unique(pixels)).issubset({0, 205, 254}):
        raise ValueError('Unexpected occupancy classes')
    text = (SCENE / 'navigation_map.yaml').read_text(encoding='utf-8')
    origin = [float(v) for v in re.search(r'origin:\s*\[([^\]]+)\]', text).group(1).split(',')]
    return manifest, pixels, pixels == 254, origin


def disc_offsets(radius_cells):
    """Reproduce build.py safe_centres() exactly, for self-verification."""
    return [(dy, dx)
            for dy in range(-radius_cells, radius_cells + 1)
            for dx in range(-radius_cells, radius_cells + 1)
            if dx * dx + dy * dy <= radius_cells * radius_cells]


def rectangle_offsets(xmin, xmax, ymin, ymax, heading_deg):
    """Cell offsets (row, col) covered by the rotated footprint, plus a half cell.

    Image rows increase as world Y decreases, so world +Y maps to -row.
    """
    theta = math.radians(heading_deg)
    cos, sin = math.cos(theta), math.sin(theta)
    xs = (xmin - MARGIN, xmax + MARGIN)
    ys = (ymin - MARGIN, ymax + MARGIN)
    corners = []
    for x in xs:
        for y in ys:
            corners.append((x * cos - y * sin, x * sin + y * cos))
    world_x = [c[0] for c in corners]
    world_y = [c[1] for c in corners]
    col_lo = math.floor(min(world_x) / RES)
    col_hi = math.ceil(max(world_x) / RES)
    row_lo = math.floor(-max(world_y) / RES)
    row_hi = math.ceil(-min(world_y) / RES)
    # Half-plane test in the body frame: undo the rotation, compare with bounds.
    edges = ((xmin, xmax), (ymin, ymax))
    offsets = []
    for row in range(row_lo, row_hi + 1):
        wy = -row * RES
        for col in range(col_lo, col_hi + 1):
            wx = col * RES
            bx = wx * cos + wy * sin
            by = -wx * sin + wy * cos
            if edges[0][0] - MARGIN <= bx <= edges[0][1] + MARGIN and \
               edges[1][0] - MARGIN <= by <= edges[1][1] + MARGIN:
                offsets.append((row, col))
    if not offsets:
        raise ValueError('Empty footprint at heading ' + str(heading_deg))
    return offsets


def erode(free, offsets):
    """safe[y, x] is True only if free[y+dy, x+dx] for every footprint offset."""
    height, width = free.shape
    blocked = np.zeros_like(free)
    for dy, dx in offsets:
        start_y, stop_y = max(0, -dy), min(height, height - dy)
        start_x, stop_x = max(0, -dx), min(width, width - dx)
        dst = (slice(start_y, stop_y), slice(start_x, stop_x))
        src = (slice(start_y + dy, stop_y + dy), slice(start_x + dx, stop_x + dx))
        shifted = np.ones_like(free)
        shifted[dst] = free[src]
        blocked |= ~shifted
    return free & ~blocked


def largest_component(mask):
    """Return (size, points) of the largest 4-connected component."""
    seen = np.zeros_like(mask)
    best, best_points = 0, []
    height, width = mask.shape
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        queue = deque([(int(y), int(x))])
        seen[y, x] = True
        points = []
        while queue:
            cy, cx = queue.popleft()
            points.append((cy, cx))
            for yy, xx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= yy < height and 0 <= xx < width and mask[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    queue.append((yy, xx))
        if len(points) > best:
            best, best_points = len(points), points
    return best, best_points


def main():
    manifest, pixels, free, origin = load_free()
    geometry = json.loads(GEOMETRY.read_text(encoding='utf-8'))
    bounds = geometry['bare_chassis_bounds_m']
    xmin, xmax = bounds['min'][0], bounds['max'][0]
    ymin, ymax = bounds['min'][1], bounds['max'][1]

    # Self-verification: the recorded 0.95 m disc result must reproduce exactly.
    disc = erode(free, disc_offsets(19))
    disc_cells = int(disc.sum())
    disc_largest, _ = largest_component(disc)
    repro = {
        'safe_centre_cells': disc_cells,
        'largest_component_cells': disc_largest,
        'matches_manifest': disc_cells == manifest['safe_centre_cells']
                            and disc_largest == manifest['largest_safe_component_cells'],
    }

    any_heading = np.zeros_like(free)
    all_headings = np.ones_like(free)
    all_headings &= free
    per_heading = {}
    safe_zero = None
    for heading in HEADINGS:
        safe = erode(free, rectangle_offsets(xmin, xmax, ymin, ymax, heading))
        if heading == 0:
            safe_zero = safe.copy()
        any_heading |= safe
        all_headings &= safe
        per_heading[str(heading)] = int(safe.sum())

    any_cells = int(any_heading.sum())
    any_largest, any_points = largest_component(any_heading)
    all_cells = int(all_headings.sum())
    area = RES * RES

    # Initial pose for scene integration: inside the largest feasible region,
    # heading 0 possible, as close to that region's centroid as possible.
    points = np.array(any_points)
    centroid = points.mean(axis=0)
    usable = points[safe_zero[points[:, 0], points[:, 1]]]
    if len(usable) == 0:
        raise ValueError('No cell in the largest region supports heading 0')
    distance = (usable[:, 0] - centroid[0]) ** 2 + (usable[:, 1] - centroid[1]) ** 2
    row, col = (int(v) for v in usable[int(np.argmin(distance))])
    height = free.shape[0]
    placement = {
        'cell_row': row,
        'cell_col': col,
        'x_m': round(origin[0] + col * RES, 4),
        'y_m': round(origin[1] + (height - row) * RES, 4),
        'z_m': 0.167,
        'yaw_rad': 0.0,
        'heading_deg': 0,
        'basis': ('Centroid-nearest cell of the largest any-heading component that '
                  'also supports heading 0; z matches the reviewed production scene.'),
        'cell_feasible_all_headings': bool(all_headings[row, col]),
    }

    result = {
        'generated': '2026-11-04',
        'method': ('Oriented CAD footprint erosion at 5-degree heading steps; '
                   'unknown cells treated as blocked; unknown stayed unknown in the '
                   'navigation map. Static geometry precheck only.'),
        'inputs': {
            'navigation_map_sha256': sha(SCENE / 'navigation_map.pgm'),
            'geometry_report': 'sim/hz_hunter_full_description/geometry_report.json',
            'geometry_bounds_frame': geometry['coordinate_convention'],
            'footprint_m': {'x': [xmin, xmax], 'y': [ymin, ymax],
                            'length': round(xmax - xmin, 4),
                            'width': round(ymax - ymin, 4)},
            'resolution_m': RES,
            'headings_deg': HEADINGS,
            'cell_margin_m': MARGIN,
        },
        'self_check_0p95m_disc': repro,
        'baseline_all_yaw_disc_0p95m': {
            'radius_m': 0.95,
            'safe_centre_cells': disc_cells,
            'largest_component_cells': disc_largest,
            'largest_component_area_m2': round(disc_largest * area, 4),
        },
        'oriented_footprint': {
            'any_heading_cells': any_cells,
            'any_heading_area_m2': round(any_cells * area, 4),
            'largest_any_component_cells': any_largest,
            'largest_any_component_area_m2': round(any_largest * area, 4),
            'all_headings_cells': all_cells,
            'all_headings_area_m2': round(all_cells * area, 4),
            'gain_largest_component_factor': round(any_largest / disc_largest, 3)
                                             if disc_largest else None,
            'per_heading_cells': per_heading,
        },
        'suggested_initial_pose': placement,
        'interpretation': {
            'any_heading': 'Upper bound: cell admits at least one of 72 headings.',
            'all_headings': 'Cell admits every heading; the strict equivalent of the disc.',
            'not_checked': ('Ackermann in-place rotation, steering rate, dynamic obstacles, '
                            'inflation layers, localization uncertainty.'),
        },
        'navigation_validated': False,
    }

    out_json = SCENE / 'traversability_oriented.json'
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    # Preview: obstacles black, unknown grey, floor pale, feasibility overlaid.
    rgb = np.repeat(pixels[:, :, None], 3, axis=2)
    rgb[free] = [235, 235, 235]
    rgb[any_heading] = [90, 190, 120]
    rgb[all_headings] = [40, 110, 220]
    image = Image.fromarray(rgb).resize((1337, 738), Image.Resampling.NEAREST)
    canvas = Image.new('RGB', (1397, 880), 'white')
    canvas.paste(image, (30, 80))
    draw = ImageDraw.Draw(canvas)
    mx, my = 30 + placement['cell_col'], 80 + placement['cell_row']
    draw.line([(mx - 9, my), (mx + 9, my)], fill='red', width=2)
    draw.line([(mx, my - 9), (mx, my + 9)], fill='red', width=2)
    title = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 24)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
    draw.text((30, 20), 'Oriented footprint traversability: HUNTER 2.0 in lab_155236', fill='black', font=title)
    draw.text((30, 800),
              'Black: obstacle | Grey: unknown (blocked) | Light: floor evidence | '
              'Green: >=1 heading | Blue: all 72 headings', fill='black', font=small)
    draw.text((30, 830),
              'Largest connected any-heading region: %.2f m2 (disc baseline %.2f m2)'
              % (any_largest * area, disc_largest * area), fill='black', font=small)
    canvas.save(SCENE / 'traversability_oriented_preview.png')
    print(json.dumps({k: result[k] for k in ('self_check_0p95m_disc', 'oriented_footprint')},
                     ensure_ascii=True))


if __name__ == '__main__':
    main()
