"""Independent artifact and source checks after analysis."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import tarfile
import numpy as np
from PIL import Image
from inspect_current import BASE, OUT, ARCHIVE, read_map, colors_of, snapshot, save_json


def main():
    before=json.loads((OUT/'source_manifest_before.json').read_text(encoding='utf-8'))
    after=snapshot()
    assert before==after, 'An input file changed during analysis'
    save_json('source_manifest_after.json',after)
    relative={str(Path(row['path']).relative_to(BASE)).replace('\\','/'):row
              for row in before if Path(row['path']).is_relative_to(BASE)}
    seen=set()
    with tarfile.open(ARCHIVE,'r:gz') as tar:
        for member in tar:
            p=PurePosixPath(member.name)
            assert p.parts and p.parts[0]==BASE.name and '..' not in p.parts and not p.is_absolute()
            if member.isdir():
                continue
            assert member.isfile(), f'Unexpected archive member: {member.name}'
            rel=str(PurePosixPath(*p.parts[1:]))
            assert rel in relative and rel not in seen
            assert member.size==relative[rel]['bytes']
            h=hashlib.sha256()
            with tar.extractfile(member) as f:
                for block in iter(lambda:f.read(1024*1024),b''):
                    h.update(block)
            assert h.hexdigest()==relative[rel]['sha256'], rel
            seen.add(rel)
    expected={key for key in relative if not key.startswith('merged/')}
    assert seen==expected, (seen-expected,expected-seen)
    print('source files unchanged; all archive members match extracted files',flush=True)
    v=np.load(OUT/'voxel_data.npz')
    points,colors,occupancy,keys,keep=v['xyz'],v['rgb'],v['occupancy'],v['keys'],v['keep']
    raw_info,raw,xyz=read_map(BASE/'merged/map_raw.pcd')
    rgb=colors_of(raw)
    assert occupancy.sum()==len(raw)
    for name,selected in [('map_working_005m.pcd',np.ones(len(points),dtype=bool)),('map_denoised_005m.pcd',keep)]:
        info,data,derived_xyz=read_map(OUT/name)
        assert np.array_equal(derived_xyz,points[selected])
        assert np.array_equal(colors_of(data),colors[selected])
        assert np.isfinite(derived_xyz).all()
    # Select random, dense, and peripheral voxels, then recompute via spatial boxes.
    rng=np.random.default_rng(50011)
    choices=np.unique(np.r_[rng.choice(len(points),8,replace=False),np.argmax(occupancy),
                            np.argmin(points,axis=0),np.argmax(points,axis=0)])
    checks=[]
    for i in choices:
        key=int(keys[i]); offset=1<<20; mask=(1<<21)-1
        grid=np.array([(key>>42)-offset,((key>>21)&mask)-offset,(key&mask)-offset],dtype=np.int64)
        low=grid.astype(np.float64)*.05
        high=(grid.astype(np.float64)+1)*.05
        included=np.all((xyz>=low)&(xyz<high),axis=1)
        assert np.count_nonzero(included)==occupancy[i], int(i)
        mean=xyz[included].astype(np.float64).mean(axis=0).astype(np.float32)
        mean_rgb=np.rint(rgb[included].astype(np.float64).mean(axis=0)).astype(np.uint8)
        assert np.allclose(mean,points[i],atol=5e-6,rtol=0)
        assert np.array_equal(mean_rgb,colors[i])
        checks.append(dict(voxel_index=int(i),original_points=int(occupancy[i]),
                           mean_xyz_max_error_m=float(np.max(np.abs(mean-points[i])))))
    images=[]
    for p in sorted(OUT.glob('*.png')):
        with Image.open(p) as im:
            im.verify()
        with Image.open(p) as im:
            assert im.width>=2000 and im.height>=800
            thumb=im.convert('RGB');thumb.thumbnail((320,240))
            assert np.asarray(thumb).std()>8
            images.append(dict(name=p.name,width=im.width,height=im.height))
    result=dict(source_files_unchanged=True,verified_source_files=len(before),
        archive_member_content_matches_extracted_files=True,archive_verified_files=len(seen),
        raw_points=len(raw),working_points=len(points),denoised_points=int(keep.sum()),
        derived_payloads_match_saved_averages=True,independent_voxel_average_checks=checks,
        png_files_verified=images,note='Content verification does not certify geometric ground-truth accuracy.')
    save_json('verification.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    main()
