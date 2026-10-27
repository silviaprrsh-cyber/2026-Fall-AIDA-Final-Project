"""Survey normalization and evidence-labelled links to the existing named river graph."""
from project_paths import resolve_runtime_path, archive_relative
from collections import defaultdict, Counter
import heapq
import json
import math
from pathlib import Path
import re
from statistics import median

import numpy as np
from pyogrio.raw import read
from pyproj import Transformer
from shapely import from_wkb, force_2d
from shapely.geometry import Point, shape, mapping
from shapely.ops import linemerge, transform
from shapely.strtree import STRtree

from rdr.storage import DATA, save_json
from rdr_eda.rainfall import finite

CRS='EPSG:3780'
TO_WGS=Transformer.from_crs(3780,4326,always_xy=True).transform
FROM_WGS=Transformer.from_crs(4326,3780,always_xy=True).transform
FROM_NHN=Transformer.from_crs(4617,3780,always_xy=True).transform
ALIASES={'RED DEER':'RED DEER RIVER','ROSEBUD':'ROSEBUD RIVER','KNEEHILLS CR':'KNEEHILLS CREEK',
         'MICHICHI CR':'MICHICHI CREEK','WILLOW CR':'WILLOW CREEK'}


def canonical(value):
    name=' '.join(str(value or '').upper().split())
    return ALIASES.get(name,name)


def clean(value):
    if value is None:return None
    if isinstance(value,(float,np.floating)) and not math.isfinite(value):return None
    if isinstance(value,np.generic):return value.item() if value.dtype.kind not in 'Mm' else str(value)
    return value


def features(path,layer):
    meta,fids,geoms,arrays=read(path,layer=layer,return_fids=True)
    for i,fid in enumerate(fids):
        yield int(fid),force_2d(from_wkb(geoms[i])),{str(k):clean(v[i]) for k,v in zip(meta['fields'],arrays)}


