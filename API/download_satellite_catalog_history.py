"""Archive finite public Sentinel-2 L2A metadata; never authenticate or process pixels."""
import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlparse
import requests
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform, unary_union
from project_paths import WORKSPACE

COLLECTION = 'https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a'
SEARCH = 'https://stac.dataspace.copernicus.eu/v1/search'

def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--max-pages', type=int, default=1000)
    args = parser.parse_args()
    if not args.run_id.replace('_','').replace('-','').isalnum():
        raise ValueError('Invalid run identifier')
    end = instant(args.end)
    if not end.tzinfo or not 1 <= args.max_pages <= 1000:
        raise ValueError('UTC-aware end and bounded page count required')
    folder = WORKSPACE/'courses/AIDA-2154/data/sources/copernicus_sentinel2/raw/catalog_history'/args.run_id
    folder.mkdir(parents=True, exist_ok=False)
    manifest_path = folder/'manifest.json'
    manifest = {'run_id': args.run_id, 'started_at': datetime.now(timezone.utc).isoformat(),
                'complete': False, 'pages': [], 'pixel_processing_performed': False,
                'credentials_used': False, 'cloud_filter': None, 'time_end': args.end,
                'max_pages': args.max_pages, 'scope': 'Current selected rivers with 500 m buffer; all bounding-box catalogue responses preserved, exact corridor intersections indexed separately.'}
    session = requests.Session()
    def fetch(method, url, payload, prefix):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname != 'stac.dataspace.copernicus.eu':
            raise RuntimeError('Unexpected public catalogue pagination host')
        for attempt in range(1, 4):
            p = folder/(prefix+f'_attempt{attempt}')
            write_json(p.with_suffix('.request.json'), {'method': method, 'url': url, 'json': payload})
            try:
                response = session.request(method, url, json=payload if method == 'POST' else None,
                                           timeout=(20,180), allow_redirects=False)
            except requests.RequestException as exc:
                write_json(p.with_suffix('.error.json'), {'type':type(exc).__name__, 'at':datetime.now(timezone.utc).isoformat()})
                if attempt == 3: raise RuntimeError('Public catalogue network request failed after three attempts') from None
                time.sleep(2**attempt)
                continue
            raw = response.content
            body_path = p.with_suffix('.json')
            body_path.write_bytes(raw)
            meta = {'path':str(body_path.relative_to(folder)).replace('\\','/'),
                    'status':response.status_code, 'url':response.url,
                    'received_at':datetime.now(timezone.utc).isoformat(),
                    'sha256':hashlib.sha256(raw).hexdigest(), 'bytes':len(raw),
                    'retry_after':response.headers.get('Retry-After')}
            write_json(p.with_suffix('.meta.json'), meta)
            if response.status_code == 200:
                return response.json(), meta
            if response.status_code not in [429,500,502,503,504] or attempt == 3:
                raise RuntimeError('Public catalogue HTTP '+str(response.status_code))
            retry = response.headers.get('Retry-After','5')
            try: delay = float(retry)
            except ValueError:
                try: delay = (parsedate_to_datetime(retry)-datetime.now(timezone.utc)).total_seconds()
                except (ValueError,TypeError): delay = 5
            time.sleep(max(1,min(delay,120)))
        raise RuntimeError('Catalogue request failed')
    try:
        collection, collection_meta = fetch('GET', COLLECTION, None, 'collection')
        intervals = collection['extent']['temporal']['interval']
        starts = [instant(x[0]) for x in intervals if x[0]]
        if not starts: raise RuntimeError('Collection has no verified earliest extent')
        start = min(starts)
        if start >= end: raise ValueError('Collection start is not before request end')
        geometry_path = WORKSPACE/'courses/AIDA-2362/project/nrcan_nhn/selected_rivers.geojson'
        geometry_raw = geometry_path.read_bytes()
        rivers = unary_union([shape(f['geometry']) for f in json.loads(geometry_raw)['features']])
        forward = Transformer.from_crs(4326,32612,always_xy=True).transform
        reverse = Transformer.from_crs(32612,4326,always_xy=True).transform
        corridor = transform(reverse, transform(forward,rivers).buffer(500))
        write_json(folder/'scope.geojson', {'type':'Feature','properties':{'buffer_m':500},'geometry':mapping(corridor)})
        manifest.update(collection_metadata=collection_meta, time_start=start.isoformat(),
                        river_sha256=hashlib.sha256(geometry_raw).hexdigest(), bbox=list(corridor.bounds))
        query = {'collections':['sentinel-2-l2a'], 'bbox':list(corridor.bounds),
                 'datetime':start.isoformat()+'/'+end.isoformat(), 'limit':100,
                 'sortby':[{'field':'datetime','direction':'asc'},{'field':'id','direction':'asc'}]}
        method,url,payload = 'POST',SEARCH,query
        seen_requests = set()
        unique = {}
        duplicates = 0
        raw_count = 0
        while True:
            number = len(manifest['pages'])+1
            if number > args.max_pages: raise RuntimeError('Page cap reached; archive is incomplete')
            identity = json.dumps([method,url,payload],sort_keys=True)
            if identity in seen_requests: raise RuntimeError('Repeated pagination request; archive is incomplete')
            seen_requests.add(identity)
            obj, meta = fetch(method,url,payload,f'page_{number:04d}')
            features = obj.get('features')
            if not isinstance(features,list): raise RuntimeError('Missing catalogue feature list')
            raw_count += len(features)
            for f in features:
                if f.get('collection') != 'sentinel-2-l2a': raise RuntimeError('Unexpected catalogue collection')
                when = instant(f['properties']['datetime'])
                if not start <= when <= end: raise RuntimeError('Catalogue item outside requested time range')
                if f['id'] in unique: duplicates += 1
                unique[f['id']] = {'id':f['id'], 'datetime':f['properties']['datetime'],
                                   'intersects_corridor':bool(f.get('geometry') and shape(f['geometry']).intersects(corridor)),
                                   'page':meta['path']}
            next_links = [link for link in obj.get('links',[]) if link.get('rel')=='next']
            if len(next_links)>1: raise RuntimeError('Ambiguous next-page link')
            meta.update(rows=len(features), numberMatched=obj.get('numberMatched'), context=obj.get('context'), next_link=next_links[0] if next_links else None)
            manifest['pages'].append(meta)
            manifest.update(raw_feature_count=raw_count, unique_scene_count=len(unique), duplicate_id_count=duplicates)
            write_json(manifest_path,manifest)
            print('Catalogue page',number,'raw scenes',raw_count,'unique scenes',len(unique),flush=True)
            if not next_links: break
            link = next_links[0]
            method = link.get('method','GET').upper()
            url = link['href']
            if method not in ['GET','POST']: raise RuntimeError('Unsupported next-page method')
            if method == 'POST':
                payload = {**(payload or query), **link.get('body',{})} if link.get('merge',False) else link.get('body',payload or query)
            else: payload = None
            time.sleep(.3)
        records = sorted(unique.values(), key=lambda f:(f['datetime'],f['id']))
        write_json(folder/'scene_index.json',records)
        scoped = [f for f in records if f['intersects_corridor']]
        manifest.update(complete=True, completion_basis='Followed every returned next link to terminal page; all original bodies and fields retained.',
                        intersecting_scene_count=len(scoped),
                        first_scene=records[0]['datetime'] if records else None,
                        last_scene=records[-1]['datetime'] if records else None,
                        first_intersecting_scene=scoped[0]['datetime'] if scoped else None,
                        last_intersecting_scene=scoped[-1]['datetime'] if scoped else None,
                        finished_at=datetime.now(timezone.utc).isoformat())
        write_json(manifest_path,manifest)
        print(json.dumps({k:manifest[k] for k in ['complete','unique_scene_count','intersecting_scene_count','first_intersecting_scene','last_intersecting_scene']}),flush=True)
    except Exception as exc:
        manifest.update(complete=False, error=type(exc).__name__+': '+str(exc), stopped_at=datetime.now(timezone.utc).isoformat())
        write_json(manifest_path,manifest)
        raise

if __name__ == '__main__':
    main()
