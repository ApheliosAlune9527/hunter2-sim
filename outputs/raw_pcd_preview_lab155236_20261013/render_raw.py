"""Deterministic, read-only RGB rendering of the requested full-resolution PCD."""
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import math
import os
import time

os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["OMP_NUM_THREADS"] = "2"
import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parent
SOURCE = Path(r"F:\rob-memory\maps\lab_20261011\lab_20261011_155236_369289\merged\map_raw.pcd")
DTYPE = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("rgb", "<u4")])
CHUNK = 600_000
WIDTH, HEIGHT = 3840, 2160
BACKGROUND = (12, 18, 25)
SENTINEL = np.uint32(0xFFFFFFFF)
ANGLE = math.radians(-12)
ROTATION = np.array([
    [math.cos(ANGLE), -math.sin(ANGLE), 0],
    [math.sin(ANGLE), math.cos(ANGLE), 0],
    [0, 0, 1],
], dtype=np.float32)
# This is a camera-framing box, not a filter on input points.
LAB_FRAME = np.array([[-3.1, 20.5], [-7.8, 2.8], [-1.1, 3.85]])


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_header(path):
    fields = {}
    with path.open("rb") as stream:
        for _ in range(100):
            line = stream.readline()
            if not line:
                raise ValueError("PCD DATA header not found")
            text = line.decode("ascii").strip()
            if text and not text.startswith("#"):
                key, *value = text.split()
                fields[key] = value
                if key == "DATA":
                    offset = stream.tell()
                    break
        else:
            raise ValueError("PCD header too long")
    assert fields["FIELDS"] == ["x", "y", "z", "rgb"]
    assert fields["SIZE"] == ["4"] * 4
    assert fields["TYPE"] == ["F", "F", "F", "U"]
    assert fields["COUNT"] == ["1"] * 4
    assert fields["DATA"] == ["binary"]
    count = int(fields["POINTS"][0])
    assert count == 16_290_495
    assert offset + count * DTYPE.itemsize == path.stat().st_size
    return fields, offset, count


def camera_basis(elevation, azimuth):
    e, a = math.radians(elevation), math.radians(azimuth)
    toward_eye = np.array([math.cos(e) * math.cos(a),
                           math.cos(e) * math.sin(a), math.sin(e)])
    right = np.array([-math.sin(a), math.cos(a), 0.0])
    up = np.cross(toward_eye, right)
    basis = np.column_stack((right, up, toward_eye)).astype(np.float32)
    assert np.allclose(basis.T @ basis, np.eye(3), atol=1e-6)
    return basis


def scan_bounds(raw):
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    checked = 0
    for start in range(0, len(raw), CHUNK):
        stop = min(start + CHUNK, len(raw))
        xyz = np.column_stack([raw[c][start:stop] for c in "xyz"])
        assert np.isfinite(xyz).all(), "Nonfinite XYZ in source"
        q = xyz @ ROTATION
        lo = np.minimum(lo, q.min(axis=0))
        hi = np.maximum(hi, q.max(axis=0))
        checked += len(xyz)
    assert checked == len(raw)
    return np.column_stack((lo, hi))


def point_sprites(depth, rgb, ids, radius=1):
    """Circular point-display sprites; colors and positions are not averaged."""
    result_depth, result_rgb, result_ids = depth.copy(), rgb.copy(), ids.copy()
    h, w = depth.shape
    offsets = [(dy, dx)
               for dy in range(-radius, radius + 1)
               for dx in range(-radius, radius + 1)
               if 0 < dy * dy + dx * dx <= radius * radius]
    for dy, dx in offsets:
        sy = slice(max(0, -dy), min(h, h - dy))
        sx = slice(max(0, -dx), min(w, w - dx))
        ty = slice(max(0, dy), min(h, h + dy))
        tx = slice(max(0, dx), min(w, w + dx))
        source_depth = depth[sy, sx]
        target_depth = result_depth[ty, tx]
        mask = source_depth > target_depth
        target_depth[mask] = source_depth[mask]
        result_rgb[ty, tx][mask] = rgb[sy, sx][mask]
        result_ids[ty, tx][mask] = ids[sy, sx][mask]
    return result_depth, result_rgb, result_ids