def normalize_surveys():
    sections=[];points=[];profiles={}
    studies=[('red_deer','Red Deer','Survey_Cross_Sections','Survey_Points',True),
             ('upper_red_deer','Upper Red Deer','Survey_Cross_Sections','Survey_Points',True),
             ('drumheller','Drumheller','XS_Planned','CrossSection',False),
             ('county_markerville','Red Deer County and Markerville','FLD_ProposedCrossSectionLines','FLD_CrossSectionTopoSurvey',False)]
    for study,directory,line_layer,point_layer,has_ids in studies:
        db=next((resolve_runtime_path(DATA/'sources/alberta_flood_surveys/manual'/directory)).rglob('*.gdb'))
        local=[];lookup={}
        for fid,geom,p in features(db,line_layer):
            if geom.geom_type=='MultiLineString':geom=linemerge(geom)
            sid=str(p.get('CS_ID') or p.get('NAME') or p.get('NodeName') or fid)
            river=canonical(p.get('RiverCode') or p.get('RIVER') or p.get('RiverName'))
            key=f'{study}:{river}:{sid}'
            if sid in lookup:raise ValueError('Duplicate source section ID within study')
            lon,lat=TO_WGS(geom.centroid.x,geom.centroid.y)
            s={'section_id':key,'source_section_id':sid,'study':study,'river':river,
               'line_status':'surveyed' if has_ids else 'planned',
               'survey_date':str(p.get('Date') or p.get('Year') or ''),
               'horizontal_crs':CRS,'vertical_datum':'CGVD28','vertical_datum_basis':'accompanying survey report',
               'longitude':lon,'latitude':lat,'source_database':str(archive_relative(db, DATA)),
               'source_layer':line_layer,'source_fid':fid,'line_length_m':geom.length,
               'geometry':mapping(geom),'profile_verified':False,'bank_elevations_verified':False}
            local.append(s);lookup[sid]=len(local)-1
        lines=[shape(s['geometry']) for s in local];tree=STRtree(lines);assigned=defaultdict(list)
        for fid,geom,p in features(db,point_layer):
            row={'point_key':f'{study}:{point_layer}:{fid}','study':study,'source_fid':fid,
                 'source_point_id':str(p.get('ID') or p.get('NAME') or fid),
                 'source_database':str(archive_relative(db, DATA)),'source_layer':point_layer,
                 'x_m':geom.x,'y_m':geom.y,'elevation_m':finite(p.get('Elevation',p.get('ELEV'))),
                 'horizontal_crs':CRS,'vertical_datum':'CGVD28',
                 'code':str(p.get('Code') or p.get('CODE') or p.get('PtType') or ''),
                 'survey_date':str(p.get('Date') or p.get('SURV_DATE') or ''),
                 'source_class':p.get('Class','Cross Section'),'section_id':None,
                 'assignment_status':'not_cross_section','offset_m':None,'line_distance_m':None,
                 'survey_water_elevation_m':finite(p.get('Water_Level_Elevation')),
                 'source_attributes':p}
            eligible=not has_ids or p.get('Class')=='Cross Section'
            index=None
            if eligible and row['elevation_m'] is not None:
                if has_ids:
                    index=lookup.get(str(p.get('CS_ID')))
                    row['assignment_status']='source_id_match' if index is not None else 'unmatched_source_id'
                else:
                    nearby=tree.query(geom.buffer(20))
                    ranked=sorted((lines[int(i)].distance(geom),int(i)) for i in nearby)
                    if ranked and (len(ranked)==1 or ranked[1][0]-ranked[0][0]>5):
                        index=ranked[0][1];row['assignment_status']='spatial_candidate_requires_review'
                    else:row['assignment_status']='ambiguous_or_outside_20m'
                if index is not None:
                    line=lines[index]
                    row.update(section_id=local[index]['section_id'],line_distance_m=line.distance(geom))
                    if line.geom_type=='LineString':row['offset_m']=line.project(geom)
                    if row['offset_m'] is not None:assigned[index].append(row)
            points.append(row)
        for index,s in enumerate(local):
            rows=assigned[index];groups=defaultdict(list)
            for r in rows:groups[round(r['offset_m'],2)].append(r)
            profile=[(x,median(r['elevation_m'] for r in group)) for x,group in sorted(groups.items())]
            s.update(point_count=len(rows),profile_point_count=len(profile),
                maximum_point_line_distance_m=max((r['line_distance_m'] for r in rows),default=None),
                coincident_offset_groups=sum(len(g)>1 for g in groups.values()),
                max_elevation_spread_at_same_offset_m=max((max(r['elevation_m'] for r in g)-min(r['elevation_m'] for r in g) for g in groups.values()),default=None),
                assignment_status='source_id_match' if has_ids else 'spatial_candidates_only')
            if len(profile)>=2:
                s.update(profile_span_m=profile[-1][0]-profile[0][0],
                    max_profile_gap_m=max(b[0]-a[0] for a,b in zip(profile,profile[1:])),
                    min_bed_elevation_m=min(z for x,z in profile))
                lowest=min(rows,key=lambda r:r['elevation_m'])
                anchor=Point(lowest['x_m'],lowest['y_m'])
                s['longitude'],s['latitude']=TO_WGS(anchor.x,anchor.y)
                s['location_basis']='lowest_assigned_survey_point'
                # TOB is an explicit source code; do not infer bank crests from endpoints.
                bank_points=[r for r in rows if r['code'].strip().upper()=='TOB']
                seed=lowest['offset_m']
                for side,subset in [('a',[r for r in bank_points if r['offset_m']<seed]),
                                    ('b',[r for r in bank_points if r['offset_m']>seed])]:
                    s[f'bank_{side}_candidate_elevation_m']=min((r['elevation_m'] for r in subset),default=None)
                s['bank_candidate_basis']='TOB code on either side of minimum bed; side A/B is not verified left/right'
                wse=[r['survey_water_elevation_m'] for r in rows if r['survey_water_elevation_m'] is not None and r['survey_water_elevation_m']>0]
                s['survey_water_elevation_median_m']=median(wse) if wse else None
                s['survey_water_elevation_range_m']=max(wse)-min(wse) if wse else None
                s['profile_status']='source_linked_review_required' if has_ids else 'spatial_reconstruction_review_required'
                profiles[s['section_id']]=profile
            else:s['profile_status']='insufficient_points'
            s['survey_years']=sorted({r['survey_date'][:4] for r in rows if r['survey_date'] and r['survey_date']!='NaT'})
        sections.extend(local)
        print(study,'sections',len(local),'assigned points',sum(len(v) for v in assigned.values()),flush=True)
    return sections,points,profiles


