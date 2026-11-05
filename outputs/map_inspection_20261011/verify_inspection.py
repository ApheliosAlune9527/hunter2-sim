from pathlib import Path
import hashlib
import json
import numpy as np
from inspect_map import BASE,OUT,read_points
from pcd_export import pcd_info


def update_payload(digest,path,offset):
    with path.open('rb') as f:
        f.seek(offset)
        for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)


def main():
    meta=json.loads((BASE/'validation.json').read_text(encoding='utf-8'))
    chunk_hash=hashlib.sha256()
    for item in meta['files']:
        path=BASE/'pcd'/Path(item['path'].replace('\\','/')).name
        info=pcd_info(path)
        assert info['points']==item['points']
        update_payload(chunk_hash,path,info['offset'])
    raw_info=pcd_info(BASE/'merged/map_raw.pcd')
    merged_hash=hashlib.sha256()
    update_payload(merged_hash,BASE/'merged/map_raw.pcd',raw_info['offset'])
    assert merged_hash.digest()==chunk_hash.digest(), 'Raw merged payload differs from source chunks'
    checks=[]
    expected={'map_working_005m.pcd':314984,'map_denoised_005m.pcd':314712}
    arrays={}
    for name,count in expected.items():
        info,array,xyz,rgb=read_points(OUT/name)
        assert info['points']==count
        assert np.isfinite(xyz).all()
        arrays[name]=array
        checks.append({'name':name,'points':count,'bytes':(OUT/name).stat().st_size,
                       'nonfinite_coordinates':0,'sha256':hashlib.sha256((OUT/name).read_bytes()).hexdigest()})
    source=arrays['map_working_005m.pcd'].view('V16')
    result=arrays['map_denoised_005m.pcd'].view('V16')
    assert np.isin(result,source).all(), 'Denoised records are not a subset of averaged map'
    report={'merged_payload_matches_all_5274_chunks':True,'raw_payload_sha256':merged_hash.hexdigest(),
            'derived_files':checks,'denoised_records_are_exact_subset':True}
    (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