def render(raw, name, elevation, azimuth, frame, margin=112, point_radius=1):
    start_time = time.perf_counter()
    destination = OUT / f"{name}.png"
    assert not destination.exists(), f"Output exists: {destination}"
    basis = camera_basis(elevation, azimuth)
    transform = ROTATION @ basis
    corners = np.array(list(itertools.product(*frame.tolist())), dtype=np.float32)
    framed = corners @ basis
    low, high = framed[:, :2].min(axis=0), framed[:, :2].max(axis=0)
    center = (low + high) / 2
    scale = min((WIDTH - 2 * margin) / float(high[0] - low[0]),
                (HEIGHT - 2 * margin) / float(high[1] - low[1]))
    depth = np.full(WIDTH * HEIGHT, -np.inf, dtype=np.float32)
    rgb = np.zeros(WIDTH * HEIGHT, dtype=np.uint32)
    ids = np.full(WIDTH * HEIGHT, SENTINEL, dtype=np.uint32)
    projected, in_view = 0, 0
    print(f"render {name}: {elevation}deg / {azimuth}deg; full source {len(raw):,}", flush=True)
    for start in range(0, len(raw), CHUNK):
        stop = min(start + CHUNK, len(raw))
        xyz = np.column_stack([raw[c][start:stop] for c in "xyz"])
        screen = xyz @ transform
        xx = (screen[:, 0] - center[0]) * scale + (WIDTH - 1) / 2
        yy = (HEIGHT - 1) / 2 - (screen[:, 1] - center[1]) * scale
        valid = (xx >= 0) & (xx <= WIDTH - 1) & (yy >= 0) & (yy <= HEIGHT - 1)
        offsets = np.flatnonzero(valid)
        projected += len(xyz)
        in_view += len(offsets)
        if len(offsets):
            px = np.rint(xx[valid]).astype(np.int32)
            py = np.rint(yy[valid]).astype(np.int32)
            pixel = py.astype(np.int64) * WIDTH + px
            zz = screen[valid, 2]
            # Larger depth is nearer to the camera. Keep the nearest raw point
            # in each pixel both within this chunk and across previous chunks.
            order = np.lexsort((zz, pixel))
            sorted_pixel = pixel[order]
            is_last = np.r_[sorted_pixel[1:] != sorted_pixel[:-1], True]
            nearest = order[is_last]
            target_pixel = pixel[nearest]
            nearest_depth = zz[nearest]
            replace = nearest_depth > depth[target_pixel]
            chosen_pixel = target_pixel[replace]
            source_offsets = offsets[nearest[replace]]
            depth[chosen_pixel] = nearest_depth[replace]
            rgb[chosen_pixel] = raw["rgb"][start:stop][source_offsets]
            ids[chosen_pixel] = (start + source_offsets).astype(np.uint32)
        if stop % (CHUNK * 8) == 0 or stop == len(raw):
            print(f"  projected {stop:,}/{len(raw):,}", flush=True)
    assert projected == len(raw)
    occupied_before = int(np.count_nonzero(ids != SENTINEL))
    _, rgb, ids = point_sprites(
        depth.reshape(HEIGHT, WIDTH),
        rgb.reshape(HEIGHT, WIDTH),
        ids.reshape(HEIGHT, WIDTH),
        radius=point_radius,
    )
    occupied = ids != SENTINEL
    canvas = np.empty((HEIGHT, WIDTH, 3), dtype=np.uint8)
    canvas[:] = BACKGROUND
    for channel, shift in enumerate((16, 8, 0)):
        canvas[:, :, channel][occupied] = ((rgb[occupied] >> shift) & 255).astype(np.uint8)
    assert np.all(ids[occupied] < len(raw))
    pixels = np.flatnonzero(occupied.ravel())
    checks = pixels[np.linspace(0, len(pixels) - 1, min(256, len(pixels))).astype(np.int64)]
    original_ids = ids.ravel()[checks]
    raw_colors = raw["rgb"][original_ids]
    expected = np.column_stack([(raw_colors >> s) & 255 for s in (16, 8, 0)]).astype(np.uint8)
    assert np.array_equal(canvas.reshape(-1, 3)[checks], expected)
    Image.fromarray(canvas).save(destination, compress_level=5)
    with Image.open(destination) as saved:
        assert saved.size == (WIDTH, HEIGHT) and saved.mode == "RGB"
        saved.load()
        saved_array = np.asarray(saved)
        assert np.array_equal(saved_array.reshape(-1, 3)[checks], expected)
    result = dict(
        file=str(destination), resolution=[WIDTH, HEIGHT],
        elevation_deg=elevation, azimuth_deg=azimuth,
        camera_framing_uvz_m=frame.tolist(),
        source_points_projected=projected, points_inside_view=in_view,
        occupied_pixels_before_sprites=occupied_before,
        displayed_pixels=int(occupied.sum()),
        point_display_size_px=point_radius * 2 + 1,
        full_source_rgb_samples_verified=len(checks),
        rgb_is_original_without_averaging=True,
        source_sampling="none",
        visibility="orthographic depth buffer; nearest original point per pixel",
        output_sha256=sha256(destination),
        seconds=round(time.perf_counter() - start_time, 3),
    )
    print(f"saved {destination.name}: {result['displayed_pixels']:,} point pixels; {result['seconds']}s", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--views", nargs="+", choices=["main", "top", "full", "dense"],
                        default=["main", "top", "full"])
    parser.add_argument("--manifest", default="render_manifest.json")
    args = parser.parse_args()
    before = json.loads((OUT / "source_before.json").read_text(encoding="utf-8"))
    initial_stat = SOURCE.stat()
    header, offset, count = read_header(SOURCE)
    assert count == before["points"] and initial_stat.st_size == before["bytes"]
    raw = np.memmap(SOURCE, dtype=DTYPE, mode="r", offset=offset, shape=(count,))
    assert raw.mode == "r"
    bounds = scan_bounds(raw)
    print(f"input: {count:,} finite original points; UVZ bounds {bounds.tolist()}", flush=True)
    results = []
    for view in args.views:
        if view == "main":
            results.append(render(raw, "map_raw_lab_4k", 55, -80, LAB_FRAME))
        elif view == "top":
            results.append(render(raw, "map_raw_top_4k", 90, -90, LAB_FRAME))
        elif view == "dense":
            results.append(render(raw, "map_raw_lab_clear_4k", 50, -75, LAB_FRAME,
                                  point_radius=2))
        else:
            results.append(render(raw, "map_raw_full_extent_4k", 55, -80, bounds, margin=64))
            assert results[-1]["points_inside_view"] == count
    after_sha = sha256(SOURCE)
    final_stat = SOURCE.stat()
    unchanged = (
        after_sha == before["source_sha256"].lower()
        and final_stat.st_size == initial_stat.st_size
        and final_stat.st_mtime_ns == initial_stat.st_mtime_ns
    )
    assert unchanged, "Source content or modification time changed"
    manifest = dict(
        source=str(SOURCE), source_points=count, source_bytes=final_stat.st_size,
        source_sha256_before=before["source_sha256"].lower(),
        source_sha256_after=after_sha, source_unchanged=unchanged,
        source_open_mode="read-only numpy memmap",
        nonfinite_xyz=0, header=header, input_uvz_bounds_m=bounds.tolist(),
        display_rotation_about_z_deg=-12, output_views=results,
        data_edits=[], voxel_downsampling=False, denoising=False,
        geometry_reconstruction=False, generative_image_model_used=False,
        note="All original points are projected for every view; camera framing and normal pixel occlusion determine visibility. No new PCD is written.",
    )
    with (OUT / args.manifest).open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    print(json.dumps(dict(source_points=count, source_unchanged=unchanged,
                         files=[v["file"] for v in results]), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
