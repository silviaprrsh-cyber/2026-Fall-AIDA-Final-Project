"""Cross-check NHN name transitions against provincial river geometry.

An unnamed reach on the mainstem must not shift a tributary mouth downstream.
Distances use EPSG:3400 metres. All geometric mouths remain mapped estimates.
"""
from project_paths import resolve_runtime_path, archive_relative
import heapq
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform, unary_union, nearest_points

from rdr.storage import DATA, save_json
from gis_tools.build_network import canonical


def select_gauge(choices):
    """Use straight distance only as a marked fallback, never name alone."""
    if not choices:
        return None, 'no_same_river_gauge'
    routed=[c for c in choices if c['along_river_distance_m'] is not None]
    if routed:
        best=min(routed,key=lambda c:c['along_river_distance_m'])
        # Straight distance is a lower bound for a missing network route.
        if all(c['along_river_distance_m'] is not None or
               c['straight_distance_m'] > best['along_river_distance_m'] for c in choices):
            return best,'along_same_river_network'
    best=min(choices,key=lambda c:c['straight_distance_m'])
    if best['mapped_river_offset_m'] > 500:
        return None,'same_name_location_unverified'
    return best,'straight_distance_provisional'


def main():
    forward=Transformer.from_crs(4326,3400,always_xy=True).transform
    nhn_forward=Transformer.from_crs(4617,3400,always_xy=True).transform
    inverse=Transformer.from_crs(3400,4326,always_xy=True).transform
    grouped=defaultdict(list);nhn=defaultdict(list)
    for name in ['streams','waterbodies','nhn_named_rivers']:
        fs=json.loads((resolve_runtime_path(DATA/f'processed/{name}.geojson')).read_text())['features']
        for f in fs:
            n=canonical(f['properties'].get('NAME') or f['properties'].get('name') or '')
            if not n:continue
            g=transform(nhn_forward if name=='nhn_named_rivers' else forward,shape(f['geometry']))
            grouped[n].append(g)
            if name=='nhn_named_rivers':nhn[n].append(g)
    unions={n:unary_union(gs) for n,gs in grouped.items()}
    main_geom=unions['RED DEER RIVER'];mouths=[]
    for n in nhn:
        if n=='RED DEER RIVER':continue
        a,b=nearest_points(unions[n],main_geom)
        gap=a.distance(b)
        if gap<=100:
            mouths.append({'watercourse':n,'parent_river':'RED DEER RIVER','mouth':b,'geometry_gap_m':gap,
                           'source':'NHN named river and Alberta mapped river geometry contact (100 m tolerance)'})
    original=resolve_runtime_path(DATA/'processed/nhn_topology_candidates.json')
    topology=json.loads((original if original.exists() else resolve_runtime_path(DATA/'processed/tributary_outlets.json')).read_text())
    if not original.exists():save_json(original,topology)
    direct_names={m['watercourse'] for m in mouths};seen={(m['watercourse'],m['parent_river']) for m in mouths}
    for t in topology:
        n,p=t['watercourse'],t['parent_river']
        if n in direct_names or (n,p) in seen or n not in unions or p not in unions:continue
        a,b=nearest_points(unions[n],unions[p]);gap=a.distance(b)
        if gap<=100:
            seen.add((n,p));mouths.append({'watercourse':n,'parent_river':p,'mouth':b,'geometry_gap_m':gap,
                 'source':'NHN directed parent candidate corroborated by mapped river contact; parent hierarchy provisional'})
    stations=json.loads((resolve_runtime_path(DATA/'processed/station_master.json')).read_text())
    hydro={s['station_id']:s for s in json.loads((resolve_runtime_path(DATA/'reports/hydrometric_validation.json')).read_text())}
    rows=[]
    for m in mouths:
        n=m['watercourse'];mouth=m.pop('mouth');lon,lat=inverse(mouth.x,mouth.y)
        lines=nhn[n];graph=defaultdict(list)
        def key(c):return (round(c[0],1),round(c[1],1))
        for line in lines:
            if line.geom_type!='LineString':continue
            a,b=key(line.coords[0]),key(line.coords[-1]);graph[a].append((b,line.length));graph[b].append((a,line.length))
        target=min(lines,key=lambda l:l.distance(mouth));pos=target.project(mouth);mouth_offset=target.distance(mouth)
        target_a,target_b=key(target.coords[0]),key(target.coords[-1])
        distances={target_a:pos,target_b:target.length-pos};q=[(d,k) for k,d in distances.items()];heapq.heapify(q)
        while q:
            d,k=heapq.heappop(q)
            if d>distances[k]:continue
            for v,length in graph[k]:
                nd=d+length
                if nd<distances.get(v,math.inf):distances[v]=nd;heapq.heappush(q,(nd,v))
        choices=[]
        for s in stations:
            if canonical(s['watercourse'])!=n:continue
            point=Point(forward(s['longitude'],s['latitude']))
            line=min(lines,key=lambda l:l.distance(point));offset=line.distance(point);at=line.project(point)
            a,b=key(line.coords[0]),key(line.coords[-1])
            route=min(distances.get(a,math.inf)+at,distances.get(b,math.inf)+line.length-at)
            if line.equals(target):route=min(route,abs(at-pos))
            if not math.isfinite(route) or offset>500 or mouth_offset>500:route=None
            choices.append({'station_id':s['station_id'],'station_name':s['name'],
                            'straight_distance_m':round(point.distance(mouth),2),'along_river_distance_m':round(route,2) if route is not None else None,
                            'station_snap_m':round(offset,2),'mouth_snap_m':round(mouth_offset,2),
                            'mapped_river_offset_m':round(unions[n].distance(point),2),
                            'data_status':hydro[s['station_id']].get('data_status')})
        chosen,method=select_gauge(choices)
        choices.sort(key=lambda c:c['straight_distance_m'])
        rows.append({**m,'geometry_gap_m':round(m['geometry_gap_m'],2),'longitude':lon,'latitude':lat,'coordinate_crs':'EPSG:4326',
                     'direct_to_mainstem':m['parent_river']=='RED DEER RIVER',
                     'selected_station_id':chosen['station_id'] if chosen else None,
                     'selection_method':method,'candidates':choices,
                     'at_mouth':bool(chosen and chosen['straight_distance_m']<=100),
                     'mouth_accuracy':'mapped_geometry_estimate_not_surveyed_confluence'})
    rows.sort(key=lambda r:(not r['direct_to_mainstem'],r['watercourse']))
    save_json(resolve_runtime_path(DATA/'processed/tributary_outlets.json'),rows)
    represented={r['watercourse'] for r in rows}
    gaps=[{'watercourse':n,'reason':'No corroborated mouth/parent within geometric tolerance',
           'station_ids':[s['station_id'] for s in stations if canonical(s['watercourse'])==n]} for n in nhn if n not in represented and n!='RED DEER RIVER']
    gaps.extend({'watercourse':r['watercourse'],'reason':'Same-name gauge is over 500 m from all mapped same-name river geometry; not automatically selected',
                 'station_ids':[c['station_id'] for c in r['candidates']]} for r in rows if r['selection_method']=='same_name_location_unverified')
    # Also retain river names present in gauge metadata but absent from named GIS.
    for s in stations:
        n=canonical(s['watercourse'])
        if s['kind']=='TRIBUTARY_NETWORK' and n not in nhn:
            gaps.append({'watercourse':n,'station_ids':[s['station_id']],'reason':'Gauge name not matched to a named NHN watercourse; no automatic substitution'})
    save_json(resolve_runtime_path(DATA/'reports/tributary_geometry_gaps.json'),gaps)
    selected={s['station_id'] for s in stations if s['kind'] in ['MAINSTEM','CONTROL']}
    selected.update(r['selected_station_id'] for r in rows if r['selected_station_id'])
    save_json(resolve_runtime_path(DATA/'processed/monitoring_station_ids.json'),sorted(selected))
    save_json(resolve_runtime_path(DATA/'reports/confluence_summary.json'),{'named_mouths':len(rows),'direct_mainstem_named_mouths':sum(r['direct_to_mainstem'] for r in rows),
       'with_same_river_gauge':sum(bool(r['selected_station_id']) for r in rows),'selected_station_count':len(selected),
       'gap_records':len(gaps),'selection_requires_review':sum(r['selection_method']=='straight_distance_provisional' for r in rows),
       'completeness':'Mapped named network inventory, not a claim that every physical/unnamed tributary is gauged.'})
    print('Refined mouths',len(rows),'selected stations',len(selected),'gaps',len(gaps),flush=True)

if __name__=='__main__':main()