class RiverGraph:
    """Named NHN edges only; coordinates already follow flow in the saved source file."""
    def __init__(self,features):
        self.lines=[];self.ids=[];self.directions=[]
        self.adj=defaultdict(list);self.forward=defaultdict(list);self.backward=defaultdict(list)
        for f in features:
            line=transform(FROM_NHN,shape(f['geometry']))
            if line.geom_type!='LineString':continue
            index=len(self.lines);self.lines.append(line);self.ids.append(f['properties']['nid'])
            known=f['properties'].get('flow_direction_code') in (1,2);self.directions.append(known)
            a,b=self.key(line.coords[0]),self.key(line.coords[-1]);length=line.length
            self.adj[a].append((b,length));self.adj[b].append((a,length))
            if known:self.forward[a].append((b,length));self.backward[b].append((a,length))
        self.tree=STRtree(self.lines)

    @staticmethod
    def key(coordinate):return tuple(round(v,1) for v in coordinate[:2])

    def snap(self,point):
        i=int(self.tree.nearest(point));line=self.lines[i]
        return {'index':i,'offset':line.project(point),'snap_m':line.distance(point)}

    def distances(self,snap,mode='undirected'):
        line=self.lines[snap['index']];a,b=self.key(line.coords[0]),self.key(line.coords[-1]);at=snap['offset']
        if mode!='undirected' and not self.directions[snap['index']]:return {}
        seeds={a:at,b:line.length-at} if mode=='undirected' else {b:line.length-at} if mode=='forward' else {a:at}
        graph=self.adj if mode=='undirected' else self.forward if mode=='forward' else self.backward
        distances=dict(seeds);queue=[(d,k) for k,d in seeds.items()];heapq.heapify(queue)
        while queue:
            distance,node=heapq.heappop(queue)
            if distance>distances[node]:continue
            for other,length in graph[node]:
                candidate=distance+length
                if candidate<distances.get(other,math.inf):distances[other]=candidate;heapq.heappush(queue,(candidate,other))
        return distances

    def route(self,source,target,distances,mode='undirected'):
        if source['snap_m']>500 or target['snap_m']>500:return None
        line=self.lines[target['index']];a,b=self.key(line.coords[0]),self.key(line.coords[-1]);at=target['offset']
        if mode!='undirected' and not self.directions[target['index']]:return None
        result=min(distances.get(a,math.inf)+at,distances.get(b,math.inf)+line.length-at) if mode=='undirected' else (
            distances.get(a,math.inf)+at if mode=='forward' else distances.get(b,math.inf)+line.length-at)
        if source['index']==target['index']:
            delta=at-source['offset']
            if mode=='undirected' or mode=='forward' and delta>=0 or mode=='backward' and delta<=0:result=min(result,abs(delta))
        return result if math.isfinite(result) else None


