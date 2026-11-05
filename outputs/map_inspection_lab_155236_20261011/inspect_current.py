"""Read-only inspection of one mapping archive; all derived files stay here."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys
import time

import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import median_filter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE = Path(r'F:\rob-memory\maps\lab_20261011\lab_20261011_155236_369289')
OUT = Path(__file__).resolve().parent
ARCHIVE = BASE.parent / (BASE.name + '.tar.gz')
sys.path.insert(0, r'F:\rob-memory\hz_mapping_tools_20261011')
from pcd_export import pcd_info, pcd_header, validate_pcd_dir, sha256_file

DTYPE = np.dtype([('x', '<f4'), ('y', '<f4'), ('z', '<f4'), ('rgb', '<u4')])
SHIFT = 1 << 20
RNG = np.random.default_rng(155236)


def save_json(name, value):
    with (OUT / name).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def read_map(path):
    info = pcd_info(path)
    assert (info['fields'], info['sizes'], info['types'], info['counts']) == (
        ['x', 'y', 'z', 'rgb'], [4]*4, ['F', 'F', 'F', 'U'], [1]*4)
    data = np.memmap(path, dtype=DTYPE, mode='r', offset=info['offset'], shape=(info['points'],))
    xyz = np.column_stack([data[c] for c in 'xyz'])
    return info, data, xyz


def colors_of(data):
    return np.column_stack([(data['rgb'] >> shift) & 255 for shift in (16, 8, 0)]).astype(np.uint8)


def voxel_keys(xyz, size):
    q = np.floor(xyz.astype(np.float64) / size).astype(np.int64)
    assert np.all((q >= -SHIFT) & (q < SHIFT)), 'Coordinates exceed packing range'
    q += SHIFT
    return (q[:, 0] << 42) | (q[:, 1] << 21) | q[:, 2]


def aggregate_voxels(xyz, rgb, size=.05):
    # Group at most 500k input points at a time, using float64 sums.
    keys = np.empty(0, dtype=np.int64)
    counts = np.empty(0, dtype=np.int64)
    sums = np.empty((0, 6), dtype=np.float64)
    preview_keys = np.empty(0, dtype=np.int64)
    for a in range(0, len(xyz), 500000):
        b = min(a + 500000, len(xyz))
        points, colors = xyz[a:b], rgb[a:b]
        valid = np.isfinite(points).all(axis=1)
        points, colors = points[valid], colors[valid]
        pk = np.unique(voxel_keys(points, .15))
        preview_keys = np.union1d(preview_keys, pk)
        local, inverse, n = np.unique(voxel_keys(points, size), return_inverse=True, return_counts=True)
        local_sums = np.column_stack([
            np.bincount(inverse, weights=points[:, i], minlength=len(local)) for i in range(3)
        ] + [np.bincount(inverse, weights=colors[:, i], minlength=len(local)) for i in range(3)])
        joined, inverse_join = np.unique(np.concatenate([keys, local]), return_inverse=True)
        next_sums = np.zeros((len(joined), 6), dtype=np.float64)
        next_counts = np.zeros(len(joined), dtype=np.int64)
        # Both local and previous key sets are individually unique.
        next_sums[inverse_join[:len(keys)]] = sums
        next_sums[inverse_join[len(keys):]] += local_sums
        next_counts[inverse_join[:len(keys)]] = counts
        next_counts[inverse_join[len(keys):]] += n
        keys, counts, sums = joined, next_counts, next_sums
        if a % 2500000 == 0 or b == len(xyz):
            print(f'voxel progress {b}/{len(xyz)}; occupied cells {len(keys)}', flush=True)
    centers = (sums[:, :3] / counts[:, None]).astype(np.float32)
    colors = np.clip(np.rint(sums[:, 3:] / counts[:, None]), 0, 255).astype(np.uint8)
    return keys, centers, colors, counts, preview_keys


def write_pcd(name, xyz, rgb, reference):
    data = np.empty(len(xyz), dtype=DTYPE)
    for i, axis in enumerate('xyz'):
        data[axis] = xyz[:, i]
    data['rgb'] = (rgb[:, 0].astype(np.uint32) << 16) | (rgb[:, 1].astype(np.uint32) << 8) | rgb[:, 2]
    with (OUT / name).open('xb') as f:
        f.write(pcd_header(reference, len(data)))
        data.tofile(f)
    return pcd_info(OUT / name)


def set_style(dark=False):
    font = Path(r'C:\Windows\Fonts\msyh.ttc')
    if font.exists():
        font_manager.fontManager.addfont(str(font))
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({'font.size': 10, 'axes.unicode_minus': False,
                         'axes.grid': not dark, 'grid.alpha': .15,
                         'figure.facecolor': '#101b25' if dark else 'white',
                         'axes.facecolor': '#101b25' if dark else 'white',
                         'text.color': '#eef4f8' if dark else '#182d3c',
                         'axes.labelcolor': '#d8e5ef' if dark else '#182d3c',
                         'xtick.color': '#b4c7d5' if dark else '#182d3c',
                         'ytick.color': '#b4c7d5' if dark else '#182d3c',
                         'axes.edgecolor': '#536b7b' if dark else '#b5c0c8'})


def snapshot():
    records = []
    for p in sorted(BASE.rglob('*')):
        if p.is_file():
            st = p.stat()
            records.append(dict(path=str(p), bytes=st.st_size, mtime_ns=st.st_mtime_ns,
                                sha256=sha256_file(p)))
    st = ARCHIVE.stat()
    records.append(dict(path=str(ARCHIVE), bytes=st.st_size, mtime_ns=st.st_mtime_ns,
                        sha256=sha256_file(ARCHIVE)))
    return records


def basic():
    t0 = time.perf_counter()
    save_json('source_manifest_before.json', snapshot())
    report = validate_pcd_dir(BASE / 'pcd')
    ids = [int(Path(f['path']).stem) for f in report['files']]
    assert ids == list(range(1, len(ids) + 1)), 'PCD numbering is not continuous'
    old = json.loads((BASE / 'validation.json').read_text(encoding='utf-8'))
    assert report['file_count'] == old['file_count']
    assert report['total_points'] == old['total_points']
    assert [f['points'] for f in report['files']] == [f['points'] for f in old['files']]
    chunk_payload = hashlib.sha256()
    for item in report['files']:
        with Path(item['path']).open('rb') as f:
            f.seek(item['offset'])
            for block in iter(lambda: f.read(1024*1024), b''):
                chunk_payload.update(block)
    info, raw, xyz = read_map(BASE / 'merged/map_raw.pcd')
    pinfo, preview, pxyz = read_map(BASE / 'merged/map_preview_015m.pcd')
    raw_payload = hashlib.sha256(memoryview(raw).cast('B')).hexdigest()
    assert chunk_payload.hexdigest() == raw_payload, 'Merged payload differs from ordered input chunks'
    assert info['points'] == report['total_points']
    print('integrity: input numbering, count and merged payload match', flush=True)
    poses = np.loadtxt(BASE / 'pcd/scans_pos.json')
    assert poses.shape == (report['file_count'], 7) and np.isfinite(poses).all()
    counts = np.array([f['points'] for f in report['files']], dtype=np.int64)
    finite = np.isfinite(xyz).all(axis=1)
    assert finite.all(), 'Nonfinite XYZ requires explicit handling before diagnostics'
    rgb = colors_of(raw)
    step = np.linalg.norm(np.diff(poses[:, :3], axis=0), axis=1)
    norms = np.linalg.norm(poses[:, 3:7], axis=1)
    dot = np.sum(poses[:-1, 3:7] * poses[1:, 3:7], axis=1) / (norms[:-1]*norms[1:])
    angles = np.degrees(2*np.arccos(np.clip(np.abs(dot), 0, 1)))
    endpoint_dot = np.abs(poses[0, 3:7] @ poses[-1, 3:7]) / (norms[0]*norms[-1])
    log = (BASE / 'mapping.log').read_text(encoding='utf-8', errors='replace')
    log = re.sub(r'\x1b\[[0-9;]*m', '', log)
    save_ids = np.array([int(x) for x in re.findall(r'current scan saved to[^\n]*?/(\d+)\.pcd', log)])
    assert np.array_equal(save_ids, np.array(ids)), 'Save messages do not match PCD files'
    images = np.array([float(x) for x in re.findall(r'its header time: (\d+\.\d+)', log)])
    imus = np.array([float(x) for x in re.findall(r'get imu at time: (\d+\.\d+)', log)])
    last_stamp = None
    save_stamps = []
    for line in log.splitlines():
        stamp = re.search(r'\[(?:INFO|WARN|ERROR)\] \[(\d+\.\d+)\]', line)
        if stamp:
            last_stamp = float(stamp[1])
        if 'current scan saved to' in line:
            save_stamps.append(last_stamp)
    have_log_times = len(save_stamps) == len(poses) and all(s is not None for s in save_stamps)
    seconds = np.array(save_stamps) - save_stamps[0] if have_log_times else np.arange(len(poses))
    if have_log_times:
        assert np.all(np.diff(seconds) >= 0)
    clean = median_filter(poses[:, :3], size=(31, 1), mode='nearest')
    quantiles = [0, .1, 1, 5, 25, 50, 75, 95, 99, 99.9, 100]
    warnings = {}
    for name in ['mapping', 'camera', 'lidar', 'imu']:
        text = (BASE / (name + '.log')).read_text(encoding='utf-8', errors='replace')
        text = re.sub(r'\x1b\[[0-9;]*m', '', text)
        hits = [line for line in text.splitlines() if re.search(r'\[(?:WARN|ERROR|FATAL)\]|Traceback|terminate called', line)]
        warnings[name] = dict(count=len(hits), first=hits[:12], last=hits[-8:])
    stats = dict(run=BASE.name, raw_points=len(xyz), preview_points=len(pxyz), pcd_files=len(ids),
        pose_records=len(poses), source_validation_matches=True, consecutive_ids=True,
        merged_payload_matches_chunks=True, merged_payload_sha256=raw_payload,
        archive_sha256=sha256_file(ARCHIVE), all_xyz_finite=bool(finite.all()),
        raw_xyz_percentiles={str(p): v.tolist() for p, v in zip(quantiles, np.percentile(xyz, quantiles, axis=0))},
        rgb_black_fraction=float((rgb == 0).all(axis=1).mean()),
        trajectory_start=poses[0, :3].tolist(), trajectory_end=poses[-1, :3].tolist(),
        trajectory_bounds=[poses[:, :3].min(axis=0).tolist(), poses[:, :3].max(axis=0).tolist()],
        trajectory_polyline_length_m=float(step.sum()),
        smoothed_subsampled_trajectory_length_m=float(np.linalg.norm(np.diff(clean[::15], axis=0), axis=1).sum()),
        endpoint_separation_m=float(np.linalg.norm(poses[-1, :3]-poses[0, :3])),
        endpoint_orientation_difference_deg=float(np.degrees(2*np.arccos(np.clip(endpoint_dot, 0, 1)))),
        step_percentiles_m=np.percentile(step, [50, 95, 99, 100]).tolist(),
        angular_step_percentiles_deg=np.percentile(angles, [50, 95, 99, 100]).tolist(),
        largest_translation_steps=[dict(after_batch=int(i+1), distance_m=float(step[i])) for i in np.argsort(step)[-8:][::-1]],
        quaternion_norm_range=[float(norms.min()), float(norms.max())],
        points_per_chunk=np.percentile(counts, [0, 50, 95, 100]).tolist(),
        log_save_times_available=have_log_times,
        log_save_duration_s=float(seconds[-1]) if have_log_times else None,
        log_save_step_percentiles_s=np.percentile(np.diff(seconds), [50, 95, 99, 100]).tolist() if have_log_times else None,
        image_stamps_count=len(images), image_range=[float(images.min()), float(images.max())] if len(images) else None,
        image_stamp_step_percentiles_s=np.percentile(np.diff(images), [50, 95, 99, 100]).tolist() if len(images)>1 else None,
        image_stamp_nonpositive_steps=int(np.count_nonzero(np.diff(images) <= 0)),
        imu_log_stamps_count=len(imus), imu_range=[float(imus.min()), float(imus.max())] if len(imus) else None,
        imu_log_stamp_nonpositive_steps=int(np.count_nonzero(np.diff(imus) <= 0)),
        no_point_lio_messages=len(re.findall(r'\[ LIO \]: No point', log)),
        no_point_vio_messages=len(re.findall(r'\[ VIO \] No point', log)),
        reset_imu_messages=log.count('Reset ImuProcess'),
        shutdown_message_present='PCD 保存完成' in log,
        warnings=warnings)
    save_json('geometry_stats.json', stats)
    np.savez_compressed(OUT / 'trajectory_data.npz', poses=poses, counts=counts,
                        seconds=seconds, images=images, steps=step, angles=angles)
    keys, centers, colors, occupancy, expected_preview_keys = aggregate_voxels(xyz, rgb)
    actual_preview_keys = voxel_keys(pxyz, .15)
    assert np.isfinite(pxyz).all()
    assert len(np.unique(actual_preview_keys)) == len(pxyz)
    assert np.array_equal(expected_preview_keys, np.sort(actual_preview_keys)), 'Preview voxel coverage differs'
    assert occupancy.sum() == len(xyz)
    # Include the point itself: remove only cells with fewer than two other nearby cells.
    support = cKDTree(centers).query_ball_point(centers, .20, return_length=True, workers=2)
    keep = support >= 3
    winfo = write_pcd('map_working_005m.pcd', centers, colors, info)
    dinfo = write_pcd('map_denoised_005m.pcd', centers[keep], colors[keep], info)
    np.savez_compressed(OUT / 'voxel_data.npz', xyz=centers, rgb=colors, occupancy=occupancy,
                        keys=keys, keep=keep, support=support)
    save_json('derived_stats.json', dict(voxel_size_m=.05, working_points=len(centers),
        denoised_points=int(keep.sum()), removed_isolated_points=int((~keep).sum()),
        original_points_in_removed_cells=int(occupancy[~keep].sum()),
        isolation_radius_m=.20, minimum_neighbors_including_self=3,
        preview_015m_unique_cells_and_full_coverage=True,
        derived_payload_bytes=[winfo['points']*16, dinfo['points']*16],
        method='Per occupied 5 cm voxel: mean XYZ, rounded mean RGB. No spatial crop.',
        occupancy_percentiles=np.percentile(occupancy, [0, 50, 95, 100]).tolist()))
    overview(centers, colors, occupancy, poses)
    print(json.dumps(stats, ensure_ascii=False, indent=2), flush=True)
    print(f'basic complete in {time.perf_counter()-t0:.1f}s', flush=True)


def overview(xyz, rgb, occupancy, poses):
    set_style()
    fig, axes = plt.subplots(2, 2, figsize=(15, 11), layout='constrained')
    zlo, zhi = np.percentile(xyz[:, 2], [1, 99])
    for ax, a, b, title in [(axes[0, 0], 0, 1, '全范围俯视'),
                            (axes[0, 1], 0, 2, '全范围 X–Z 投影'),
                            (axes[1, 0], 1, 2, '全范围 Y–Z 投影')]:
        sc = ax.scatter(xyz[:, a], xyz[:, b], c=xyz[:, 2], s=.5, cmap='turbo',
                        vmin=zlo, vmax=zhi, rasterized=True)
        ax.plot(poses[:, a], poses[:, b], color='#d92742', lw=1, label='估计轨迹')
        ax.set(xlabel='XYZ'[a] + ' (m)', ylabel='XYZ'[b] + ' (m)', title=title)
        ax.set_aspect('equal'); ax.margins(.04)
    axes[0, 0].legend(fontsize=8, markerscale=5)
    axes[1, 1].hist(xyz[:, 2], bins=250, weights=occupancy, color='#28728c')
    axes[1, 1].set(xlabel='Z (m)', ylabel='原始点数', title='高度分布：按原始点权重')
    fig.colorbar(sc, ax=axes[:, 0], label='地图 Z (m)', fraction=.02, shrink=.65)
    fig.suptitle('本轮全范围检查 · 5 cm 平均点云 · 坐标与全部外围结构保留', fontsize=16)
    fig.savefig(OUT / 'overview_full_extent.png', dpi=170)
    plt.close(fig)
    set_style(True)
    fig = plt.figure(figsize=(15, 10), layout='constrained')
    ax = fig.add_subplot(111, projection='3d')
    ax.scatter(xyz[:, 0], xyz[:, 1], xyz[:, 2], c=rgb/255., s=.7, depthshade=False)
    ax.plot(*poses[:, :3].T, color='#ff9a63', lw=1.1)
    ax.set_box_aspect(np.maximum(np.ptp(xyz, axis=0), 1))
    ax.view_init(elev=45, azim=-70); ax.set_axis_off()
    ax.set_title('完整扫描范围 · RGB 预览 · 5 cm 平均点云', fontsize=17, pad=15)
    fig.savefig(OUT / 'full_rgb_view.png', dpi=190, facecolor=fig.get_facecolor())
    plt.close(fig)
    set_style()


def in_box(xyz, bounds):
    mask = np.ones(len(xyz), dtype=bool)
    for i, (lo, hi) in enumerate(bounds):
        mask &= (xyz[:, i] >= lo) & (xyz[:, i] <= hi)
    return mask


def fit_plane(points, dependent, limit=.025, iterations=450, max_angle=15):
    points = np.asarray(points, dtype=np.float64)
    if len(points) > 40000:
        points = points[RNG.choice(len(points), 40000, replace=False)]
    assert len(points) >= 30, 'Too few points for plane fitting'
    other = [i for i in range(3) if i != dependent]
    design = np.column_stack([points[:, other], np.ones(len(points))])
    best, best_count = None, -1
    for _ in range(iterations):
        rows = RNG.choice(len(points), 3, replace=False)
        try:
            coef = np.linalg.solve(design[rows], points[rows, dependent])
        except np.linalg.LinAlgError:
            continue
        if np.linalg.norm(coef[:2]) > np.tan(np.deg2rad(max_angle)):
            continue
        residual = (points[:, dependent]-design[:, 0]*coef[0]-design[:, 1]*coef[1]-coef[2]) / np.sqrt(1+sum(coef[:2]**2))
        count = np.count_nonzero(np.abs(residual) < limit)
        if count > best_count:
            best, best_count = coef, count
    if best is None:
        raise ValueError('No plane meets orientation constraint')
    for _ in range(4):
        residual = points[:, dependent]-design @ best
        keep = np.abs(residual) < limit*np.sqrt(1+sum(best[:2]**2))
        best = np.linalg.lstsq(design[keep], points[keep, dependent], rcond=None)[0]
    normal = np.zeros(3)
    normal[dependent] = 1
    normal[other] = -best[:2]
    norm = np.linalg.norm(normal)
    return normal/norm, float(-best[2]/norm), dict(fit_points=len(points),
        fit_inliers=int(keep.sum()), ransac_limit_m=limit, ransac_iterations=iterations)


def detail():
    data = np.load(OUT / 'voxel_data.npz')
    centers, colors, keep = data['xyz'], data['rgb'], data['keep']
    saved = np.load(OUT / 'trajectory_data.npz')
    poses, counts, seconds = saved['poses'], saved['counts'], saved['seconds']
    info, raw, xyz = read_map(BASE / 'merged/map_raw.pcd')
    a = np.deg2rad(-12)
    rotation = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    q = centers @ rotation
    qr = xyz @ rotation.astype(np.float32)
    qp = poses[:, :3] @ rotation
    crop = [[-3.1, 20.5], [-7.8, 2.8], [-1.1, 3.85]]
    core = in_box(q, crop)
    floor_fit_bounds = [[0, 16], [-5.5, -1.5], [-.95, -.25]]
    normal, offset, floor_fit = fit_plane(q[in_box(q, floor_fit_bounds)], 2, limit=.02, max_angle=10)
    floor_height = q @ normal + offset
    trajectory_height = qp @ normal + offset
    world_normal = rotation @ normal
    boundaries = np.r_[0, np.cumsum(counts)]
    rois = [
        ('near_wall', '左端局部墙面', [[-2.35, -1.7], [-4.5, -3.8], [0.0, .8]], 0),
        ('far_wall', '右端局部墙面', [[18.45, 19.15], [-4.3, -3.2], [1.0, 1.8]], 0),
        ('side_wall', '长边局部墙面', [[.3, .9], [-6.95, -6.35], [1.1, 1.9]], 1),
    ]
    patches, residuals, time_groups, pairs = [], {}, {}, []
    for name, title, bounds, axis in rois:
        vm = in_box(q, bounds)
        n, d, fitting = fit_plane(q[vm], axis, limit=.025)
        indices = np.flatnonzero(in_box(qr, bounds))
        assert len(indices) > 0
        residual = qr[indices] @ n + d
        percentiles = np.percentile(residual, [2.5, 25, 50, 75, 97.5])
        batch = np.searchsorted(boundaries, indices, side='right') - 1
        item = dict(name=name, label=title, bounds_uvz_m=bounds, original_points=len(indices),
                    voxel_points=int(vm.sum()), fit=fitting, normal_uvz=n.tolist(),
                    normal_xyz=(rotation@n).tolist(), offset_m=d,
                    residual_percentiles_m=percentiles.tolist(),
                    central95_width_m=float(percentiles[-1]-percentiles[0]),
                    within3cm_fraction=float((np.abs(residual)<.03).mean()))
        patches.append(item); residuals[name] = residual
        time_groups[name] = np.minimum(batch*3//len(counts), 2)
        early, late = batch < 350, batch >= len(counts)-350
        if np.count_nonzero(early) >= 50 and np.count_nonzero(late) >= 50:
            pairs.append(dict(name=name, early_batches=[1, 350], late_batches=[len(counts)-349, len(counts)],
                early_points=int(early.sum()), late_points=int(late.sum()),
                early_median_m=float(np.median(residual[early])), late_median_m=float(np.median(residual[late])),
                late_minus_early_m=float(np.median(residual[late])-np.median(residual[early])),
                early95_m=np.percentile(residual[early], [2.5,97.5]).tolist(),
                late95_m=np.percentile(residual[late], [2.5,97.5]).tolist()))
        else:
            pairs.append(dict(name=name, early_points=int(early.sum()), late_points=int(late.sum()),
                              note='Insufficient paired observations; no start/end offset claim'))
    floor_patches = []
    for name, bounds in [
        ('floor_near', [[.2, 1.7], [-4.4, -2.3], [-.85, -.35]]),
        ('floor_middle', [[7.5, 9], [-4.4, -2.3], [-.85, -.25]]),
        ('floor_far', [[15.5, 17], [-4.4, -2.3], [-.85, -.15]])]:
        selected = qr[in_box(qr, bounds)]
        residual = selected @ normal + offset
        if len(residual):
            percentiles = np.percentile(residual, [2.5,25,50,75,97.5])
            floor_patches.append(dict(name=name, bounds_uvz_m=bounds, raw_points=len(selected),
                residual_percentiles_m=percentiles.tolist(), central95_width_m=float(percentiles[-1]-percentiles[0]),
                within3cm_fraction=float((np.abs(residual)<.03).mean())))
    moved = np.flatnonzero(np.linalg.norm(poses[:, :2]-poses[0, :2], axis=1)>.3)
    height_quantiles = np.percentile(trajectory_height, [0, 2.5, 25, 50, 75, 97.5, 100])
    stats = dict(display_rotation_deg=-12, xyz_to_uvz_columns=rotation.tolist(),
        crop_uvz_m=crop, crop_voxels=int(core.sum()), outside_display_crop_voxels=int((~core).sum()),
        floor_fit_bounds_uvz_m=floor_fit_bounds, floor_fit=floor_fit,
        floor_plane_normal_uvz=normal.tolist(), floor_plane_normal_xyz=world_normal.tolist(), floor_plane_offset_m=offset,
        floor_tilt_from_map_z_deg=float(np.degrees(np.arccos(np.clip(normal[2], -1, 1)))),
        estimated_height_above_floor_percentiles_m=height_quantiles.tolist(),
        estimated_height_above_floor_central95_range_m=float(height_quantiles[-2]-height_quantiles[1]),
        first_departure_03m_s=float(seconds[moved[0]]) if len(moved) else None,
        last_distance_over_03m_s=float(seconds[moved[-1]]) if len(moved) else None,
        main_motion_interval_s=float(seconds[moved[-1]]-seconds[moved[0]]) if len(moved) else None,
        patch_measurements=patches, same_patch_early_late=pairs, floor_patches=floor_patches,
        note='ROI widths describe selected surface consistency. Physical parking offsets, ground truth and precise per-pose sensor timestamps are unavailable.')
    save_json('detail_stats.json', stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2), flush=True)
    detail_images(q, colors, keep, core, qp, floor_height, trajectory_height, seconds,
                  crop, normal, offset, patches, residuals, time_groups, pairs, poses)


def detail_images(q, colors, keep, core, qp, height, trajectory_height, seconds,
                  crop, normal, offset, patches, residuals, time_groups, pairs, poses):
    set_style()
    fig, axes = plt.subplots(2, 1, figsize=(16, 12), layout='constrained')
    walls = core & keep & (height > .4) & (height < 2.2)
    floor = core & keep & (np.abs(height)<.12)
    for ax, mask, title in [(axes[0], walls, '墙面与设备切片：距拟合地面 0.4–2.2 m'),
                            (axes[1], floor, '地面切片：距拟合平面 ±12 cm')]:
        ax.scatter(q[mask, 0], q[mask, 1], c=colors[mask]/255., s=1.5, rasterized=True)
        ax.plot(qp[:,0], qp[:,1], color='#df4d35', lw=1.0, label='估计轨迹', alpha=.8)
        ax.scatter(*qp[0, :2], color='#0e6e91', marker='o', s=65, label='开始', zorder=5)
        ax.scatter(*qp[-1, :2], color='#ce3362', marker='x', s=75, label='结束', zorder=6)
        for i, item in enumerate(patches):
            b=item['bounds_uvz_m']
            ax.add_patch(plt.Rectangle((b[0][0], b[1][0]), b[0][1]-b[0][0], b[1][1]-b[1][0],
                                      fill=False, edgecolor='#5d48aa', lw=1.7))
            if ax is axes[0]:
                ax.annotate(str(i+1), ((b[0][0]+b[0][1])/2,(b[1][0]+b[1][1])/2),
                            xytext=(7, 7), textcoords='offset points', color='#5d48aa', fontsize=11)
        ax.set(xlim=crop[0], ylim=crop[1], xlabel='U (m)', ylabel='V (m)', title=title)
        ax.set_aspect('equal'); ax.legend(fontsize=9, loc='upper right')
    fig.suptitle('实验室主体俯视 · 5 cm 平均点云 · 紫框为本轮检查片段', fontsize=17)
    fig.savefig(OUT/'lab_top_view.png', dpi=190);plt.close(fig)
    for azim, name in [(-64, 'lab_rgb_view'), (116, 'lab_rgb_reverse')]:
        set_style(True)
        fig=plt.figure(figsize=(16, 9), layout='constrained')
        ax=fig.add_subplot(111, projection='3d')
        pts=q[core & keep];cols=colors[core & keep]
        ax.scatter(*pts.T, c=cols/255., s=.85, depthshade=False)
        ax.plot(*qp.T, color='#ffb06e', lw=1)
        ax.set(xlim=crop[0],ylim=crop[1],zlim=crop[2])
        ax.set_box_aspect([b[1]-b[0] for b in crop])
        ax.view_init(elev=48, azim=azim);ax.set_proj_type('ortho');ax.set_axis_off()
        ax.set_title('实验室主体 · 5 cm RGB 预览' + (' · 反向视角' if 'reverse' in name else ''), fontsize=17, pad=9)
        fig.text(.5,.035,'此图放大主体范围；完整扫描范围见 full_rgb_view.png，两份 5 cm PCD 均保存全范围。',
                 ha='center', color='#a6becf', fontsize=10)
        fig.savefig(OUT/(name+'.png'),dpi=210,facecolor=fig.get_facecolor());plt.close(fig)
    set_style()
    fig, axes=plt.subplots(2,2,figsize=(16,11),layout='constrained')
    axes[0,0].plot(seconds,poses[:,2]*100,color='#c58d38',lw=1,label='地图 Z')
    axes[0,0].plot(seconds,(trajectory_height-np.median(trajectory_height[:150]))*100,
                   color='#167b9b',lw=1,label='扣除拟合地面倾斜后的高度变化')
    axes[0,0].set(xlabel='最近保存日志时刻 (s)',ylabel='高度 / 变化 (cm)',title='车体高度：区分地图倾斜与高度变化')
    axes[0,0].legend(fontsize=8)
    im=axes[0,1].scatter(qp[:,0],qp[:,1],c=seconds,s=3,cmap='plasma')
    axes[0,1].set(xlabel='U (m)',ylabel='V (m)',title='估计轨迹（按记录时间着色）');axes[0,1].set_aspect('equal')
    fig.colorbar(im,ax=axes[0,1],label='s',shrink=.7)
    for ax,item in zip([axes[1,0],axes[1,1]],patches[:2]):
        name=item['name'];res=residuals[name]*100;groups=time_groups[name]
        limits=np.percentile(res,[.1,99.9]); limits=[min(limits[0],-8),max(limits[1],8)]
        bins=np.linspace(*limits,140)
        for group,col,label in [(0,'#178b9b','前 1/3 记录'),(1,'#d79a37','中 1/3 记录'),(2,'#bc3971','后 1/3 记录')]:
            if np.count_nonzero(groups==group):
                ax.hist(res[groups==group],bins=bins,density=True,histtype='step',lw=1.5,color=col,label=label)
        ax.set(xlabel='相对拟合墙面的法向偏移 (cm)',ylabel='分布密度',title=item['label']+'：95% 宽度 '+f"{item['central95_width_m']*100:.2f} cm")
        ax.legend(fontsize=8)
    fig.suptitle('本轮局部一致性诊断 · 没有现场尺寸或独立定位真值',fontsize=17)
    fig.savefig(OUT/'geometry_diagnostics.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(16,5),layout='constrained')
    for ax,item in zip(axes,patches):
        name=item['name'];res=residuals[name]*100
        limits=np.percentile(res,[.1,99.9]);bins=np.linspace(min(-8,limits[0]),max(8,limits[1]),150)
        ax.hist(res,bins=bins,color='#2b8395',alpha=.85)
        ax.axvline(0,color='#ba3959',lw=1)
        ax.set(xlabel='法向偏移 (cm)',ylabel='原始点数',title=item['label'])
        ax.text(.97,.94,f"95% 宽度 {item['central95_width_m']*100:.2f} cm\n±3 cm 内 {item['within3cm_fraction']*100:.1f}%",
                transform=ax.transAxes,va='top',ha='right',fontsize=9)
    fig.suptitle('局部表面检查：空间选框内全部原始点参与统计，未按残差二次筛选',fontsize=13)
    fig.savefig(OUT/'wall_patch_measurements.png',dpi=180);plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['basic', 'detail'])
    args = parser.parse_args()
    if args.stage == 'basic':
        basic()
    elif args.stage == 'detail':
        detail()


if __name__ == '__main__':
    main()
