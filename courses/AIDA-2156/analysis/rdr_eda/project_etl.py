"""Build a scoped, offline relational dataset without changing acquired originals."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import hashlib
import json
import sqlite3

from project_paths import WORKSPACE, ROOT
from API.observations import parse_time
from API.collector import station_calculation_interval
from .rainfall import finite, normalize_swob, aggregate_precipitation

BASE = WORKSPACE / 'courses/AIDA-2156/data'
GIS = WORKSPACE / 'courses/AIDA-2362/project'
DEST = BASE / 'processed/project_etl'
ASSUMPTION = 'reported_level_as_variable_depth_below_gauge_zero_excluded'
TABLE_NOTES = {
    'model_segments': ('Independent submodel chain up to 05CC002; lake elevation is a feature only for P03 to P04.', '到 05CC002 为止的独立子模型链；湖面高程仅用于 P03 到 P04。'),
    'model_segment_legs': ('Along-river input-leg distances for arrival calculations, including tributary routes.', '到达时间计算所用的输入路径沿河距离，包含支流河段。'),
    'segment_training': ('Integrated table: one trajectory and segment per row; label_* columns are endpoint supervision, never input features.', '整合主表：每行为一条递推轨迹的一个河段；label_* 是终点监督标签，禁止作为输入特征。'),
    'segment_arrivals': ('Per-leg departure, velocity, distance and estimated arrival; missing speed never falls back to simultaneous matching.', '各输入路径的出发时间、流速、距离和预计到达时间；缺流速时不退回同时刻匹配。'),
    'stations': ('Selected river gauges and separate lake reference; joins on station_id.', '所选河流站及独立湖泊参考站，通过 station_id 关联。'),
    'weather_stations': ('Selected weather locations; nearby observations, not catchment averages.', '所选气象站位置；为邻近站点观测，不是流域平均值。'),
    'river_inputs': ('Selected river topology and confluences from the final GIS map; no flow summation.', '最终 GIS 地图的河网与汇入口；不在此累加流量。'),
    'water_observations': ('Instantaneous archived river observations with original levels and experimental variable depths.', '归档河流瞬时观测，保留原水位及实验可变水深。'),
    'water_daily_history': ('Historical daily river values for later EDA/ML; dates have no invented time of day.', '供后续 EDA/ML 使用的历史日值；日期不补造具体时刻。'),
    'lake_reference': ('Sylvan Lake 05CC003 elevation observations, separated from river depth inputs.', 'Sylvan Lake 05CC003 湖面高程观测，与河流水深输入分离。'),
    'weather_observations': ('Selected temperature, humidity, wind and rainfall context; retain units and quality codes.', '选取温度、湿度、风及降雨辅助变量，保留单位和质量码。'),
    'precipitation_intervals': ('SWOB precipitation intervals with validity, duration and revision provenance.', 'SWOB 降水时段，保留有效性、时长和修订来源。'),
    'station_windows': ('Water observations joined to their own trailing precipitation windows; missing totals remain null.', '各水文观测与自身向前降水窗口关联，覆盖不完整时累计量为空。'),
    'sections': ('Only section lines selected in the final GIS project, with profile and datum caveats.', '仅保留最终 GIS 工程所选断面，保留剖面与基准限制。'),
    'section_profile_points': ('Normalized cross-section offsets and elevations; join to sections by section_id.', '规范化断面横向距离和高程，通过 section_id 关联断面表。'),
    'prediction_targets': ('P01-P11 positions and section links; no predictions or observed target values are fabricated.', 'P01—P11 位置及断面关联，不生成虚构预测值或观测值。'),
    'target_input_links': ('Candidate boundary, incremental tributary and downstream validation inputs per target; no time alignment or flow addition.', '各预测点的候选上游边界、区间支流和下游验证输入；不在此进行传播时间对齐或流量相加。'),
    'section_station_candidates': ('In-scope same-river association candidates; not verified hydraulic transfers.', '范围内同河断面与站点的候选关联，并非已验证水力传递。'),
    'satellite_assets': ('Existing raster paths and geometric coverage; no image duplication or CV inference.', '现有影像路径及几何覆盖，不复制影像、不运行 CV 推理。'),
}


def companion(path, english, chinese):
    path.with_name(path.name + '.md').write_text(f'# `{path.name}`\n\n{english}\n', encoding='utf-8')
    path.with_name(path.name + 'CN.md').write_text(f'# `{path.name}`\n\n{chinese}\n', encoding='utf-8')


def utc(value):
    return parse_time(value).astimezone(timezone.utc).isoformat() if value else None


class Builder:
    """Track exact input bytes and normalization issues for each build."""

    def __init__(self):
        self.inputs = {}
        self.issues = []

    def read(self, path):
        path = Path(path)
        data = path.read_bytes()
        self.inputs[path.relative_to(WORKSPACE).as_posix()] = hashlib.sha256(data).hexdigest()
        return data.decode('utf-8-sig')

    def obj(self, path):
        return json.loads(self.read(path))

    def meta(self, path):
        sidecar = path.with_suffix(path.suffix + '.meta.json')
        return self.obj(sidecar) if sidecar.exists() else {}

    def issue(self, path, reason):
        self.issues.append({'path': Path(path).relative_to(WORKSPACE).as_posix(), 'reason': reason})


def store_latest(records, key, row):
    """Keep the newest archived revision, including missing/invalid replacements."""
    rank = (row.get('provider_processed_at') or '', row.get('received_at') or '',
            row.get('source_path') or '')
    old = records.get(key)
    if old is None or rank > old[0]:
        records[key] = (rank, row)


def extract_observations(builder, station_ids, weather_ids):
    water, weather, precipitation = {}, {}, {}
    for source in ['eccc_hydrometric_datamart', 'eccc_hydrometric_geomet', 'eccc_weather_geomet']:
        folder = BASE / 'sources' / source / 'raw'
        for path in sorted(folder.rglob('*')):
            if path.suffix not in {'.csv', '.json'} or path.name.endswith('.meta.json'):
                continue
            if path.suffix == '.csv' and path.stem not in station_ids:
                continue
            meta = builder.meta(path)
            if meta.get('status', 200) != 200:
                builder.issue(path, 'source_http_error')
                continue
            raw = path.relative_to(WORKSPACE).as_posix()
            received = utc(meta.get('received_at_utc'))
            if path.suffix == '.csv':
                if source != 'eccc_hydrometric_datamart':
                    continue
                for values in csv.reader(builder.read(path).splitlines()):
                    if not values or values[0].strip() not in station_ids:
                        continue
                    if len(values) < 10:
                        builder.issue(path, 'short_water_row')
                        continue
                    sid = values[0].strip()
                    try:
                        stamp = utc(values[1])
                    except (ValueError, TypeError):
                        builder.issue(path, 'invalid_water_timestamp')
                        continue
                    row = {'station_id': sid, 'observed_at': stamp, 'observation_date': None,
                           'resolution': 'instantaneous', 'level_m': finite(values[2]),
                           'discharge_m3_s': finite(values[6]), 'level_quality': values[5],
                           'discharge_quality': values[9], 'level_symbol': values[4],
                           'discharge_symbol': values[8], 'record_id': f'{sid}:{stamp}',
                           'source': source, 'source_path': raw, 'received_at': received,
                           'provider_processed_at': None, 'transmitted_at': None}
                    store_latest(water, (sid, stamp, 'instantaneous'), row)
                continue
            try:
                obj = builder.obj(path)
            except (ValueError, UnicodeError):
                builder.issue(path, 'invalid_json')
                continue
            for feature in obj.get('features', []) if isinstance(obj, dict) else []:
                p = feature.get('properties', {})
                sid = p.get('STATION_NUMBER')
                if source == 'eccc_hydrometric_geomet' and sid in station_ids:
                    if 'LEVEL' not in p and 'DISCHARGE' not in p:
                        continue
                    date, stamp = p.get('DATE'), p.get('DATETIME')
                    if not date and not stamp:
                        continue
                    resolution = 'instantaneous' if stamp else 'daily_mean'
                    try:
                        stamp = utc(stamp)
                        date = None if stamp else datetime.strptime(date, '%Y-%m-%d').date().isoformat()
                    except (ValueError, TypeError):
                        builder.issue(path, 'invalid_water_timestamp')
                        continue
                    row = {'station_id': sid, 'observed_at': stamp, 'observation_date': date,
                           'resolution': resolution, 'level_m': finite(p.get('LEVEL')),
                           'discharge_m3_s': finite(p.get('DISCHARGE')),
                           'level_quality': None, 'discharge_quality': None,
                           'level_symbol': p.get('LEVEL_SYMBOL_EN'),
                           'discharge_symbol': p.get('DISCHARGE_SYMBOL_EN'),
                           'record_id': p.get('IDENTIFIER') or feature.get('id'),
                           'source': source, 'source_path': raw, 'received_at': received,
                           'provider_processed_at': None, 'transmitted_at': None}
                    store_latest(water, (sid, stamp or date, resolution), row)
                wid = str(p.get('msc_id-value', ''))
                if source != 'eccc_weather_geomet' or wid not in weather_ids or not p.get('date_tm-value'):
                    continue
                try:
                    stamp = utc(p.get('obs_date_tm') or p['date_tm-value'])
                    processed = utc(p.get('processed_date_tm'))
                    intervals = normalize_swob(p, raw, received, feature.get('id'))
                except (ValueError, TypeError):
                    builder.issue(path, 'invalid_weather_timestamp')
                    continue
                common = {'station_id': wid, 'observed_at': stamp,
                          'record_id': feature.get('id') or p.get('id'),
                          'provider_processed_at': processed, 'received_at': received,
                          'transmitted_at': None, 'source_path': raw}
                for field in ['air_temp', 'rel_hum', 'avg_wnd_spd_10m_pst1hr',
                              'avg_wnd_spd_10m_pst10mts', 'rnfl_amt_pst1hr']:
                    if field not in p:
                        continue
                    row = {**common, 'field': field, 'value': finite(p[field]),
                           'unit': p.get(field + '-uom'), 'quality': p.get(field + '-qa'),
                           'data_flag': p.get(field + '-data_flag-value')}
                    store_latest(weather, (wid, stamp, field), row)
                for r in intervals:
                    row = {**r, 'provider_processed_at': processed, 'received_at': received,
                           'source_path': raw}
                    # Existing aggregation calls this field published_at; it is provider processing time.
                    row['published_at'] = processed
                    store_latest(precipitation, (wid, r['field'], r['start'], r['end']), row)
        print(f'Read {source}', flush=True)
    rows = [v[1] for _, v in sorted(water.items())]
    for row in rows:
        q = row['discharge_m3_s']
        row['discharge_status'] = 'missing' if q is None else 'negative_rejected' if q < 0 else 'source_value'
        if q is not None and q < 0:
            row['discharge_m3_s'] = None
        row['depth_assumption'] = ASSUMPTION if row['station_id'] != '05CC003' else None
        h = row['level_m']
        row['experimental_variable_depth_m'] = h if row['station_id'] != '05CC003' and h is not None and h >= 0 else None
        row['level_status'] = 'missing' if h is None else 'negative_not_used_as_depth' if h < 0 else 'source_value'
    return rows, [v[1] for _, v in sorted(weather.items())], [v[1] for _, v in sorted(precipitation.items())]


def build_windows(water, rain, stations):
    """Use every instantaneous water observation as its own trailing-window endpoint."""
    import bisect
    lookup = {s['station_id']: s for s in stations}
    weather = {}
    for wid in {s.get('weather_station_id') for s in stations} - {None}:
        rr = sorted((r for r in rain if r['station_id'] == wid), key=lambda r: r['end'])
        weather[wid] = ([parse_time(r['end']) for r in rr], rr)
    output = []
    for r in water:
        if r['resolution'] != 'instantaneous' or r['station_id'] not in lookup:
            continue
        s = lookup[r['station_id']]
        interval = s.get('calculation_interval_seconds')
        if not interval or not s.get('weather_station_id'):
            continue
        end = parse_time(r['observed_at']); start = end - timedelta(seconds=interval)
        ends, rr = weather.get(s['weather_station_id'], ([], []))
        candidates = rr[bisect.bisect_right(ends, start):bisect.bisect_right(ends, end)]
        result = aggregate_precipitation(candidates, start.isoformat(), end.isoformat())
        output.append({'station_id': r['station_id'], 'weather_station_id': s['weather_station_id'],
                       **result, 'level_m': r['level_m'],
                       'experimental_variable_depth_m': r['experimental_variable_depth_m'],
                       'depth_assumption': r['depth_assumption'], 'discharge_m3_s': r['discharge_m3_s'],
                       'water_record_id': r['record_id'], 'water_source_path': r['source_path'],
                       'water_received_at': r['received_at'], 'water_level_quality': r['level_quality'],
                       'water_discharge_quality': r['discharge_quality'],
                       'water_level_symbol': r['level_symbol'], 'water_discharge_symbol': r['discharge_symbol'],
                       'temporal_basis': 'retrospective_trailing_window_overlapping_windows_not_additive'})
    return output


def spatial_tables(b, scope, config):
    from pyproj import Transformer
    from shapely.geometry import shape, Point
    from shapely.ops import transform
    project = Transformer.from_crs(4326, 3400, always_xy=True).transform
    rivers = b.obj(GIS / 'nrcan_nhn/selected_rivers.geojson')['features']
    main = transform(project, shape(next(f['geometry'] for f in rivers if f['properties']['river'] == 'RED DEER RIVER')))
    positions, network = {}, []
    for f in rivers:
        p = f['properties']; mouth = p.get('actual_mouth_lon_lat')
        chain = main.project(transform(project, Point(mouth))) if mouth else None
        if p.get('station_id'):
            positions[p['station_id']] = chain
        network.append({'river': p['river'], 'role': p['role'], 'station_id': p.get('station_id'),
                        'length_m': p.get('length_m'), 'mainstem_confluence_chainage_m': chain,
                        'mouth_longitude': mouth[0] if mouth else None, 'mouth_latitude': mouth[1] if mouth else None,
                        'routing_verified': False, 'source_direction_conflict_ids': p.get('source_direction_conflict_ids', []),
                        'input_status': 'unmeasured_inflow_excluded_from_experiment' if p['river'] == 'SYLVAN CREEK' else 'observed_input_or_mainstem',
                        'source_path': (GIS / 'nrcan_nhn/selected_rivers.geojson').relative_to(WORKSPACE).as_posix()})
    cfg = {s['station_id']: s for s in config['stations']}
    station_features = b.obj(GIS / 'eccc_hydrometric_geomet/stations.geojson')['features']
    station_features += b.obj(GIS / 'eccc_hydrometric_geomet/historical_tributary_stations.geojson')['features']
    stations = []
    for f in station_features:
        p = f['properties']; sid = p['station_id']
        if sid not in set(scope['station_ids']) | {'05CC003'}:
            continue
        c = cfg.get(sid, {}); lon, lat = f['geometry']['coordinates'][:2]
        role = 'lake_reference' if sid == '05CC003' else 'upstream_boundary' if sid == '05CB007' else 'internal_validation' if sid == '05CC002' else 'tributary_input'
        stations.append({'station_id': sid, 'name': p['name'], 'river': p['river'], 'role': role,
                         'longitude': lon, 'latitude': lat, 'coordinate_crs': 'EPSG:4326',
                         'vertical_datum': p.get('vertical_datum'),
                         'mainstem_chainage_or_confluence_m': positions.get(sid) if role == 'tributary_input' else main.project(transform(project, Point(lon, lat))) if role != 'lake_reference' else None,
                         'weather_station_id': c.get('weather_link', {}).get('weather_id') if role != 'lake_reference' else None,
                         'weather_distance_km': c.get('weather_link', {}).get('distance_km') if role != 'lake_reference' else None,
                         'calculation_interval_seconds': station_calculation_interval(c) if c else None,
                         'hydraulic_transfer_verified': False, 'metadata_source': p.get('metadata_source'),
                         'boundary_note': 'Tunnel discharge is not verified total dam release' if sid == '05CB007' else None})
    stations.sort(key=lambda s: (s['mainstem_chainage_or_confluence_m'] is None, s['mainstem_chainage_or_confluence_m'] or 0))
    weather_stations = []
    for f in b.obj(GIS / 'eccc_weather_geomet/stations.geojson')['features']:
        p = f['properties']; xy = f['geometry']['coordinates']
        if p['station_id'] in scope['weather_ids']:
            weather_stations.append({'station_id': p['station_id'], 'name': p['name'], 'longitude': xy[0],
                                     'latitude': xy[1], 'coordinate_crs': 'EPSG:4326',
                                     'role': 'nearby_point_not_catchment_average', 'source_path': p.get('provenance')})
    profiles = b.obj(BASE / 'processed/etl/profiles.json')
    sections, points = [], []
    for path in sorted((GIS / 'alberta_flood_surveys').rglob('cross_section_lines.geojson')):
        for f in b.obj(path)['features']:
            p = f['properties']; sid = p['section_id']
            fields = ['section_id', 'source_section_id', 'study', 'river', 'longitude', 'latitude',
                      'vertical_datum', 'profile_status', 'assignment_status', 'line_status',
                      'min_bed_elevation_m', 'bank_a_candidate_elevation_m', 'bank_b_candidate_elevation_m',
                      'survey_years', 'survey_water_elevation_median_m', 'selected_river_chainage_m',
                      'maximum_point_line_distance_m', 'max_profile_gap_m', 'source_database', 'source_layer', 'source_fid']
            sections.append({k: p.get(k) for k in fields} | {'gauge_zero_verified': False, 'profile_points': len(profiles.get(sid, []))})
            for index, (offset, elevation) in enumerate(profiles.get(sid, [])):
                points.append({'section_id': sid, 'point_index': index, 'offset_m': offset,
                               'elevation_m': elevation, 'vertical_datum': p.get('vertical_datum')})
    sections.sort(key=lambda r: (r['river'], r['selected_river_chainage_m'] or 0, r['section_id']))
    targets = []
    for f in b.obj(GIS / 'derived_prediction_targets/prediction_points.geojson')['features']:
        p = f['properties']; xy = f['geometry']['coordinates']
        targets.append({'target_id': p['target_id'], 'name': p['name'], 'longitude': xy[0], 'latitude': xy[1],
                        'chainage_from_dickson_m': p['chainage_from_dickson_m'],
                        'section_id': p.get('on_section_id'), 'nearest_section_id': p.get('nearest_section_id'),
                        'nearest_section_along_river_offset_m': p.get('nearest_section_along_river_offset_m'),
                        'selection_method': p.get('selection_method'), 'selection_evidence': p.get('selection_evidence'),
                        'status': 'not_predicted', 'hydraulic_transfer_verified': False})
    targets.sort(key=lambda r: r['chainage_from_dickson_m'])
    section_ids = {s['section_id'] for s in sections}
    links = []
    for r in b.obj(BASE / 'processed/etl/section_station_links.json'):
        if r['section_id'] not in section_ids:
            continue
        for candidate in r.get('candidates', []):
            if candidate['station_id'] in scope['station_ids']:
                links.append({'section_id': r['section_id'], **candidate, 'transfer_verified': False,
                              'link_method': r.get('link_method'), 'role': 'candidate_not_water_level_transfer'})
    return stations, weather_stations, network, sections, points, targets, links, main


def target_inputs(stations, targets):
    """Separate serial constraints from disjoint tributary candidates by chainage."""
    controls = sorted((s for s in stations if s['role'] in {'upstream_boundary', 'internal_validation'}),
                      key=lambda s: s['mainstem_chainage_or_confluence_m'])
    rows = []
    for t in targets:
        at = t['chainage_from_dickson_m']
        upstream = [s for s in controls if s['mainstem_chainage_or_confluence_m'] <= at]
        if not upstream:
            raise ValueError(f"No upstream boundary for {t['target_id']}")
        boundary = upstream[-1]
        selected = [(boundary, 'upstream_boundary')]
        selected += [(s, 'incremental_tributary') for s in stations if s['role'] == 'tributary_input'
                     and s['mainstem_chainage_or_confluence_m'] is not None
                     and boundary['mainstem_chainage_or_confluence_m'] < s['mainstem_chainage_or_confluence_m'] <= at]
        downstream = [s for s in controls if s['mainstem_chainage_or_confluence_m'] > at]
        if downstream:
            selected.append((downstream[0], 'downstream_validation_only'))
        for s, role in selected:
            rows.append({'target_id': t['target_id'], 'station_id': s['station_id'], 'role': role,
                         'mainstem_distance_from_station_or_mouth_m': abs(at - s['mainstem_chainage_or_confluence_m']),
                         'travel_time_seconds': None, 'alignment_status': 'not_time_aligned',
                         'hydraulic_transfer_verified': False})
    return rows


def image_index(b, main):
    scope = b.obj(ROOT / 'config/active_scope.json')
    selected = WORKSPACE / 'courses/AIDA-2154/data/processed/satellite_history' / scope['scope_id'] / 'image_index.json'
    if selected.exists():
        index = b.obj(selected)
        river_path = GIS / 'nrcan_nhn/selected_rivers.geojson'
        if index['river_sha256'] != hashlib.sha256(river_path.read_bytes()).hexdigest():
            raise ValueError('Satellite scope index is stale: run cv_tools.select_scope_history')
        return [{'raster_path': row['image'], 'image_sha256': row['image_sha256'],
                 'scope_id': index['scope_id'], 'source_archive': row['source_archive'],
                 'time_matches': row['time_matches'], 'quality': row['quality'],
                 'matched_clear_candidate': row['matched_clear_candidate'],
                 'scope_mask_required': True, 'metadata_path': selected.relative_to(WORKSPACE).as_posix()}
                for row in index['images']]
    from shapely.geometry import shape, box
    from shapely.ops import transform
    from pyproj import Transformer
    import rasterio
    project = Transformer.from_crs(4326, 3400, always_xy=True).transform
    rows = []
    folder = WORKSPACE / 'courses/AIDA-2154/data/sources/copernicus_sentinel2/raw'
    for scene in sorted(folder.rglob('selected_scene.json')):
        d = b.obj(scene); p = d['properties']
        footprint = transform(project, shape(d['geometry']))
        if not footprint.intersects(main):
            continue
        for raster in sorted(scene.parent.glob('*.tif')):
            b.inputs[raster.relative_to(WORKSPACE).as_posix()] = hashlib.sha256(raster.read_bytes()).hexdigest()
            with rasterio.open(raster) as ds:
                to_project = Transformer.from_crs(ds.crs, 3400, always_xy=True).transform
                extent = transform(to_project, box(*ds.bounds))
                intersects = extent.intersects(main)
                rows.append({'scene_id': d['id'], 'acquired_at': p.get('datetime'),
                             'tile_cloud_percent': p.get('eo:cloud_cover'),
                             'scene_covers_mainstem': footprint.covers(main),
                             'raster_path': raster.relative_to(WORKSPACE).as_posix(),
                             'raster_crs': str(ds.crs), 'band_count': ds.count,
                             'pixel_width': abs(ds.res[0]), 'pixel_height': abs(ds.res[1]),
                             'raster_intersects_mainstem': intersects, 'raster_covers_mainstem': extent.covers(main),
                             'coverage_basis': 'bounding_geometry_only_not_clear_water_pixels',
                             'metadata_path': scene.relative_to(WORKSPACE).as_posix()})
    return rows


def export_tables(folder, tables):
    """Write readable CSVs and typed relational SQLite tables from the same rows."""
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / 'project.build.sqlite3'
    if temporary.exists():
        temporary.unlink()
    db = sqlite3.connect(temporary)
    try:
        for name, rows in tables.items():
            fields = list(dict.fromkeys(k for r in rows for k in r))
            if not fields:
                raise ValueError(f'Unexpected empty required table: {name}')
            def cell(v):
                return json.dumps(v, ensure_ascii=False, allow_nan=False) if isinstance(v, (dict, list)) else v
            with (folder / (name + '.csv')).open('w', encoding='utf-8-sig', newline='') as h:
                w = csv.DictWriter(h, fieldnames=fields); w.writeheader()
                w.writerows({k: cell(r.get(k)) for k in fields} for r in rows)
            en, cn = TABLE_NOTES[name]
            field_text = ', '.join(f'`{field}`' for field in fields)
            companion(folder / (name + '.csv'), en + '\n\nGenerated by `python -B run.py etl` from local archives, configuration and selected GIS layers. Input hashes are recorded in `../../reports/project_etl_validation.json`. Empty CSV cells represent missing values, not zero. This data file calls nothing and creates no other files.\n\nColumns: ' + field_text,
                      cn + '\n\n由 `python -B run.py etl` 读取本地归档、配置及所选 GIS 图层生成。输入哈希见 `../../reports/project_etl_validation.json`。CSV 空单元格表示缺失，不是零。该数据文件不调用程序，也不生成其他文件。\n\n字段：' + field_text)
            declarations = []
            for field in fields:
                vals = [r[field] for r in rows if r.get(field) is not None]
                kind = 'REAL' if vals and all(isinstance(v, (int, float)) for v in vals) else 'TEXT'
                if not vals and field.endswith(('_m', '_m_s', '_m3_s', '_seconds', '_mm', '_mm_h')):
                    kind = 'REAL'
                declarations.append(f'"{field}" {kind}')
            db.execute(f'CREATE TABLE "{name}" ({", ".join(declarations)})')
            db.executemany(f'INSERT INTO "{name}" VALUES ({",".join("?" for _ in fields)})',
                           [[cell(r.get(k)) for k in fields] for r in rows])
            key = 'station_id' if 'station_id' in fields else 'section_id' if 'section_id' in fields else None
            if key:
                db.execute(f'CREATE INDEX "idx_{name}_{key}" ON "{name}" ("{key}")')
        db.commit()
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed')
    finally:
        db.close()
    temporary.replace(folder / 'project.sqlite3')
    companion(folder / 'project.sqlite3', 'Relational copy of the CSV tables in this folder, generated by `rdr_eda.project_etl`. Query with SQLite using station_id, section_id and observation timestamps. This file calls nothing and generates nothing.',
              '本目录 CSV 表的关系数据库副本，由 `rdr_eda.project_etl` 生成。使用 SQLite 按 station_id、section_id 和观测时间关联查询。本文件不调用程序或生成其他文件。')


def run_project_pipeline(*, segment_state_path=None):
    b = Builder()
    scope = b.obj(ROOT / 'config/active_scope.json')
    config = b.obj(ROOT / 'config/stations.json')
    stations, weather_stations, network, sections, points, targets, links, main = spatial_tables(b, scope, config)
    active = set(scope['station_ids']); allowed = active | {'05CC003'}
    print('Reading archived water and weather responses...', flush=True)
    water, weather, rain = extract_observations(b, allowed, set(scope['weather_ids']))
    empty_rows = Counter(r['station_id'] for r in water if r['level_m'] is None and r['discharge_m3_s'] is None)
    water = [r for r in water if r['level_m'] is not None or r['discharge_m3_s'] is not None]
    current = [r for r in water if r['station_id'] in active and r['resolution'] == 'instantaneous']
    daily = [r for r in water if r['station_id'] in active and r['resolution'] == 'daily_mean']
    lake = [dict(r, experimental_variable_depth_m=None, depth_assumption=None) for r in water if r['station_id'] == '05CC003']
    print('Building independent observation-time windows...', flush=True)
    windows = build_windows(current, rain, stations)
    # Export provider processing with its actual meaning, not publication/transmission time.
    precipitation = [{k: v for k, v in r.items() if k not in {'published_at', 'available_at', 'raw_path'}} for r in rain]
    tables = {'stations': stations, 'weather_stations': weather_stations, 'river_inputs': network,
              'water_observations': current, 'water_daily_history': daily, 'lake_reference': lake,
              'weather_observations': weather, 'precipitation_intervals': precipitation,
              'station_windows': windows, 'sections': sections, 'section_profile_points': points,
              'prediction_targets': targets, 'section_station_candidates': links,
              'target_input_links': target_inputs(stations, targets),
              'satellite_assets': image_index(b, main)}
    from .segments import build_segment_tables, postgres_export, feature_contract
    print('Building independent submodel tables and arrival-aligned labels...', flush=True)
    segment_tables, segment_summary = build_segment_tables(b, tables, segment_state_path)
    tables.update(segment_tables)
    section_ids = {r['section_id'] for r in sections}
    assert {s['station_id'] for s in stations} == allowed
    assert {s['station_id'] for s in weather_stations} == set(scope['weather_ids'])
    assert all(not t['section_id'] or t['section_id'] in section_ids for t in targets)
    assert all(not t['nearest_section_id'] or t['nearest_section_id'] in section_ids for t in targets)
    assert all(p['section_id'] in section_ids for p in points)
    assert all(r['observed_at'] is None for r in daily)
    assert len({(r['station_id'], r['observed_at']) for r in current}) == len(current)
    assert len({(r['station_id'], r['observation_date']) for r in daily}) == len(daily)
    assert all(w['precipitation_total_mm'] is None for w in windows if w['status'] != 'complete')
    report = {'scope_id': scope['scope_id'], 'built_at_utc': datetime.now(timezone.utc).isoformat(),
              'counts': {k: len(v) for k, v in tables.items()}, 'depth_assumption': ASSUMPTION,
              'window_status': dict(Counter(w['status'] for w in windows)),
              'all_missing_water_rows_excluded_after_revision_selection': dict(empty_rows),
              'issues': b.issues, 'inputs_sha256': b.inputs,
              'segment_etl': segment_summary,
              'limitations': ['Retrospective archives, not point-in-time ML replay; split by time before training.',
                              'Daily values retain date precision and are not instantaneous observations.',
                              'Gauge zero is not aligned to profiles; no area, velocity or risk prediction is produced.',
                              'Sylvan Lake elevation is an ML feature in P03 to P04; no outlet discharge is inferred or added.',
                              'Dam tunnel discharge is not proven total dam release.',
                              'Station windows overlap; never sum them as independent precipitation.',
                              'Spatial links remain candidates and do not establish travel times.']}
    export_tables(DEST, tables)
    schema = postgres_export(DEST, segment_tables)
    contract_path = DEST / 'segment_feature_contract.json'
    contract_path.write_text(json.dumps(feature_contract(segment_tables), indent=2) + '\n', encoding='utf-8')
    companion(contract_path,
              'Explicit predictor allowlist per submodel and endpoint supervision fields. Prevents label_* and own output_* columns from being fed back as inputs. Generated by rdr_eda.segments.feature_contract; this file runs no code.',
              '各子模型可用输入字段白名单及终点监督字段，防止把 label_* 或本段 output_* 当作输入。由 rdr_eda.segments.feature_contract 生成，本文件不执行代码。')
    report['postgresql'] = {'schema': schema, 'status': 'sql_export_only_not_imported',
                            'file': 'segments_postgresql.sql'}
    companion(DEST / 'segments_postgresql.sql',
              'Transactional PostgreSQL export of the four segment tables. Creates a content-addressed schema; fails safely if that schema exists, without replacing existing data. Run psql with ON_ERROR_STOP=1 and an explicitly configured connection. No credentials included. Generated by rdr_eda.segments.postgres_export.',
              '四张分段表的 PostgreSQL 事务导入文件。按内容哈希创建独立 schema；同名 schema 已存在则安全失败，不覆盖既有数据。使用明确配置的连接并设置 psql ON_ERROR_STOP=1。文件不含凭据，由 rdr_eda.segments.postgres_export 生成。')
    report_path = BASE / 'reports/project_etl_validation.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    companion(report_path, 'Build counts, normalization issues, limitations and SHA-256 hashes of the local inputs read by `rdr_eda.project_etl`. No online availability or model validation claim. This report calls nothing and generates nothing.',
              '记录 `rdr_eda.project_etl` 的构建数量、规范化问题、限制及所读本地输入的 SHA-256 哈希。不表示在线可用性检查或模型验证。本报告不调用程序或生成其他文件。')
    print(json.dumps({k: v for k, v in report.items() if k not in {'inputs_sha256', 'issues'}}, indent=2), flush=True)
    return report
