"""Download every 20K river segment intersecting the Red Deer watershed.

Uses returnIdsOnly + explicit ID chunks: no silent ArcGIS transfer-limit truncation.
"""
from project_paths import resolve_runtime_path, archive_relative
import concurrent.futures
import json
import sys
from pathlib import Path
from shapely.geometry import shape, mapping
from shapely.ops import unary_union


from rdr.storage import DATA, save_json
from API.client import get_json

BASE = 'https://geospatial.alberta.ca/titan/rest/services/environment/base_water_feature/MapServer'

def main():
    huc = json.loads((resolve_runtime_path(DATA / 'sources/alberta_geospatial/static/gis/huc4_red_deer.geojson')).read_text())
    tertiary = json.loads((resolve_runtime_path(DATA / 'sources/alberta_geospatial/static/gis/tertiary_red_deer.geojson')).read_text())
    basin = unary_union([shape(f['geometry']) for f in huc['features'] + tertiary['features']])
    save_json(resolve_runtime_path(DATA / 'processed/basin_boundary.geojson'), {'type':'FeatureCollection','features':[
        {'type':'Feature','properties':{'source':'Union of Alberta HUC4 and WSC 05C tertiary units, including internally drained areas'},'geometry':mapping(basin)}]})
    # Simplification only affects remote candidate selection; use a buffer to
    # avoid losing boundary segments. Exact original basin filters downloaded data.
    query_shape = basin.buffer(0.002).simplify(0.001, preserve_topology=True)
    polygons = list(query_shape.geoms) if query_shape.geom_type=='MultiPolygon' else [query_shape]
    # Short envelope query avoids server URL-length limits for complex polygons.
    geometry = ','.join(map(str, basin.bounds))
    for layer, label in [(107, 'streams'), (108, 'intermittent'), (72, 'waterbodies')]:
        params={'where':'1=1','geometry':geometry,'geometryType':'esriGeometryEnvelope',
                'inSR':4326,'spatialRel':'esriSpatialRelIntersects','returnIdsOnly':'true','f':'json'}
        ids_doc=get_json(f'{BASE}/{layer}/query',f'sources/alberta_geospatial/static/gis/{label}_ids.json',params,timeout=120)
        ids=sorted(ids_doc.get('objectIds') or [])
        print(label,'expected',len(ids),flush=True)
        def chunk(start):
            wanted=ids[start:start+250]
            obj=get_json(f'{BASE}/{layer}/query',f'sources/alberta_geospatial/static/gis/{label}/page_{start:06}.geojson',
                         {'objectIds':','.join(map(str,wanted)),'outFields':'*','outSR':4326,'f':'geojson'},timeout=120)
            fs=obj.get('features',[])
            received={f['properties']['OBJECTID'] for f in fs}
            if received!=set(wanted): raise ValueError(f'{label}: incomplete ID chunk {start}')
            print(label,start,len(fs),flush=True)
            return fs
        all_features=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            for fs in pool.map(chunk,range(0,len(ids),250)): all_features.extend(fs)
        actual=[f for f in all_features if shape(f['geometry']).intersects(basin)]
        save_json(resolve_runtime_path(DATA/f'processed/{label}.geojson'),{'type':'FeatureCollection','features':actual})
        save_json(resolve_runtime_path(DATA/f'reports/{label}_coverage.json'),{'requested_feature_count':len(ids),'received_feature_count':len(all_features),
                'basin_intersecting_count':len(actual),'complete_id_download':len(all_features)==len(ids),
                'note':'Full intersecting features retained; geometry not clipped. Provincial service extent is Alberta.'})

if __name__=='__main__': main()
