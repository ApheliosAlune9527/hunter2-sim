"""Read-only geometric inspection of this saved laboratory mapping run."""
from pathlib import Path
import json
import re
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = Path(r'F:\rob-memory\maps\lab_20261011\lab_20261011_141011_768151')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(r'F:\rob-memory\hz_mapping_tools_20261011')))
from pcd_export import pcd_info


def read_points(path):
    info = pcd_info(path)
    assert info['fields'] == ['x', 'y', 'z', 'rgb']
    assert info['sizes'] == [4, 4, 4, 4]
    assert info['types'] == ['F', 'F', 'F', 'U']
    points = np.memmap(path, dtype=[('x', '<f4'), ('y', '<f4'), ('z', '<f4'), ('rgb', '<u4')],
                       mode='r', offset=info['offset'], shape=(info['points'],))
    xyz = np.column_stack([points[k] for k in 'xyz'])
    rgb = np.column_stack([(points['rgb'] >> shift) & 255 for shift in (16, 8, 0)]).astype(np.uint8)
    return info, points, xyz, rgb


def main():
    raw_info, raw, xyz, rgb = read_points(BASE / 'merged/map_raw.pcd')
    preview_info, preview, pxyz, prgb = read_points(BASE / 'merged/map_preview_015m.pcd')
    poses = np.loadtxt(BASE / 'pcd/scans_pos.json')
    meta = json.loads((BASE / 'validation.json').read_text(encoding='utf-8'))
    counts = np.asarray([f['points'] for f in meta['files']], dtype=np.int64)
    assert counts.sum() == len(xyz)
    assert len(poses) == len(counts), (len(poses), len(counts))
    finite = np.isfinite(xyz).all(axis=1)
    q = np.percentile(xyz[finite], [0, .1, 1, 5, 25, 50, 75, 95, 99, 99.9, 100], axis=0)
    diffs = np.diff(poses[:, :3], axis=0)
    quat = poses[:, 3:7]
    norms = np.linalg.norm(quat, axis=1)
    dot = np.sum(quat[:-1]*quat[1:], axis=1) / (norms[:-1]*norms[1:])
    angular_step = np.degrees(2*np.arccos(np.clip(np.abs(dot), 0, 1)))
    log = (BASE / 'mapping.log').read_text(encoding='utf-8', errors='replace')
    log = re.sub(r'\x1b\[[0-9;]*m', '', log)
    save_ids = np.array([int(x) for x in re.findall(r'current scan saved to[^\n]*?/(\d+)\.pcd', log)])
    assert len(save_ids) == len(counts) and np.array_equal(save_ids, np.arange(1, len(counts)+1))
    image_stamps = np.array([float(x) for x in re.findall(r'its header time: (\d+\.\d+)', log)])
    imu_stamps = np.array([float(x) for x in re.findall(r'get imu at time: (\d+\.\d+)', log)])
    summary = dict(
        raw_points=len(xyz), preview_points=len(pxyz), pcd_files=len(counts),
        nonfinite_points=int((~finite).sum()),
        xyz_percentiles={str(p): row.tolist() for p, row in zip([0, .1, 1, 5, 25, 50, 75, 95, 99, 99.9, 100], q)},
        rgb_all_zero_fraction=float((rgb == 0).all(axis=1).mean()),
        trajectory_start=poses[0,:3].tolist(), trajectory_end=poses[-1,:3].tolist(),
        trajectory_bounds=[poses[:,:3].min(axis=0).tolist(), poses[:,:3].max(axis=0).tolist()],
        trajectory_polyline_length_m=float(np.linalg.norm(diffs,axis=1).sum()),
        endpoint_separation_m=float(np.linalg.norm(poses[-1,:3]-poses[0,:3])),
        pose_step_percentiles_m=np.percentile(np.linalg.norm(diffs,axis=1),[50,95,99,100]).tolist(),
        angular_step_percentiles_deg=np.percentile(angular_step,[50,95,99,100]).tolist(),
        quaternion_norm_bounds=[float(norms.min()),float(norms.max())],
        points_per_chunk_percentiles=np.percentile(counts,[0,50,95,100]).tolist(),
        image_header_time_range=[float(image_stamps.min()),float(image_stamps.max())],
        image_header_time_count=len(image_stamps), imu_header_time_range=[float(imu_stamps.min()),float(imu_stamps.max())],
        imu_header_time_count=len(imu_stamps),
        no_point_lio_messages=len(re.findall(r'\[ LIO \]: No point',log)),
        no_point_vio_messages=len(re.findall(r'\[ VIO \] No point',log)),
        reset_imu_messages=log.count('Reset ImuProcess'),
        warnings=re.findall(r'[^\n]*(?:\[WARN\]|\[ERROR\])[^\n]*',log),
        shutdown_message_present='PCD 保存完成' in log,
    )
    (OUT / 'geometry_stats.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2),encoding='utf-8')
    np.savez_compressed(OUT / 'inspection_data.npz', poses=poses, counts=counts, image_stamps=image_stamps)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

    plt.rcParams.update({'font.size':10, 'axes.grid':True,'grid.alpha':.2})
    fig, axes = plt.subplots(2,2,figsize=(15,11),layout='constrained')
    lims = np.percentile(pxyz,[.1,99.9],axis=0)
    for ax, a,b,title in [(axes[0,0],0,1,'Top view: height color'),
                          (axes[0,1],0,2,'Front projection: height color'),
                          (axes[1,0],1,2,'Side projection: height color')]:
        ax.scatter(pxyz[:,a],pxyz[:,b],c=pxyz[:,2],s=1.5,cmap='turbo',vmin=lims[0,2],vmax=lims[1,2],rasterized=True)
        ax.plot(poses[:,a],poses[:,b],c='black',lw=.7,alpha=.7)
        ax.set(xlabel='XYZ'[a]+' (m)',ylabel='XYZ'[b]+' (m)',title=title)
        ax.set_aspect('equal')
        ax.set_xlim(lims[0,a]-.5,lims[1,a]+.5);ax.set_ylim(lims[0,b]-.5,lims[1,b]+.5)
    axes[1,1].hist(xyz[finite,2],bins=np.arange(np.floor(q[0,2]*50)/50, np.ceil(q[-1,2]*50)/50+.02,.02),color='#316a99')
    axes[1,1].set(xlabel='Z (m)',ylabel='Raw point count',title='Height histogram (2 cm bins)')
    fig.suptitle('Laboratory map: saved points and mapping trajectory',fontsize=16)
    fig.savefig(OUT/'initial_projections.png',dpi=160)
    plt.close(fig)

    fig=plt.figure(figsize=(13,9),layout='constrained')
    ax=fig.add_subplot(111,projection='3d')
    ax.scatter(pxyz[:,0],pxyz[:,1],pxyz[:,2],c=prgb/255.,s=1.7,depthshade=False)
    ax.plot(poses[:,0],poses[:,1],poses[:,2],c='#ff6048',lw=1.4)
    ax.set(xlabel='X (m)',ylabel='Y (m)',zlabel='Z (m)',title='Saved RGB map (15 cm preview) and trajectory')
    ax.set_box_aspect(np.maximum(lims[1]-lims[0],1))
    ax.view_init(elev=40,azim=-65)
    fig.savefig(OUT/'initial_rgb_view.png',dpi=160)
    plt.close(fig)

if __name__=='__main__':
    main()
