"""Subdivide broad wall areas; report every tested tile and selected local patches."""
import csv
import json
import numpy as np
import matplotlib.pyplot as plt
from inspect_current import BASE, OUT, read_map, in_box, fit_plane, save_json, set_style


def main():
    detail = json.loads((OUT / 'detail_stats.json').read_text(encoding='utf-8'))
    rotation = np.array(detail['xyz_to_uvz_columns'])
    voxels = np.load(OUT / 'voxel_data.npz')
    q = voxels['xyz'] @ rotation
    _, raw, xyz = read_map(BASE / 'merged/map_raw.pcd')
    qr = xyz @ rotation.astype(np.float32)
    saved = np.load(OUT / 'trajectory_data.npz')
    counts, poses = saved['counts'], saved['poses']
    boundaries = np.r_[0, np.cumsum(counts)]
    candidates = []
    datasets = [
        ('near', 0, [-2.45, -1.25], [-4.7, -4.1, -3.5, -2.9, -2.3, -1.7], [.8, 1.4, 2.0]),
        ('far', 0, [18.1, 19.4], [-4.6, -4.0, -3.4], [1.0, 1.7, 2.4]),
        ('side', 1, [-7.1, -6.0], [-.7, .4, 1.5, 2.6, 3.7, 4.8], [.9, 1.5, 2.1]),
    ]
    for group, axis, normal_bounds, starts, heights in datasets:
        tangential = 1-axis
        for start in starts:
            for z in heights:
                bounds = [[0., 0.], [0., 0.], [z, z+.4]]
                bounds[axis] = normal_bounds
                bounds[tangential] = [start, start+.4]
                vm = in_box(q, bounds)
                ri = np.flatnonzero(in_box(qr, bounds))
                if np.count_nonzero(vm) < 30 or len(ri) < 200:
                    candidates.append(dict(group=group, bounds_uvz_m=bounds,
                        voxel_points=int(vm.sum()), raw_points=len(ri), status='insufficient points'))
                    continue
                try:
                    n, d, fitting = fit_plane(q[vm], axis, limit=.02, iterations=250)
                except ValueError:
                    candidates.append(dict(group=group, bounds_uvz_m=bounds,
                        voxel_points=int(vm.sum()), raw_points=len(ri), status='no constrained plane'))
                    continue
                residual = qr[ri] @ n + d
                quantiles = np.percentile(residual, [2.5, 25, 50, 75, 97.5])
                batch = np.searchsorted(boundaries, ri, side='right') - 1
                early, late = batch < 350, batch >= len(counts)-350
                item = dict(group=group, bounds_uvz_m=bounds, voxel_points=int(vm.sum()), raw_points=len(ri),
                    status='measured', normal_uvz=n.tolist(), normal_xyz=(rotation@n).tolist(), offset_m=d,
                    fit_inlier_fraction=float(fitting['fit_inliers']/fitting['fit_points']),
                    residual_percentiles_m=quantiles.tolist(), central95_width_m=float(quantiles[-1]-quantiles[0]),
                    within3cm_fraction=float((np.abs(residual)<.03).mean()),
                    early_points=int(early.sum()), late_points=int(late.sum()))
                if early.sum()>=50 and late.sum()>=50:
                    item['early_median_m']=float(np.median(residual[early]))
                    item['late_median_m']=float(np.median(residual[late]))
                    item['late_minus_early_m']=item['late_median_m']-item['early_median_m']
                candidates.append(item)
    selected = []
    for group, *_ in datasets:
        usable=[c for c in candidates if c['group']==group and c['status']=='measured']
        usable.sort(key=lambda c: c['central95_width_m'])
        print(group, 'best four', json.dumps(usable[:4],ensure_ascii=False),flush=True)
        if usable:
            selected.append(usable[0])
    save_json('flat_patch_stats.json', dict(
        method='Fixed tangential 0.4 m by height 0.4 m tiles within broad wall bands; all raw points in each box. Selected lowest 95% width per band for LOCAL examples only.',
        candidate_count=len(candidates), measured_count=sum(c['status']=='measured' for c in candidates),
        selected_local_examples=selected, all_candidates=candidates,
        note='Selection intentionally finds locally coherent pieces and cannot estimate all-wall or global accuracy. Full broad-region distributions are separately retained in detail_stats.json.'))
    with (OUT/'patch_candidates.csv').open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['group','bounds_UVZ_m','raw_points','voxel_points','status','central95_width_cm','within3cm_fraction','fit_inlier_fraction'])
        for c in candidates:
            writer.writerow([c['group'],json.dumps(c['bounds_uvz_m']),c['raw_points'],c['voxel_points'],c['status'],
                c.get('central95_width_m',0)*100 if c['status']=='measured' else '',
                c.get('within3cm_fraction',''),c.get('fit_inlier_fraction','')])
    set_style()
    fig,axes=plt.subplots(2,3,figsize=(16,10),layout='constrained')
    names={'near':'左端局部小片段','far':'右端局部小片段','side':'长边局部小片段'}
    for i,c in enumerate(selected):
        indices=np.flatnonzero(in_box(qr,c['bounds_uvz_m']))
        n=np.array(c['normal_uvz']);res=qr[indices]@n+c['offset_m']
        # Tangential height coordinates expose multi-layer structure without hiding outliers.
        tangential=1 if c['group']!='side' else 0
        im=axes[0,i].scatter(qr[indices,tangential],qr[indices,2],c=res*100,s=1,cmap='coolwarm',vmin=-5,vmax=5)
        axes[0,i].set(xlabel=('V' if tangential else 'U')+' (m)',ylabel='Z (m)',title=names[c['group']])
        axes[0,i].set_aspect('equal');fig.colorbar(im,ax=axes[0,i],label='法向偏移 (cm)',shrink=.7)
        batch=np.searchsorted(boundaries,indices,side='right')-1
        thirds=np.minimum(batch*3//len(counts),2)
        bins=np.linspace(min(-5,np.percentile(res*100,.1)),max(5,np.percentile(res*100,99.9)),120)
        for g,col,label in [(0,'#178b9b','前 1/3'),(1,'#d79a37','中 1/3'),(2,'#bc3971','后 1/3')]:
            if np.count_nonzero(thirds==g):
                axes[1,i].hist(res[thirds==g]*100,bins=bins,density=True,histtype='step',lw=1.5,color=col,label=label)
        axes[1,i].set(xlabel='法向偏移 (cm)',ylabel='分布密度',title=f"95% 宽度 {c['central95_width_m']*100:.2f} cm；仅此片段")
        axes[1,i].legend(fontsize=8)
    fig.suptitle('平整小片段示例 · 从固定网格中选择局部一致性最好的一块 · 不代表全墙精度',fontsize=14)
    fig.savefig(OUT/'flat_patch_measurements.png',dpi=190);plt.close(fig)
    fig,ax=plt.subplots(figsize=(16,7),layout='constrained')
    height=q@np.array(detail['floor_plane_normal_uvz'])+detail['floor_plane_offset_m']
    core=in_box(q,detail['crop_uvz_m'])
    mask=core&(height>.4)&(height<2.2)
    ax.scatter(q[mask,0],q[mask,1],c=voxels['rgb'][mask]/255.,s=1)
    qp=poses[:,:3]@rotation
    ax.plot(qp[:,0],qp[:,1],color='#df4d35',lw=.8)
    for i,c in enumerate(selected):
        b=c['bounds_uvz_m']
        ax.add_patch(plt.Rectangle((b[0][0],b[1][0]),b[0][1]-b[0][0],b[1][1]-b[1][0],fill=False,edgecolor='#884ad8',lw=2))
        ax.annotate(str(i+1),((b[0][0]+b[0][1])/2,(b[1][0]+b[1][1])/2),xytext=(8,10),textcoords='offset points',color='#743dbb',fontsize=12)
    ax.set(xlim=detail['crop_uvz_m'][0],ylim=detail['crop_uvz_m'][1],xlabel='U (m)',ylabel='V (m)',title='紫框：三个局部小片段示例；框内全部原始点参与统计')
    ax.set_aspect('equal')
    fig.savefig(OUT/'flat_patch_locations.png',dpi=190);plt.close(fig)


if __name__=='__main__':
    main()
