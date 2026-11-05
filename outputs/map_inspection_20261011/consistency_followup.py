from pathlib import Path
import json
import re
import numpy as np
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from inspect_map import BASE,OUT,read_points
from detail_geometry import mask_box,patch_metrics


def main():
    raw_info,raw,xyz,rgb=read_points(BASE/'merged/map_raw.pcd')
    derived_info,derived,vxyz,vrgb=read_points(OUT/'map_working_005m.pcd')
    saved=np.load(OUT/'inspection_data.npz')
    poses,counts=saved['poses'],saved['counts']
    detail=json.loads((OUT/'detail_stats.json').read_text(encoding='utf-8'))
    floor=detail['plane_patches'][0]
    normal=np.array(floor['normal']); d=floor['offset']
    height=poses[:,:3]@normal+d
    stamps=[];latest=None
    for line in (BASE/'mapping.log').read_text(encoding='utf-8',errors='replace').splitlines():
        match=re.search(r'\[(?:INFO|WARN|ERROR)\] \[(\d+\.\d+)\]',line)
        if match:latest=float(match[1])
        if 'current scan saved to' in line:stamps.append(latest)
    assert len(stamps)==len(poses) and all(s is not None for s in stamps)
    stamps=np.array(stamps);seconds=stamps-stamps[0]
    assert np.all(np.diff(seconds)>=0)
    moving=np.flatnonzero(np.linalg.norm(poses[:,:2]-poses[0,:2],axis=1)>.3)
    clean_near=patch_metrics(xyz,vxyz,'near_wall_flat_patch',[[-.45,-.1],[-3.08,-2.9],[0,.6]],1)
    clean_far=patch_metrics(xyz,vxyz,'far_wall_flat_patch',[[1.3,2.5],[17.85,18.25],[1.2,1.9]],1)
    boundaries=np.r_[0,np.cumsum(counts)]
    start=xyz[:boundaries[350]];end=xyz[boundaries[-351]:]
    box=[[-.45,-.1],[-3.08,-2.9],[0,.6]]
    start_patch=start[mask_box(start,box)];end_patch=end[mask_box(end,box)]
    start_res=start_patch@np.array(clean_near['normal'])+clean_near['offset']
    end_res=end_patch@np.array(clean_near['normal'])+clean_near['offset']
    if not len(start_patch) or not len(end_patch):raise ValueError('No paired flat-wall observations')
    sub=[(-2.5,8),(-4,19)]
    floor_vox=vxyz[mask_box(vxyz,[sub[0],sub[1],[-1.1,-.3]])]
    floor_res=floor_vox@normal+d
    local_floor_metrics=[]
    for lo,hi in [(0,4),(5,9),(10,14)]:
        band=floor_vox[(floor_vox[:,0]>0)&(floor_vox[:,0]<5)&(floor_vox[:,1]>lo)&(floor_vox[:,1]<hi)]
        residual=band@normal+d
        # Report the dominant floor surface AND explicitly count other low surfaces.
        core=np.abs(residual)<.03
        local_floor_metrics.append({'y_range_m':[lo,hi],'candidate_voxels':len(band),
                                   'within_3cm_fraction':float(core.mean()),
                                   'dominant_floor_median_signed_m':float(np.median(residual[core])),
                                   'dominant_floor_IQR_m':np.percentile(residual[core],[25,75]).tolist()})
    traj_yaw=np.unwrap(2*np.arctan2(poses[:,6],poses[:,3])) # Approximate planar yaw, wxyz.
    stats=dict(
        batch_log_duration_s=float(seconds[-1]),
        first_departure_03m_time_s=float(seconds[moving[0]]),
        last_away_03m_time_s=float(seconds[moving[-1]]),
        approximate_moving_loop_span_s=float(seconds[moving[-1]]-seconds[moving[0]]),
        time_note='Times are ROS log wall timestamps nearest each save, not precision sensor timestamps.',
        estimated_height_above_fitted_floor_m_percentiles=np.percentile(height,[0,2.5,25,50,75,97.5,100]).tolist(),
        estimated_height_above_floor_central95_spread_m=float(np.percentile(height,97.5)-np.percentile(height,2.5)),
        flat_wall_patches=[clean_near,clean_far],
        start_wall_patch_points=len(start_patch),end_wall_patch_points=len(end_patch),
        start_wall_patch_median_residual_m=float(np.median(start_res)),
        end_wall_patch_median_residual_m=float(np.median(end_res)),
        flat_wall_start_end_offset_m=float(np.median(end_res)-np.median(start_res)),
        local_floor_patches=local_floor_metrics)
    (OUT/'consistency_stats.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False,indent=2))

    plt.rcParams.update({'font.size':10,'axes.grid':True,'grid.alpha':.2})
    fig,axes=plt.subplots(2,2,figsize=(13,9),layout='constrained')
    axes[0,0].plot(seconds,poses[:,2]*100,label='Z in original map frame',color='#d18b33',lw=1)
    axes[0,0].plot(seconds,(height-np.median(height[:150]))*100,label='Height relative to fitted floor',color='#22648b',lw=1)
    axes[0,0].set(xlabel='Elapsed save-log time (s)',ylabel='Change in height (cm)',title='Tilt of map axes explains most height change')
    axes[0,0].legend(fontsize=8)
    axes[0,1].scatter(poses[:,0],poses[:,1],c=seconds,s=2,cmap='plasma')
    axes[0,1].set_aspect('equal');axes[0,1].set(xlabel='X (m)',ylabel='Y (m)',title='Estimated loop trajectory, time color')
    for residual,color,label in [(start_res,'#168997','Start observation'),(end_res,'#c14076','End observation')]:
        axes[1,0].hist(residual*100,bins=np.linspace(-8,8,100),density=True,histtype='step',color=color,lw=1.5,label=label)
    axes[1,0].set(xlabel='Signed offset from fitted wall (cm)',ylabel='Density',title='Flat wall patch: start and end in same map frame')
    axes[1,0].legend()
    mask=mask_box(vxyz,[[-2.5,8],[-4,19],[-1.1,-.3]])
    selected=vxyz[mask];delta=selected@normal+d
    im=axes[1,1].scatter(selected[:,0],selected[:,1],c=delta*100,s=1,vmin=-8,vmax=8,cmap='coolwarm')
    axes[1,1].set_aspect('equal');axes[1,1].set(xlabel='X (m)',ylabel='Y (m)',title='Low surfaces: distance from fitted floor')
    fig.colorbar(im,ax=axes[1,1],label='Distance (cm)',shrink=.75)
    fig.suptitle('Follow-up measurements: local consistency, no ground-truth accuracy claim',fontsize=13)
    fig.savefig(OUT/'consistency_measurements.png',dpi=180);plt.close(fig)

if __name__=='__main__':main()
