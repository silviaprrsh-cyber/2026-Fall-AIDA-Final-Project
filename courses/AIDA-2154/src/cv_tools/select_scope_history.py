"""Select archived imagery and recalculate pixel quality for the active river scope."""
import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from pyproj import Transformer
from shapely.geometry import shape, mapping, box
from shapely.ops import transform, unary_union

from project_paths import WORKSPACE
from rdr_eda.project_etl import companion


def main():
    base = WORKSPACE / 'courses/AIDA-2154/data/processed/satellite_history'
    source = base / '20261103_history/image_index.json'
    rivers = WORKSPACE / 'courses/AIDA-2362/project/nrcan_nhn/selected_rivers.geojson'
    scope = json.loads((WORKSPACE / 'shared-resources/config/active_scope.json').read_text())
    index = json.loads(source.read_text())
    project = Transformer.from_crs(4326, 32612, always_xy=True).transform
    corridor = unary_union([transform(project, shape(f['geometry']))
                           for f in json.loads(rivers.read_text())['features']]).buffer(500)
    records = []
    for original in index['images']:
        path = (WORKSPACE / original['image']).resolve()
        if not path.is_relative_to(WORKSPACE):
            raise ValueError('Image path must stay in the workspace')
        with rasterio.open(path) as ds:
            if ds.crs.to_epsg() != 32612:
                raise ValueError('Unexpected archived raster CRS')
            if not corridor.intersects(box(*ds.bounds)):
                continue
            inside = geometry_mask([mapping(corridor)], out_shape=(ds.height, ds.width),
                                   transform=ds.transform, invert=True)
            count = int(inside.sum())
            if not count:
                continue
            values = ds.read()
            valid = inside & (values[5] == 1)
            clear = valid & np.isin(values[4], [4, 5, 6])
            signal = bool(np.any(values[:4, valid] > 0))
            fraction = float(clear.sum() / count)
            time_match = bool(original['time_matches']) and all(
                m['common_origin']['within_150_seconds'] for m in original['time_matches'])
            records.append({**original, 'scope_id': scope['scope_id'],
                            'historical_quality': original['quality'],
                            'quality': {'corridor_pixels': count, 'valid_pixels': int(valid.sum()),
                                        'clear_pixels': int(clear.sum()), 'clear_corridor_fraction': fraction},
                            'image_signal_present': signal,
                            'clear_corridor_at_least_80_percent': fraction >= .8,
                            'matched_clear_candidate': signal and fraction >= .8 and time_match,
                            'scope_mask_required': True})
    output = base / scope['scope_id']
    output.mkdir(parents=True, exist_ok=True)
    result = {'scope_id': scope['scope_id'], 'source_index': str(source.relative_to(WORKSPACE)),
              'source_index_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'river_sha256': hashlib.sha256(rivers.read_bytes()).hexdigest(),
              'buffer_m': 500, 'source_image_count': len(index['images']),
              'selected_images': len(records),
              'matched_clear_candidates': sum(r['matched_clear_candidate'] for r in records),
              'note': 'Original rasters preserved. Apply scope_corridor.geojson before CV; quality denominator includes invalid corridor pixels. No CV training.',
              'images': records}
    for name, data in [('image_index.json', result), ('scope_corridor.geojson', {
            'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {
                'scope_id': scope['scope_id'], 'buffer_m': 500}, 'geometry': mapping(transform(
                    Transformer.from_crs(32612, 4326, always_xy=True).transform, corridor))}]} )]:
        path = output / name
        path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        companion(path, 'Active-scope satellite selection or mask from cv_tools.select_scope_history. Original imagery is unchanged.',
                  '\u5f53\u524d\u8303\u56f4\u7684\u536b\u661f\u5f71\u50cf\u7b5b\u9009\u6216\u63a9\u819c\uff0c\u539f\u59cb\u5f71\u50cf\u4fdd\u7559\u4e0d\u53d8\u3002')
    print(json.dumps({k: v for k, v in result.items() if k != 'images'}, indent=2))


if __name__ == '__main__':
    main()
