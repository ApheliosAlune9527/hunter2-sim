"""Geometry measurements and derived views; input files remain read-only."""
from pathlib import Path
import json
import re
import sys
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import median_filter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from inspect_map import BASE, OUT, read_points
from pcd_export import pcd_header, pcd_info

RNG = np.random.default_rng(20261011)


def voxel_centroids(xyz, rgb, size=.05):
    keys = np.floor(xyz/size).astype(np.int32)
    packed = keys.view(np.dtype((np.void, keys.dtype.itemsize*3))).ravel()
    _, first, inverse, counts = np.unique(packed, return_index=True, return_inverse=True, return_counts=True)
    centers = np.column_stack([np.bincount(inverse, weights=xyz[:,i], minlength=len(first))/counts for i in range(3)]).astype(np.float32)
    colors = np.column_stack([np.bincount(inverse, weights=rgb[:,i], minlength=len(first))/counts for i in range(3)])
    return centers, np.clip(np.rint(colors),0,255).astype(np.uint8), counts


def write_rgb_pcd(path, xyz, rgb, reference):
    data = np.empty(len(xyz),dtype=[('x','<f4'),('y','<f4'),('z','<f4'),('rgb','<u4')])
    for i,k in enumerate('xyz'):data[k]=xyz[:,i]
    data['rgb']=(rgb[:,0].astype(np.uint32)<<16)|(rgb[:,1].astype(np.uint32)<<8)|rgb[:,2].astype(np.uint32)
    with path.open('wb') as f:
        f.write(pcd_header(reference,len(data)))
        data.tofile(f)
    pcd_info(path)


def fit_plane(points, dep_axis, limit=.035, max_angle=20, iterations=350):
    other=[i for i in range(3) if i!=dep_axis]
    if len(points)>35000:points=points[RNG.choice(len(points),35000,replace=False)]
    design=np.column_stack([points[:,other],np.ones(len(points))])
    best=None;best_n=-1
    for _ in range(iterations):
        idx=RNG.choice(len(points),3,replace=False)
        try:coef=np.linalg.solve(design[idx],points[idx,dep_axis])
        except np.linalg.LinAlgError:continue
        if np.linalg.norm(coef[:2])>np.tan(np.radians(max_angle)):continue
        residual=(points[:,dep_axis]-(design[:,0]*coef[0]+design[:,1]*coef[1]+coef[2]))/np.sqrt(1+sum(coef[:2]**2))
        n=np.count_nonzero(np.abs(residual)<limit)
        if n>best_n:best_n=n;best=coef
    if best is None:raise ValueError('No plane fit')
    for _ in range(3):
        residual=points[:,dep_axis]-design@best
        mask=np.abs(residual)<limit*np.sqrt(1+sum(best[:2]**2))
        best=np.linalg.lstsq(design[mask],points[mask,dep_axis],rcond=None)[0]
    normal=np.zeros(3);normal[dep_axis]=1;normal[other]=-best[:2]
    d=-best[2];norm=np.linalg.norm(normal)
    return normal/norm,d/norm


def mask_box(xyz, bounds):
    result=np.ones(len(xyz),dtype=bool)
    for i,(lo,hi) in enumerate(bounds):result&=(xyz[:,i]>=lo)&(xyz[:,i]<=hi)
    return result


def patch_metrics(xyz,voxel_xyz,name,bounds,dep_axis):
    vpatch=voxel_xyz[mask_box(voxel_xyz,bounds)]
    normal,d=fit_plane(vpatch,dep_axis)
    rawpatch=xyz[mask_box(xyz,bounds)]
    residual=rawpatch@normal+d
    q=np.percentile(residual,[2.5,25,50,75,97.5])
    return dict(name=name,bounds=bounds,raw_points=len(rawpatch),voxel_points=len(vpatch),normal=normal.tolist(),offset=float(d),
                residual_quantiles_m=q.tolist(),central_95_percent_width_m=float(q[-1]-q[0]),
                within_3cm_fraction=float((np.abs(residual)<.03).mean()),within_5cm_fraction=float((np.abs(residual)<.05).mean()))


