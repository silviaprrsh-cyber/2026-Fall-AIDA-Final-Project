"""Expose downloaded satellite TIFFs and audit their image-time water matches."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import tarfile

import numpy as np
import rasterio

from project_paths import WORKSPACE
from rdr_eda.project_etl import companion


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',args.run_id): raise ValueError('Invalid run identifier')
    base=WORKSPACE/'courses/AIDA-2154/data'
    report=base/'reports/satellite_history'/args.run_id
    manifest=json.loads((report/'manifest.json').read_text())
    raw=base/'sources/copernicus_sentinel2/raw/history'/args.run_id
    output=base/'processed/satellite_history'/args.run_id
    output.mkdir(parents=True,exist_ok=True)
    records=[]
    for job in manifest['jobs']:
        if job['status']!='downloaded': continue
        original=raw/job['id']/job['archive_name']
        with original.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=job['sha256']: raise ValueError('Source checksum mismatch')
        target=output/(job['id']+'.tif')
        with tarfile.open(original) as archive:
            data=archive.extractfile('image.tif').read()
            digest=hashlib.sha256(data).hexdigest()
            if target.exists():
                with target.open('rb') as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=digest: raise ValueError('Extracted TIFF changed')
            else:
                target.write_bytes(data)
                companion(target,'Lossless extraction of image.tif from the linked Copernicus Process API TAR. Bands: red, green, blue, NIR (reflectance x 10000), SCL, dataMask. EPSG:32612, 10 m. Use quality masks and source sensing times before CV analysis.',
                          '从对应 Copernicus Process API TAR 无损提取的 image.tif。波段为红、绿、蓝、近红外（反射率乘 10000）、SCL、dataMask。EPSG:32612，10 m。CV 分析前须使用质量掩膜及源拍摄时间。')
        with rasterio.open(target) as raster:
            assert raster.count==6 and raster.res==(10,10) and raster.crs.to_epsg()==32612
            values=raster.read()
            valid=values[5]==1
            signal_present=bool(valid.any() and np.any(values[:4,valid]>0))
            if not np.isin(values[4],[0,1,2,3,4,5,6,7,8,9,10,11]).all(): raise ValueError('Unexpected SCL classes')
        match=json.loads((raw/job['id']/'sensing_and_water_matches.json').read_text())
        if any(tile.get('sentinel2ProductId',tile.get('productId','')).removesuffix('.SAFE') not in job['scene_ids'] for tile in match['source_metadata']['tiles']):
            raise ValueError('Source product does not belong to the indexed acquisition')
        records.append({'image':str(target.relative_to(WORKSPACE)),'source_archive':str(original.relative_to(WORKSPACE)),
                        'image_sha256':digest,'quality':job['quality'],'time_matches':match['matches'],
                        'image_signal_present':signal_present,
                        'clear_corridor_at_least_80_percent':job['quality']['clear_corridor_fraction']>=.8,
                        'matched_clear_candidate':signal_present and job['quality']['clear_corridor_fraction']>=.8 and bool(match['matches']) and all(m['common_origin']['within_150_seconds'] for m in match['matches'])})
    summary={'run_id':args.run_id,'catalog_scene_count':manifest['catalog_scenes'],
             'expected_grid_requests':len(manifest['jobs']),'statuses':dict(Counter(j['status'] for j in manifest['jobs'])),
             'download_complete':all(j['status'] in ['downloaded','no_data'] for j in manifest['jobs']),
             'extracted_images':len(records),'clear_corridor_at_least_80_percent':sum(r['clear_corridor_at_least_80_percent'] for r in records),
             'images_with_all_source_times_matching_common_origins':sum(all(m['common_origin']['within_150_seconds'] for m in r['time_matches']) for r in records),
             'matched_clear_candidates':sum(r['matched_clear_candidate'] for r in records),
             'images_without_reflectance_signal':sum(not r['image_signal_present'] for r in records),
             'candidate_rule':'Nonzero image signal, at least 80% clear corridor pixels (SCL 4/5/6 with dataMask 1), and every source tile time within 150 seconds of a screened common hydrometric origin. Candidate status is not a manual quality approval.',
             'river_sha256':manifest['river_sha256'],'time_start':manifest['time_start'],'time_end':manifest['time_end'],
             'note':'Cloud threshold applies to source tiles. Local quality fractions and actual acquisition times govern usability. Multiple grids from one overpass are not independent observation events.',
             'images':records}
    path=output/'image_index.json'
    path.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    companion(path,'Extracted TIFF inventory, raw archive provenance, quality checks and actual image-time matches. Generated by cv_tools.index_satellite_history. No model training is performed.',
              'cv_tools.index_satellite_history 生成的 TIFF 清单，包含原始归档来源、质量检查及实际拍摄时间匹配。不进行模型训练。')
    english=(f'# Historical Sentinel-2 river images\n\n'
             f'Run `{args.run_id}` covers {manifest["time_start"]} to {manifest["time_end"]}. '
             f'Download complete: {summary["download_complete"]}. Extracted TIFFs: {len(records)}. '
             f'Clear, time-matched candidates: {summary["matched_clear_candidates"]}.\n\n'
             'Scope is the selected Dickson outlet-to-Joffre river network with a 500 m buffer. '
             'Open `.tif` files in QGIS using bands 1/2/3 for red/green/blue. EPSG:32612, 10 m pixels. '
             'Bands 1–4 are B04/B03/B02/B08 reflectance multiplied by 10000. Bands 5–6 are SCL and dataMask. '
             'SCL is resampled from 20 m. Outside-corridor pixels are invalid, not dry land.\n\n'
             'See [image_index.json](image_index.json) for source TAR paths, checksums, local quality fractions, '
             'actual sensing timestamps, nearest station observations, and both ML partitions. '
             'Candidates require at least 80% clear corridor pixels and all source times within 150 seconds of a screened common origin. '
             'These are automated candidates pending visual review. Original responses remain under the course data/sources directory. '
             'Multiple grids from the same overpass are one acquisition event, not independent training samples.\n')
    chinese=(f'# Sentinel-2 历史河道影像\n\n'
             f'批次 `{args.run_id}`，时段为 {manifest["time_start"]} 至 {manifest["time_end"]}。'
             f'下载完成状态：{summary["download_complete"]}。已提取 TIFF：{len(records)} 份。'
             f'清晰且时间匹配的候选：{summary["matched_clear_candidates"]} 份。\n\n'
             '范围为选定的 Dickson 出口至 Joffre 河网及两侧 500 m 缓冲区。'
             '在 QGIS 中打开 `.tif`，用 1/2/3 波段分别显示红/绿/蓝。EPSG:32612，10 m 像元。'
             '1–4 波段为 B04/B03/B02/B08 反射率乘以 10000，5–6 波段为 SCL 和 dataMask。'
             'SCL 由 20 m 重采样。河道范围以外的像元无效，不代表干地。\n\n'
             '见 [image_index.json](image_index.json)，其中保存源 TAR 路径、校验值、局部质量比例、'
             '实际拍摄时间、最近站点观测及两种 ML 划分。候选要求河道清晰像元至少 80%，'
             '且所有源拍摄时间均与筛选后的共同观测时刻相差不超过 150 秒。'
             '这只是待人工查看的自动候选。原始响应保留在课程 data/sources 中。'
             '同次过境的多个网格属于一次拍摄事件，不是独立训练样本。\n')
    (output/'README.md').write_text(english,encoding='utf-8')
    (output/'READMECN.md').write_text(chinese,encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='images'},indent=2))


if __name__=='__main__':
    main()
