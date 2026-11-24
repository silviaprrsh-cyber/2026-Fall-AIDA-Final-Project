"""Offline, append-only snapshot: retain haze/cloud diversity, never invent labels."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform, unary_union
from project_paths import WORKSPACE


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(r, prior):
    """SCL only changes review priority; it never rejects an otherwise valid scene."""
    if not r['hash_verified'] or not r['signal_present'] or not r['valid_corridor_pixels']:
        return 'unreliable_input_review'
    if (prior.get('decision', '').startswith('hold') or
            r['corridor_pixels'] < 100 or r['river_core_pixels'] < 20 or
            r['valid_corridor_fraction'] < .95 or
            r['clear_corridor_fraction'] < .8 or r['clear_river_core_fraction'] < .9 or
            r['snow_ice_corridor_fraction'] > .01):
        return 'challenge_region_review'
    return 'clear_proxy_label_review'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, help='Replay an existing input_snapshot.json')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    base = WORKSPACE / 'courses/AIDA-2154'
    old = base / 'outputs/cv_material_screening_20261111'
    root = base / 'data/sources/copernicus_sentinel2/raw/cv_gap_fill_20261111'
    riverpath = WORKSPACE / 'courses/AIDA-2362/project/nrcan_nhn/selected_rivers.geojson'
    out = args.output or base / 'outputs/cv_material_diversity_20261111' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    if not out.is_absolute():
        out = WORKSPACE / out
    out = out.resolve()
    assert out.is_relative_to((base / 'outputs').resolve()), 'Outputs must stay in course outputs'
    out.mkdir(parents=True, exist_ok=False)
    if args.snapshot:
        snap = json.loads(args.snapshot.read_text(encoding='utf-8'))
    else:
        raw = (root / 'manifest.json').read_bytes()
        manifest = json.loads(raw)
        geo = (root / 'planned_geometries.json').read_bytes()
        assert hashlib.sha256(geo).hexdigest() == manifest['geometry_index_sha256']
        with (old / 'all_image_screening.csv').open(encoding='utf-8-sig', newline='') as f:
            historical = list(csv.DictReader(f))
        reviews = {}
        for folder, name, origin in [(old, 'visual_review.json', 'historical'), (base / 'outputs/cv_gap_fill_20261111', 'visual_review_first24.json', 'gap_fill')]:
            for r in json.loads((folder / name).read_text(encoding='utf-8'))['reviews']:
                reviews[origin + ':' + r.get('id', r.get('request_id'))] = r
        snap = {'created_utc': datetime.now(timezone.utc).isoformat(), 'manifest_sha256': hashlib.sha256(raw).hexdigest(),
                'geometry_sha256': hashlib.sha256(geo).hexdigest(), 'river_sha256': sha(riverpath),
                'historical_csv_sha256': sha(old / 'all_image_screening.csv'), 'historical': historical,
                'jobs': [j for j in manifest['jobs'] if j['status'] == 'downloaded'],
                'non_downloaded_jobs': [j for j in manifest['jobs'] if j['status'] != 'downloaded'],
                'geometries': json.loads(geo), 'prior_reviews': reviews,
                'manifest_status_counts': dict(Counter(j['status'] for j in manifest['jobs']))}
    assert sha(riverpath) == snap['river_sha256'], 'Scope changed; do not replay against different geometry'
    (out / 'input_snapshot.json').write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding='utf-8')
    # Older replay snapshots may contain needs_review jobs. Never inspect their pixels.
    skipped = snap.get('non_downloaded_jobs', []) + [j for j in snap['jobs'] if j['status'] != 'downloaded']
    with (out / 'non_downloaded_requests.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'status', 'image_file_exists', 'userdata_file_exists', 'pixel_quality', 'candidate_status'])
        writer.writeheader()
        for j in skipped:
            writer.writerow(dict(id=j['id'], status=j['status'], image_file_exists=(root/j['id']/'image.tif').is_file(), userdata_file_exists=(root/j['id']/'userdata.json').is_file(), pixel_quality='unknown_not_read', candidate_status='unknown_not_confirmed_downloaded'))
    rivers = unary_union([transform(Transformer.from_crs(4326, 32612, always_xy=True).transform, shape(f['geometry'])) for f in json.loads(riverpath.read_text())['features']])
    corridor, core = rivers.buffer(500), rivers.buffer(20)
    inputs = []
    for h in snap['historical']:
        inputs.append(('historical', h['id'], h['image'], h['image_sha256'], mapping(corridor), h['sensing_at'], h['event_group'], h['grid'], h['eligible_for_label_review']))
    for j in snap['jobs']:
        if j['status'] != 'downloaded':
            continue
        inputs.append(('gap_fill', j['id'], str((root / j['id'] / 'image.tif').relative_to(WORKSPACE)).replace('\\', '/'), j['image_sha256'], snap['geometries'][j['id']], j['scene_time'], j['observation_key'], j['grid'], str(j.get('cv_candidate', False))))
    rows, regions, corrections = [], [], []
    (out / 'region_review_masks').mkdir()
    for origin, identity, image, expected, geometry, sensing, event, grid, strict in inputs:
        p = (WORKSPACE / image).resolve()
        assert p.is_relative_to(WORKSPACE)
        digest = sha(p)
        key = origin + ':' + identity
        prior = snap['prior_reviews'].get(key, {})
        if prior:
            assert prior['image_sha256'] == digest, 'Prior visual review belongs to different pixels'
        with rasterio.open(p) as ds:
            assert ds.count == 6 and ds.crs.to_epsg() == 32612 and ds.res == (10, 10)
            a = ds.read()
            inside = geometry_mask([geometry], out_shape=ds.shape, transform=ds.transform, invert=True)
            near = geometry_mask([mapping(core.intersection(shape(geometry)))], out_shape=ds.shape, transform=ds.transform, invert=True)
            valid = inside & (a[5] == 1) & np.all(np.isfinite(a[:4]), axis=0)
            clear = valid & np.isin(a[4], [4, 5, 6])
            cloud = valid & np.isin(a[4], [3, 8, 9, 10])
            snow = valid & (a[4] == 11)
            n, k = int(inside.sum()), int(near.sum())
            r = dict(origin=origin, id=identity, image=image, image_sha256=digest, hash_verified=digest == expected,
                     sensing_at=sensing, event_group_hint=event, grid=grid, previous_strict_candidate=strict,
                     corridor_pixels=n, river_core_pixels=k, valid_corridor_pixels=int(valid.sum()),
                     valid_corridor_fraction=float(valid.sum()/max(n, 1)), clear_corridor_fraction=float(clear.sum()/max(n, 1)),
                     cloud_shadow_corridor_fraction=float(cloud.sum()/max(n, 1)), snow_ice_corridor_fraction=float(snow.sum()/max(n, 1)),
                     clear_river_core_fraction=float((clear & near).sum()/max(k, 1)),
                     signal_present=bool(np.any(a[:4, valid] > 0)),
                     prior_preview_decision=prior.get('decision', ''), prior_preview_reason=prior.get('reason_code', ''),
                     independent_label_status='not_available', split_status='unassigned_requires_cross_archive_overpass_grouping')
            r['review_group'] = classify(r, prior)
            r['retained_for_region_review'] = r['review_group'] != 'unreliable_input_review'
            r['visibility_confirmed'] = False
            # This is a review aid, NEVER a segmentation target or water class.
            mask = np.zeros(ds.shape, dtype='uint8')
            mask[inside & ~valid] = 2
            mask[valid] = 1
            mask[valid & ~np.isin(a[4], [4, 5, 6])] = 5
            mask[cloud] = 3
            mask[snow] = 4
            mp = out / 'region_review_masks' / (origin + '_' + identity + '.tif')
            profile = ds.profile.copy()
            profile.update(count=1, dtype='uint8', nodata=0, compress='deflate')
            with rasterio.open(mp, 'w', **profile) as dest:
                dest.write(mask, 1)
                dest.update_tags(purpose='REVIEW_ONLY_NOT_WATER_LABELS', codes='0=outside_scope_ignore;1=valid_unlabelled;2=invalid_ignore;3=provider_cloud_shadow_review;4=provider_snow_ice_review;5=other_SCL_review')
            r['region_review_mask'] = str(mp.relative_to(out)).replace('\\', '/')
            regions.append(dict(origin=origin, id=identity, invalid_ignore_pixels=int((mask == 2).sum()),
                                provider_cloud_shadow_review_pixels=int((mask == 3).sum()),
                                provider_snow_ice_review_pixels=int((mask == 4).sum()),
                                other_scl_review_pixels=int((mask == 5).sum()), valid_unlabelled_pixels=int((mask == 1).sum())))
            assert sum(regions[-1][v] for v in list(regions[-1])[2:]) == n
            rows.append(r)
            if prior.get('decision', '').startswith('hold'):
                corrections.append(r.copy())
    def csvwrite(name, data, fields):
        with (out / name).open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(data)
    csvwrite('all_materials.csv', rows, list(rows[0]))
    for group in ['clear_proxy_label_review', 'challenge_region_review', 'unreliable_input_review']:
        csvwrite(group + '.csv', [r for r in rows if r['review_group'] == group], list(rows[0]))
    csvwrite('region_quality_inventory.csv', regions, list(regions[0]))
    csvwrite('previous_holds_retained.csv', corrections, list(rows[0]))
    summary = dict(created_utc=snap['created_utc'], images=len(rows), sources=dict(Counter(r['origin'] for r in rows)),
                   groups=dict(Counter(r['review_group'] for r in rows)),
                   source_groups={s: dict(Counter(r['review_group'] for r in rows if r['origin'] == s)) for s in ['historical', 'gap_fill']},
                   hash_failures=sum(not r['hash_verified'] for r in rows), previous_holds_retained=len(corrections),
                   non_downloaded_requests=dict(Counter(j['status'] for j in skipped)),
                   image_exclusion_by_cloud_score=False, script_sha256=sha(Path(__file__)), independent_labels=0, training_started=False)
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    cn = f'''# 卫星 CV 素材：保留薄雾与局部云的多样性

本次快照共 {len(rows)} 张，分组计数见 summary.json。旧报告、原始影像、下载状态均未修改。本快照只包含读取清单时已经完成的影像；如果后续下载继续，可重新运行生成新快照。

non_downloaded_requests.csv 单列尚未确认完成的请求。needs_review、pending 等不读取像素或元数据，不计作下载影像，实际质量及候选资格未知，不自动重试。文件存在字段只反映本地状态，不证明服务端执行结果。

## 修正后的准则

薄雾、局部云或亮度异常本身不是整张淘汰理由。只要区域内河道边界仍能可靠辨认，就可进入独立标注候选，作为挑战样本补充晴朗样本。不能辨认的区域应人工确认后忽略，不能猜测水体边界，也不能把云或无效像素当作非水体。

- clear_proxy_label_review.csv：达到旧的严格像素指标，且未被已有预览标为需复核。名称中的 clear_proxy 只是 SCL 指标代理，不代表已证明晴朗、可用或已标注。
- challenge_region_review.csv：保留薄雾、云影、雪冰、低覆盖、其他 SCL 指标未达旧阈值或已有预览提示的素材。必须逐区域核查；该组不是“全都属于薄雾”，也不是全都可训练。雪冰需按项目非冻结水面用途单独处理。
- unreliable_input_review.csv：仅用于哈希异常、无有效像素或无反射率信号的输入问题。所有原片仍保留，不删除。
- region_quality_inventory.csv 和 region_review_masks/：像素级复核辅助。编码 0 为范围外忽略，1 为有效但未标注，2 为无效必须忽略，3 为供应商云/影待复核建议，4 为供应商雪冰待复核建议，5 为其他 SCL 待复核。3/4/5 不是已确认遮挡，也不是必须整片忽略。编码 1 也不保证可辨认。不得直接把此栅格送入训练作为水/非水标签。

## 原预览修正

previous_holds_retained.csv 保留旧预览的八个 hold 项：历史 #11/#12/#16 与新补采 #8/#9/#13 进入挑战复核；历史 #1/#15 因覆盖很小保留为区域适用性复核。复看两张接触表可见，新 #8/#9/#13 仍有河道形态，适合优先查看原分辨率；旧 #11/#12 明显发白，不能从缩略图认定所有区域可标注；旧 #16 覆盖很小。这里只修正候选处置，不创建人工标签或确认全部可训练。预览表未覆盖的影像不作视觉结论。

## 可复现与边界

运行：`.venv\\Scripts\\python.exe -B run.py -m cv_tools.retain_challenge_materials`。默认每次新建带 UTC 时间的输出子目录。精确重放使用 `--snapshot <本次 input_snapshot.json> --output <新的课程 outputs 子目录>`。输入快照记录已完成任务、几何与旧指标/预览；逐张重新检查 SHA-256、六波段、10m、EPSG:32612，重新计算像素指标。尚在下载中的文件不读取。

500m 河道走廊是研究范围；20m 线邻域只衡量覆盖，不是水体真值。SCL 原生20m重采样至10m，不能提供10m精度真值。候选仍需独立标签、分组切分、泄漏检查、误差切片和许可核实，符合课程 README 与 data-model-card 的证据要求。两个归档的事件键格式不同，训练前必须统一真实过境时间/轨道及空间邻近分组，不能直接按 CSV 的 event_group_hint 切分。本次没有训练、调整模型、设定最终数据切分或声称精度。
'''
    (out / 'README_CN.md').write_text(cn, encoding='utf-8')
    print(json.dumps({'output': str(out), **summary}, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