def main():
    info,raw,xyz,rgb=read_points(BASE/'merged/map_raw.pcd')
    data=np.load(OUT/'inspection_data.npz')
    poses,counts=data['poses'],data['counts']
    centers,colors,occupancy=voxel_centroids(xyz,rgb)
    write_rgb_pcd(OUT/'map_working_005m.pcd',centers,colors,info)
    # Isolation diagnostic only; peripheral connected surfaces are retained.
    tree=cKDTree(centers)
    support=tree.query_ball_point(centers,.20,return_length=True,workers=2)
    keep=support>=3
    write_rgb_pcd(OUT/'map_denoised_005m.pcd',centers[keep],colors[keep],info)
    metrics=[]
    for name,bounds,axis in [
        ('floor', [[0,5],[0,15],[-.85,-.50]],2),
        ('near_wall', [[-.5,3.5],[-3.12,-2.85],[-.3,1.0]],1),
        ('far_wall', [[0,5],[17.85,18.25],[.1,2.1]],1),
    ]:
        metrics.append(patch_metrics(xyz,centers,name,bounds,axis))
    floor=metrics[0];normal=np.array(floor['normal']);d=floor['offset']
    distance=centers@normal+d
    core=mask_box(centers,[[-2.5,8],[-4,19],[-1.1,3.5]])
    walls=core&(distance>.40)&(distance<2.0)
    floor_band=core&(np.abs(distance)<.12)
    early_late=[]
    boundaries=np.r_[0,np.cumsum(counts)]
    # Compare start and end observations in the original map frame, no registration.
    selections={'start':(0,350),'end':(len(counts)-350,len(counts))}
    for label,(a,b) in selections.items():
        arr=xyz[boundaries[a]:boundaries[b]]
        subset=arr[mask_box(arr,[[-.5,3.5],[-3.12,-2.85],[-.3,1.0]])]
        if len(subset):
            residual=subset@np.array(metrics[1]['normal'])+metrics[1]['offset']
            early_late.append({'period':label,'chunks':[a+1,b],'points':len(subset),
                               'wall_signed_median_m':float(np.median(residual)),
                               'wall_signed_quantiles_m':np.percentile(residual,[2.5,97.5]).tolist()})
    near_idx=np.nonzero(mask_box(xyz,[[-.5,3.5],[-3.12,-2.85],[-.3,1.0]]))[0]
    near_xyz=xyz[near_idx]
    near_residual=near_xyz@np.array(metrics[1]['normal'])+metrics[1]['offset']
    chunk_idx=np.searchsorted(boundaries,near_idx,side='right')-1
    groups=np.minimum(chunk_idx*3//len(counts),2)
    filtered=median_filter(poses[:,:3],size=(31,1),mode='nearest')
    smoothed_length=np.linalg.norm(np.diff(filtered[::15],axis=0),axis=1).sum()
    qstart=np.median(poses[:150,3:7],axis=0);qend=np.median(poses[-150:,3:7],axis=0)
    endpoint_rot=np.degrees(2*np.arccos(np.clip(np.abs(qstart@qend)/(np.linalg.norm(qstart)*np.linalg.norm(qend)),0,1)))
    stats=dict(voxel_size_m=.05,working_points=len(centers),denoised_points=int(keep.sum()),
               isolation_removed_points=int((~keep).sum()),isolation_radius_m=.20,minimum_neighbor_points_including_self=3,
               core_visualization_bounds=[[-2.5,8],[-4,19],[-1.1,3.5]],
               core_points=int(core.sum()),peripheral_points=int((~core).sum()),
               plane_patches=metrics,start_end_same_wall=early_late,
               floor_normal_tilt_from_z_deg=float(np.degrees(np.arccos(normal[2]))),
               points_below_floor_more_than_015m_in_core=int((core&(distance<-.15)).sum()),
               smoothed_trajectory_length_m=float(smoothed_length),
               estimated_start_end_orientation_difference_deg=float(endpoint_rot),
               note='Plane patch thickness is a surface consistency measure, not ground-truth accuracy. Endpoint differences are not a measured loop-closure error.')
    (OUT/'detail_stats.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False,indent=2))

    plt.rcParams.update({'font.size':10,'axes.grid':True,'grid.alpha':.16})
    fig,axes=plt.subplots(1,2,figsize=(13,10),layout='constrained')
    for ax,mask,title in [(axes[0],walls,'Wall / object slice: 0.4–2.0 m above fitted floor'),
                          (axes[1],floor_band,'Floor slice: within 12 cm of fitted plane')]:
        ax.scatter(centers[mask,0],centers[mask,1],c=distance[mask],s=1,cmap='viridis',rasterized=True)
        ax.plot(poses[:,0],poses[:,1],c='#e44834',lw=1.2,label='Estimated path')
        ax.scatter(*poses[0,:2],c='#222',s=45,marker='o',label='Start',zorder=4)
        ax.scatter(*poses[-1,:2],c='#e44834',s=70,marker='x',label='End',zorder=5)
        ax.set(xlim=(-2.5,8),ylim=(-4,19),xlabel='X (m)',ylabel='Y (m)',title=title)
        ax.set_aspect('equal');ax.legend(loc='upper right',fontsize=8)
    fig.suptitle('Main laboratory region — display crop only, original points retained',fontsize=13)
    fig.savefig(OUT/'lab_top_view.png',dpi=180);plt.close(fig)

    fig,axes=plt.subplots(2,2,figsize=(13,9),layout='constrained')
    axes[0,0].plot(poses[:,2],c='#26607a',lw=.7)
    axes[0,0].set(xlabel='Saved batch number',ylabel='Estimated Z (m)',title='Trajectory height')
    axes[0,1].hist((centers[floor_band]@normal+d),bins=np.linspace(-.12,.12,100),color='#26607a')
    axes[0,1].set(xlabel='Signed distance to floor plane (m)',ylabel='5 cm voxel count',title='Floor spread; ROI shown in report')
    for group,col,lab in [(0,'#178a9d','First third'),(1,'#e5a43b','Middle third'),(2,'#cb4075','Last third')]:
        axes[1,0].hist(near_residual[groups==group],bins=np.linspace(-.2,.2,140),density=True,histtype='step',color=col,lw=1.3,label=lab)
    axes[1,0].legend();axes[1,0].set(xlabel='Signed distance to near-wall plane (m)',ylabel='Density',title='Near-wall observations over the run')
    for item,col in zip(early_late,['#178a9d','#cb4075']):
        a,b=item['chunks'];arr=xyz[boundaries[a-1]:boundaries[b]]
        mask=mask_box(arr,[[-.5,3.5],[-3.12,-2.85],[-.3,1.0]])
        subset=arr[mask][::max(1,np.count_nonzero(mask)//30000)]
        axes[1,1].scatter(subset[:,0],subset[:,1],s=.3,c=col,alpha=.35,label=item['period'])
    axes[1,1].set(xlabel='X (m)',ylabel='Y (m)',title='Same wall: start and end, without re-registration')
    axes[1,1].legend(markerscale=6)
    fig.suptitle('Geometry consistency diagnostics — no ground-truth reference',fontsize=14)
    fig.savefig(OUT/'geometry_diagnostics.png',dpi=180);plt.close(fig)

    for azim,name in [(-60,'lab_rgb_view'),(120,'lab_rgb_reverse')]:
        fig=plt.figure(figsize=(13,8),facecolor='#101820',layout='constrained')
        ax=fig.add_subplot(111,projection='3d',facecolor='#101820')
        pts=centers[core & keep];cols=colors[core & keep]
        ax.scatter(pts[:,0],pts[:,1],pts[:,2],c=cols/255.,s=1,depthshade=False)
        ax.plot(poses[:,0],poses[:,1],poses[:,2],c='#ff7659',lw=1)
        ax.set(xlim=(-2.5,8),ylim=(-4,19),zlim=(-1.1,3.5))
        ax.set_box_aspect((10.5,23,4.6));ax.view_init(elev=38,azim=azim);ax.set_axis_off()
        ax.set_title('Laboratory map — 5 cm averaged RGB voxels, display crop',color='white',pad=6)
        fig.savefig(OUT/(name+'.png'),dpi=180,facecolor=fig.get_facecolor());plt.close(fig)

if __name__=='__main__':main()
