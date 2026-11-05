"""Offline derivative of the verified Oct 11 archive; never changes the inputs.

This is a ground-evidence candidate, not a ray-cast occupancy reconstruction.
Only a cell containing an observed floor return can be a candidate free cell.
Any return in the obstacle height interval wins. No hole filling is performed.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import platform
import sys

sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage
from PIL import Image
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch, Rectangle

ROOT = Path(r"F:\rob-memory")
BASE = ROOT / "maps/lab_20261011/lab_20261011_155236_369289"
RAW = BASE / "merged/map_raw.pcd"
POSES = BASE / "pcd/scans_pos.json"
DETAIL = ROOT / "outputs/map_inspection_lab_155236_20261011/detail_stats.json"
OUT = Path(__file__).resolve().parent
STEM = "lab_155236_floor_evidence_candidate"
EXPECTED_RAW = "a57844447f23c2c02cd30f101aaf622ae86eb8a1cd207b684a940fa464d06441"
EXPECTED_POSES = "fd111e7da47165af78d8c8077df2284b0b328390a0e77a32543a486a85b48518"
RES = 0.05
FLOOR_BAND = 0.04
OBSTACLE_MIN = 0.10
OBSTACLE_MAX = 1.50
MARGIN = 0.50


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_only_signature(path):
    stat = Path(path).stat()
    return {"path": str(path), "bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns, "sha256": sha(path)}


def main():
    targets = [OUT / (STEM + suffix) for suffix in (".pgm", ".yaml")]
    targets += [OUT / name for name in
                ("raster_evidence.npz", "conversion_report.json", "candidate_preview.png")]
    if any(path.exists() for path in targets):
        raise FileExistsError("Candidate outputs already exist; do not overwrite them.")
    inputs = [RAW, POSES, DETAIL]
    before = [read_only_signature(path) for path in inputs]
    assert before[0]["sha256"] == EXPECTED_RAW
    assert before[1]["sha256"] == EXPECTED_POSES
    sys.path.insert(0, str(ROOT / "hz_mapping_tools_20261011"))
    from pcd_export import pcd_info
    writer_path = ROOT / "knowledge_base/Hunter知识库/脚本/xt32_nav_bringup_scripts/pcd_to_2d_map.py"
    spec = importlib.util.spec_from_file_location("reference_map_writer", writer_path)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    writer_before = read_only_signature(writer_path)
    info = pcd_info(RAW)
    assert (info["fields"], info["sizes"], info["types"], info["counts"]) == (
        ["x", "y", "z", "rgb"], [4] * 4, ["F", "F", "F", "U"], [1] * 4)
    dtype = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("rgb", "<u4")])
    raw = np.memmap(RAW, dtype=dtype, mode="r", offset=info["offset"], shape=(info["points"],))
    detail = json.loads(DETAIL.read_text(encoding="utf-8"))
    normal = np.asarray(detail["floor_plane_normal_xyz"], dtype=np.float64)
    offset = float(detail["floor_plane_offset_m"])
    assert abs(np.linalg.norm(normal) - 1.0) < 1e-8 and normal[2] > 0.99
    min_x = float(np.floor((float(raw["x"].min()) - MARGIN) / RES) * RES)
    min_y = float(np.floor((float(raw["y"].min()) - MARGIN) / RES) * RES)
    max_x = float(np.ceil((float(raw["x"].max()) + MARGIN) / RES) * RES)
    max_y = float(np.ceil((float(raw["y"].max()) + MARGIN) / RES) * RES)
    width = int(round((max_x - min_x) / RES))
    height = int(round((max_y - min_y) / RES))
    floor_count = np.zeros((height, width), dtype=np.uint32)
    obstacle_count = np.zeros_like(floor_count)
    selected_counts = {"floor_returns": 0, "obstacle_returns": 0}
    for first in range(0, len(raw), 1_000_000):
        block = raw[first:first + 1_000_000]
        x, y, z = (block[axis].astype(np.float64) for axis in "xyz")
        assert np.isfinite(x).all() and np.isfinite(y).all() and np.isfinite(z).all()
        relative_height = x * normal[0] + y * normal[1] + z * normal[2] + offset
        ix = np.floor((x - min_x) / RES).astype(np.int64)
        iy = np.floor((y - min_y) / RES).astype(np.int64)
        assert ((ix >= 0) & (ix < width) & (iy >= 0) & (iy < height)).all()
        indices = iy * width + ix
        floor_mask = np.abs(relative_height) <= FLOOR_BAND
        obstacle_mask = (relative_height >= OBSTACLE_MIN) & (relative_height <= OBSTACLE_MAX)
        for dest, mask, key in ((floor_count, floor_mask, "floor_returns"),
                                (obstacle_count, obstacle_mask, "obstacle_returns")):
            tally = np.bincount(indices[mask], minlength=height * width)
            dest += tally.astype(np.uint32).reshape(height, width)
            selected_counts[key] += int(mask.sum())
        print(f"Processed {min(first + len(block), len(raw))}/{len(raw)} points", flush=True)
    occupied = obstacle_count > 0
    floor_seen = floor_count > 0
    free = floor_seen & ~occupied
    world_grid = np.full((height, width), 205, dtype=np.uint8)
    world_grid[free] = 254
    world_grid[occupied] = 0
    img = np.flipud(world_grid).copy()
    # Reuse the reference script's image writer, but not its all-free initialization.
    reference.write_pgm(targets[0], img)
    metadata = {"image": targets[0].name, "mode": "trinary", "resolution": RES,
                "origin": [min_x, min_y, 0.0], "negate": 0,
                "occupied_thresh": 0.65, "free_thresh": 0.196}
    with targets[1].open("x", encoding="utf-8", newline="\n") as stream:
        yaml.safe_dump(metadata, stream, sort_keys=False)
    decoded_image = np.asarray(Image.open(targets[0]))
    assert np.array_equal(decoded_image, img)
    loaded_metadata = yaml.safe_load(targets[1].read_text(encoding="utf-8"))
    assert loaded_metadata == metadata and (OUT / loaded_metadata["image"]).is_file()
    # Exact trinary rule in Nav2 Humble map_io.cpp, including strict thresholds and Y flip.
    probability = 1.0 - decoded_image.astype(np.float64) / 255.0
    decoded = np.full(decoded_image.shape, -1, dtype=np.int8)
    decoded[probability > metadata["occupied_thresh"]] = 100
    decoded[probability < metadata["free_thresh"]] = 0
    decoded = np.flipud(decoded)
    assert np.array_equal(decoded == 100, occupied)
    assert np.array_equal(decoded == 0, free)
    assert not ((decoded == 0) & ~floor_seen).any()
    assert ((decoded == -1) == (~floor_seen & ~occupied)).all()
    assert np.all(decoded[0, :] == -1) and np.all(decoded[-1, :] == -1)
    assert np.all(decoded[:, 0] == -1) and np.all(decoded[:, -1] == -1)
    np.savez_compressed(OUT / "raster_evidence.npz", floor_count=floor_count,
                        obstacle_count=obstacle_count, origin=np.array([min_x, min_y]),
                        resolution=RES, floor_normal=normal, floor_offset=offset)
    labels, number = ndimage.label(free)
    components = np.bincount(labels.ravel())[1:]
    font = Path(r"C:\Windows\Fonts\msyh.ttc")
    if font.exists():
        font_manager.fontManager.addfont(str(font))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({"font.size": 10, "axes.unicode_minus": False})
    # This rectangle is for PNG viewing only; the PGM retains the full original XY extent.
    rotation = np.array(detail["xyz_to_uvz_columns"])[:2, :2]
    u_bounds, v_bounds = detail["crop_uvz_m"][:2]
    corners = np.array([[u, v] for u in u_bounds for v in v_bounds]) @ rotation.T
    zoom_x = [float(corners[:, 0].min()), float(corners[:, 0].max())]
    zoom_y = [float(corners[:, 1].min()), float(corners[:, 1].max())]
    fig, axes = plt.subplots(1, 2, figsize=(16, 6.8),
                             gridspec_kw={"width_ratios": [1, 1.65]}, layout="constrained")
    extent = [min_x, max_x, min_y, max_y]
    for ax in axes:
        ax.imshow(img, cmap="gray", vmin=0, vmax=255, extent=extent,
                  origin="upper", interpolation="nearest")
        ax.set_aspect("equal")
        ax.set(xlabel="原地图 X / m", ylabel="原地图 Y / m")
    axes[0].set_title("完整保存范围 · 包含外围点群")
    axes[0].add_patch(Rectangle((zoom_x[0], zoom_y[0]), zoom_x[1] - zoom_x[0],
                                zoom_y[1] - zoom_y[0], fill=False, lw=1.3, ec="#2675b8"))
    axes[1].set(xlim=zoom_x, ylim=zoom_y, title="实验室主体放大 · 不旋转或改变地图坐标")
    legend = [Patch(facecolor="black", label="障碍命中"),
              Patch(facecolor="#fefefe", edgecolor="#777777", label="地面观测支持的候选空闲"),
              Patch(facecolor="#cdcdcd", label="未知（未填白）")]
    fig.legend(handles=legend, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.005))
    fig.suptitle("第二轮 FAST-LIVO2 点云 → 二维候选图  |  0.05 m / 格", fontsize=16)
    fig.savefig(OUT / "candidate_preview.png", dpi=165, bbox_inches="tight")
    plt.close(fig)
    after = [read_only_signature(path) for path in inputs]
    assert before == after and writer_before == read_only_signature(writer_path)
    report = {"status": "offline_candidate_only_not_robot_validated",
              "source_unchanged": before == after, "inputs": before,
              "source_car_hashes_matched": True, "points": info["points"],
              "method": "Observed floor support and height-slice occupied endpoints; occupied wins; no rays or hole filling.",
              "reference_reuse": {"writer": writer_before, "function": "write_pgm",
                                  "pcd_parser": str(ROOT / "hz_mapping_tools_20261011/pcd_export.py")},
              "coordinate_frame": "Original FAST-LIVO2 XY; no rotation, registration, or recalibration.",
              "floor_plane": {"normal_xyz": normal.tolist(), "offset_m": offset,
                              "source": str(DETAIL)},
              "height_interval_m": [OBSTACLE_MIN, OBSTACLE_MAX],
              "floor_band_m": [-FLOOR_BAND, FLOOR_BAND], "resolution": RES,
              "width": width, "height": height, "origin": metadata["origin"],
              **selected_counts,
              "cells": {"occupied": int(occupied.sum()), "free_candidate": int(free.sum()),
                        "unknown": int((decoded == -1).sum()), "total": width * height},
              "free_components_4connected": int(number),
              "largest_free_component_cells": int(components.max()) if len(components) else 0,
              "verification": {"pgm_reload": True, "yaml_relative_image": True,
                               "humble_trinary_y_flip_and_labels": True,
                               "white_cells_without_floor_observation": 0,
                               "all_obstacle_hit_cells_preserved": True,
                               "unobserved_border_unknown": True,
                               "native_ros_map_load_tested": False,
                               "localization_or_navigation_tested": False},
              "limits": ["Floor returns do not certify the whole vertical clearance column.",
                         "Sparse floor coverage may leave disconnected free areas; not a navigation-ready claim.",
                         "No dynamic-object removal, hand painting, unknown-to-free filling, or obstacle deletion.",
                         "Height band is a review candidate and not a certified vehicle clearance envelope."],
              "python": platform.python_version(),
              "artifacts": [dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))
                            for path in targets if path.name != "conversion_report.json"]}
    with (OUT / "conversion_report.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({key: report[key] for key in ("status", "width", "height", "origin",
          "cells", "free_components_4connected", "largest_free_component_cells", "source_unchanged")},
          ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