def build_links(sections,stations):
    grouped=defaultdict(list)
    for f in json.loads((resolve_runtime_path(DATA/'processed/nhn_named_rivers.geojson')).read_text())['features']:
        grouped[canonical(f['properties']['name'])].append(f)
    graphs={};gauge_routes={};links=[]
    for river in sorted({s['river'] for s in sections}):
        if river not in grouped:continue
        graph=RiverGraph(grouped[river]);graphs[river]=graph
        for station in stations:
            if canonical(station['watercourse'])!=river:continue
            point=Point(FROM_WGS(station['longitude'],station['latitude']));snap=graph.snap(point)
            gauge_routes[station['station_id']]=(snap,{mode:graph.distances(snap,mode) for mode in ['undirected','forward','backward']})
    for section in sections:
        river=section['river'];graph=graphs.get(river)
        location=Point(FROM_WGS(section['longitude'],section['latitude']))
        snap=graph.snap(location) if graph else None
        section['reach_id']=graph.ids[snap['index']] if snap and snap['snap_m']<=500 else None
        section['river_snap_m']=snap['snap_m'] if snap else None
        candidates=[]
        for station in stations:
            if canonical(station['watercourse'])!=river:continue
            point=Point(FROM_WGS(station['longitude'],station['latitude']))
            route=None;upstream=None;downstream=None
            if graph and station['station_id'] in gauge_routes:
                source,distances=gauge_routes[station['station_id']]
                route=graph.route(source,snap,distances['undirected'])
                upstream=graph.route(source,snap,distances['forward'],'forward')
                downstream=graph.route(source,snap,distances['backward'],'backward')
            candidates.append({'station_id':station['station_id'],'straight_distance_m':point.distance(location),
                'along_river_distance_m':route,'station_relation':'upstream' if upstream is not None and downstream is None else
                    'downstream' if downstream is not None and upstream is None else 'ambiguous_or_unknown',
                'upstream_path_m':upstream,'downstream_path_m':downstream})
        candidates.sort(key=lambda c:(c['along_river_distance_m'] is None,c['along_river_distance_m'] or c['straight_distance_m']))
        chosen=candidates[0] if candidates else None
        links.append({'section_id':section['section_id'],'river':river,'reach_id':section['reach_id'],
            'station_id':chosen['station_id'] if chosen else None,
            'link_method':'same_river_network_candidate' if chosen and chosen['along_river_distance_m'] is not None else
                'same_river_straight_distance_provisional' if chosen else 'no_same_river_station',
            'transfer_verified':False,'candidates':candidates,
            'note':'Spatial association does not establish a water-level or discharge transfer function.'})
    confluences=[]
    for index,mouth in enumerate(json.loads((resolve_runtime_path(DATA/'processed/tributary_outlets.json')).read_text())):
        point=Point(FROM_WGS(mouth['longitude'],mouth['latitude']))
        entry={**mouth,'confluence_id':f'confluence_{index:03d}','nearest_sections':{}}
        for role,river in [('tributary',canonical(mouth['watercourse'])),('parent',canonical(mouth['parent_river']))]:
            choices=[(point.distance(Point(FROM_WGS(s['longitude'],s['latitude']))),s['section_id']) for s in sections if s['river']==river]
            if choices:
                distance,sid=min(choices);entry['nearest_sections'][role]={'section_id':sid,'straight_distance_m':distance,
                    'within_1km':distance<=1000,'status':'spatial_candidate_not_verified_hydraulic_connection'}
        confluences.append(entry)
    coverage=[]
    for station in stations:
        point=Point(FROM_WGS(station['longitude'],station['latitude']))
        choices=[(point.distance(Point(FROM_WGS(s['longitude'],s['latitude']))),s['section_id']) for s in sections if s['river']==canonical(station['watercourse'])]
        nearest=min(choices) if choices else None
        coverage.append({'station_id':station['station_id'],'river':station['watercourse'],
            'same_river_section_count':len(choices),'nearest_section_id':nearest[1] if nearest else None,
            'nearest_section_straight_distance_m':nearest[0] if nearest else None,
            'section_within_1km':bool(nearest and nearest[0]<=1000),'hydraulic_transfer_verified':False})
    return links,confluences,coverage
