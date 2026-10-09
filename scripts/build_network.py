"""Derive tributary outlets and nearest SAME-river gauges from NHN topology.

Unknown flow directions and absent gauges remain explicit coverage gaps.
This is a catalog builder, not a hydraulic model.
"""
import csv
import heapq
import io
import json
import math
import sys
import zipfile
from collections import defaultdict, Counter
from pathlib import Path
import shapefile
from pyproj import Transformer, CRS
from shapely.geometry import LineString, Point, mapping
from shapely.ops import transform

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rdr.storage import DATA, save_json

ALIASES={'DEER CREEK EAST BRANCH':'EAST BRANCH DEER CREEK',
         'BERRY CREEK (EAST BRANCH)':'EAST BERRY CREEK',
         'DEAD FISH CREEK':'DEADFISH CREEK','WELSH CREEK':'WELCH CREEK'}

def canonical(name):
    name=' '.join(name.upper().split())
    return ALIASES.get(name,name)


def node(coord):
    # Sub-metre rounding stitches identical work-unit boundary coordinates.
    return (round(coord[0],6),round(coord[1],6))


def main():
    stations=json.loads((DATA/'processed/station_master.json').read_text())
    hydro={x['station_id']:x for x in json.loads((DATA/'reports/hydrometric_validation.json').read_text())}
    edges={};named=defaultdict(list);outgoing=defaultdict(list);incoming=defaultdict(list)
    known=Counter();features=[]
    project=Transformer.from_crs(4617,3400,always_xy=True).transform
    unproject=Transformer.from_crs(3400,4326,always_xy=True).transform
    for path in sorted((DATA/'sources/nrcan_nhn/static/nhn').glob('*.zip')):
        with zipfile.ZipFile(path) as z:
            for filename in z.namelist():
                if not filename.endswith('NLFLOW_1.shp'):continue
                base=filename[:-4]
                reader=shapefile.Reader(shp=io.BytesIO(z.read(filename)),dbf=io.BytesIO(z.read(base+'.dbf')),
                                       shx=io.BytesIO(z.read(base+'.shx')),encoding='utf-8',encodingErrors='replace')
                for sr in reader.iterShapeRecords():
                    p=sr.record.as_dict();eid=p['NID']
                    if eid in edges:continue
                    coords=list(sr.shape.points)
                    if len(coords)<2:continue
                    a,b=node(coords[0]),node(coords[-1]);direction=p['DIRECTION']
                    if direction==2:a,b=b,a;coords.reverse()
                    line=LineString(coords);metres=transform(project,line)
                    edge={'id':eid,'name':canonical(p.get('NAME_1') or p.get('NAME_2') or ''),
                          'a':a,'b':b,'length':metres.length,'direction':direction,
                          'line':metres if p.get('NAME_1') or p.get('NAME_2') else None}
                    edges[eid]=edge;known[direction]+=1
                    if edge['name']:
                        named[edge['name']].append(eid)
                        features.append({'type':'Feature','properties':{'nid':eid,'name':edge['name'],
                            'flow_direction_code':direction,'work_unit':p['DATASETNAM']},'geometry':mapping(line)})
                    if direction in (1,2):
                        outgoing[a].append(eid);incoming[b].append(eid)
        print('Read',path.name,'edges',len(edges),flush=True)
    save_json(DATA/'processed/nhn_named_rivers.geojson',{'type':'FeatureCollection',
       'name':'NHN named drainage network; coordinates NAD83(CSRS), EPSG:4617',
       'crs':{'type':'name','properties':{'name':'urn:ogc:def:crs:EPSG::4617'}},'features':features})

    def downstream_parent(start,name):
        queue=[(0,start)];visited=set()
        while queue:
            distance,n=heapq.heappop(queue)
            if n in visited or distance>50000:continue
            visited.add(n)
            for eid in outgoing[n]:
                e=edges[eid]
                if e['name'] and e['name']!=name:return e['name'],n,distance
                if e['name']==name:return None,None,None # Same river resumes: not an outlet.
                heapq.heappush(queue,(distance+e['length'],e['b']))
        return None,None,None

    outlets=[];unresolved=[]
    for name,eids in named.items():
        if name=='RED DEER RIVER':continue
        candidates={edges[e]['b'] for e in eids if edges[e]['direction'] in (1,2)
                    and not any(edges[n]['name']==name for n in outgoing[edges[e]['b']])}
        found={}
        for candidate in candidates:
            parent,mouth,gap=downstream_parent(candidate,name)
            if parent:found[(parent,mouth)]=(candidate,gap)
        if not found:
            unresolved.append({'watercourse':name,'reason':'No unambiguous downstream named parent in supplied NHN directions',
                'station_ids':[s['station_id'] for s in stations if canonical(s['watercourse'])==name]})
        for (parent,mouth),(candidate,gap) in found.items():
            # Walk upstream only through this named river and unnamed connectors.
            distances={mouth:0.0};queue=[(0.0,mouth)]
            while queue:
                d,n=heapq.heappop(queue)
                if d>distances[n]:continue
                for eid in incoming[n]:
                    e=edges[eid]
                    if e['name'] not in ('',name):continue
                    nd=d+e['length']
                    if nd<distances.get(e['a'],math.inf):distances[e['a']]=nd;heapq.heappush(queue,(nd,e['a']))
            station_options=[]
            for s in stations:
                if canonical(s['watercourse'])!=name:continue
                point=Point(project(s['longitude'],s['latitude']))
                ranked=sorted((edges[e]['line'].distance(point),e) for e in eids if edges[e]['line'] is not None)
                if not ranked:continue
                offset,eid=ranked[0];e=edges[eid]
                route=None
                if e['b'] in distances and e['direction'] in (1,2) and offset<=1500:
                    route=distances[e['b']]+e['length']-e['line'].project(point)
                straight=point.distance(Point(project(*mouth)))
                station_options.append({'station_id':s['station_id'],'name':s['name'],
                    'snap_distance_m':round(offset,2),'along_river_distance_m':round(route,2) if route is not None else None,
                    'straight_distance_m':round(straight,2),'data_status':hydro.get(s['station_id'],{}).get('data_status')})
            # No preference for active gauges: user asked for geographically nearest.
            # If any same-river candidate lacks a route, use geodesic/projection
            # ranking for ALL candidates and flag the result as provisional.
            route_complete=bool(station_options) and all(x['along_river_distance_m'] is not None for x in station_options)
            field='along_river_distance_m' if route_complete else 'straight_distance_m'
            station_options.sort(key=lambda x:x[field])
            chosen=station_options[0] if station_options else None
            outlets.append({'watercourse':name,'parent_river':parent,'longitude':mouth[0],'latitude':mouth[1],
                'direct_to_mainstem':parent=='RED DEER RIVER','unnamed_connector_m':round(gap,2),
                'selected_station_id':chosen['station_id'] if chosen else None,
                'selection_method':'along_river_distance' if route_complete else 'straight_distance_provisional' if chosen else 'no_same_river_gauge',
                'at_mouth': bool(chosen and chosen['straight_distance_m']<=100),
                'candidates':station_options,'source':'NHN FROM/TO geometry, DIRECTION 1/2 only; same-watercourse gauge matching',
                'coordinate_crs':'EPSG:4617'})
    # Preserve every direct unnamed inflow junction, even without gauge/name.
    main_nodes={edges[e]['a'] for e in named['RED DEER RIVER']}|{edges[e]['b'] for e in named['RED DEER RIVER']}
    unnamed=[]
    for n in main_nodes:
        for eid in incoming[n]:
            e=edges[eid]
            if not e['name']:
                unnamed.append({'network_edge_id':eid,'longitude':n[0],'latitude':n[1],
                                'status':'unnamed_inflow_no_same_river_gauge_match','coordinate_crs':'EPSG:4617'})
    save_json(DATA/'processed/tributary_outlets.json',outlets)
    save_json(DATA/'processed/unnamed_mainstem_inflows.json',unnamed)
    save_json(DATA/'reports/tributary_topology_gaps.json',unresolved)
    selected={s['station_id'] for s in stations if s['kind'] in ('MAINSTEM','CONTROL')}
    selected.update(x['selected_station_id'] for x in outlets if x['selected_station_id'])
    save_json(DATA/'processed/monitoring_station_ids.json',sorted(selected))
    summary={'deduplicated_network_edges':len(edges),'direction_codes':dict(known),'named_watercourses':len(named),
             'identified_named_outlets':len(outlets),'direct_named_mainstem_outlets':sum(x['direct_to_mainstem'] for x in outlets),
             'outlets_with_same_river_gauge':sum(bool(x['selected_station_id']) for x in outlets),
             'unresolved_watercourses':len(unresolved),'unnamed_mainstem_inflows':len(unnamed),
             'scheduled_target_station_count':len(selected),
             'limitations':['Unknown flow directions retained as gaps; no invented flow direction.',
             'Nearest selection uses all same-river WSC gauges, including discontinued gauges.',
             'Lake/reservoir gauges are not silently substituted for a tributary gauge.',
             'NHN topology is historical source data, not a contemporary riverbed survey.']}
    save_json(DATA/'reports/network_summary.json',summary)
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
