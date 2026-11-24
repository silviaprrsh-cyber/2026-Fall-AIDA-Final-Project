"""Retrospective, indirect width validation of frozen CNN test predictions."""
from bisect import bisect_right
from collections import Counter
import csv
from datetime import datetime
import json
from pathlib import Path
import math
import numpy as np
import rasterio
from shapely.geometry import Point, LineString, box, shape
from shapely.ops import transform
from pyproj import Transformer
from PIL import Image, ImageDraw
from cv_tools.make_point_water_masks import GIS, WORKSPACE, BASE, points, sha
from cv_tools.train_point_cnn import OUT as CNN

OUT=BASE/'data/processed/point_width_validation_20261113'
HYDRO=WORKSPACE/'courses/AIDA-2156/data/processed/model_unit_history/20261103T070414Z'
STATIONS=['05CB001','05CB007','05CC002','05CC007']
PARAMS=dict(transect_length_m=500,parallel_offsets_m=[-50,0,50],orientation_sensitivity_degrees=[-10,0,10],maximum_hydro_age_seconds=300,cnn_threshold=.5,survey_orientation_maximum_distance_m=100,river_tangent_span_m=50)

def timestamp(s):return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def write_json(name,obj): (OUT/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def corr(x,y):
    x=np.asarray(x,float);y=np.asarray(y,float)
    if len(x)<5 or np.std(x)<1e-9 or np.std(y)<1e-9:return None
    return float(np.corrcoef(x,y)[0,1])
def ranks(a):
    a=np.round(np.asarray(a,dtype=float),6);out=np.zeros(len(a),float)
    for v in np.unique(a):
        ii=np.where(a==v)[0];out[ii]=np.sum(a<v)+(len(ii)+1)/2
    return out

def transects():
    forward=Transformer.from_crs(4326,32612,always_xy=True).transform
    rivers=[(f['properties']['river'],transform(forward,shape(f['geometry']))) for f in json.loads((GIS/'nrcan_nhn/selected_rivers.geojson').read_text())['features']]
    sections=[]
    for path in (GIS/'alberta_flood_surveys').rglob('cross_section_lines.geojson'):
        sections += [(f['properties'],transform(forward,shape(f['geometry']))) for f in json.loads(path.read_text())['features']]
    result={}
    for p in points():
        xy=np.array(forward(*p['coordinates']));pt=Point(xy);river_name='LITTLE RED DEER RIVER' if p['id']=='05CB001' else 'MEDICINE RIVER' if p['id']=='05CC007' else 'RED DEER RIVER'
        river=min([g for n,g in rivers if n==river_name],key=lambda g:g.distance(pt));along=river.project(pt)
        tangent=np.array(river.interpolate(min(river.length,along+50)).coords[0])-np.array(river.interpolate(max(0,along-50)).coords[0]);tangent/=np.linalg.norm(tangent)
        prop,section=min([(s,g) for s,g in sections if s['river']==river_name],key=lambda q:q[1].distance(pt));dist=section.distance(pt)
        if dist<=PARAMS['survey_orientation_maximum_distance_m']:
            s=section.project(pt);direction=np.array(section.interpolate(min(section.length,s+50)).coords[0])-np.array(section.interpolate(max(0,s-50)).coords[0]);direction/=np.linalg.norm(direction)
            basis='nearby_section_orientation_translated_to_exact_GIS_point'
        else:
            direction=np.array([-tangent[1],tangent[0]]);basis='perpendicular_to_local_GIS_river_tangent'
        result[p['id']]=dict(id=p['id'],coordinates=p['coordinates'],xy=xy.tolist(),direction=direction.tolist(),river_name=river_name,basis=basis,nearest_section_id=prop['section_id'],nearest_section_distance_m=float(dist),section_status=prop['line_status'],river_point_distance_m=river.distance(pt),transect_river_angle_degrees=float(np.degrees(np.arccos(np.clip(abs(np.dot(direction,tangent)),0,1)))))
    return result

def line_weights(ds,definition,offset=0,angle=0):
    v=np.array(definition['direction']);normal=np.array([-v[1],v[0]]);r=math.radians(angle);v=np.array([[math.cos(r),-math.sin(r)],[math.sin(r),math.cos(r)]])@v
    xy=np.array(definition['xy'])+offset*normal;line=LineString([xy-250*v,xy+250*v]);weights=np.zeros((61,61))
    # Exact line length inside native pixel cells; no artificial subpixel imagery.
    for row in range(61):
        for col in range(61):
            x0,y0=ds.transform*(col,row);x1,y1=ds.transform*(col+1,row+1)
            weights[row,col]=line.intersection(box(min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1))).length
    return weights,line

def hydro_series():
    out={};info={}
    for station in STATIONS:
        path=HYDRO/(station+'_observations.csv');rows=list(csv.DictReader(path.open(encoding='utf-8-sig')));rows=sorted(rows,key=lambda r:r['observed_at']);out[station]=([timestamp(r['observed_at']) for r in rows],rows);info[station]=dict(file=path.relative_to(WORKSPACE).as_posix(),sha256=sha(path),rows=len(rows))
    return out,info

def main():
    OUT.mkdir(parents=True,exist_ok=True);definitions=transects();write_json('transects.json',dict(parameters=PARAMS,points=definitions))
    manifest=json.loads((CNN/'dataset_manifest.json').read_text());records=manifest['records'];data=np.load(CNN/'dataset.npz');predictions=np.load(CNN/'test_predictions.npz');ids=predictions['indices'];prob=predictions['probabilities'];hydro,hydroinfo=hydro_series();rows=[];panels=[];cache={}
    for j,i in enumerate(ids):
        r=records[int(i)];point=r['point_id'];definition=definitions[point];truth=data['y'][i];valid=truth!=255;prediction=prob[j]>=.5
        train=[k for k,s in enumerate(records) if s['split']=='train' and s['point_id']==point]
        static=(data['y'][train]==1).sum(axis=0)/np.maximum((data['y'][train]!=255).sum(axis=0),1)>=.5
        maskpath=BASE/'data/processed/point_water_masks_20261113'/r['mask']
        with rasterio.open(maskpath) as ds:
            key=(point,tuple(ds.transform))
            if key not in cache:cache[key]={(off,ang):line_weights(ds,definition,off,ang) for off in [-50,0,50] for ang in [-10,0,10]}
            matrices=cache[key]
            with rasterio.open(WORKSPACE/r['source']) as src:
                w=rasterio.windows.from_bounds(*ds.bounds,transform=src.transform).round_offsets().round_lengths();a=src.read(window=w)
            row=dict(id=r['id'],point_id=point,image_at=r['date'],source=r['source'],split='test',month=r['date'][5:7],unknown_fraction=float((~valid).mean()),cloud_shadow_fraction=float(np.isin(a[4],[3,8,9,10]).mean()),snow_fraction=float((a[4]==11).mean()),mean_visible_brightness=float(data['x'][i,:3].mean()),width_kind='sum_of_water_intersections_not_bank_to_bank',label_type='automatic_candidate',hydro_match_status='no_local_observed_station' if point not in STATIONS else 'pending')
            for method,mask in [('cnn',prediction),('static',static),('weak_label',truth==1)]:
                widths=[]
                for offset in [-50,0,50]:
                    weight,_=matrices[(offset,0)];unknown=float(weight[~valid].sum());value=float(weight[mask&valid].sum())
                    row[f'{method}_width_offset_{offset}_m']=value if unknown<1e-6 and weight.sum()>499.99 else None
                    if offset==0:row['centre_unknown_length_m']=unknown
                    widths.append(row[f'{method}_width_offset_{offset}_m'])
                row[method+'_median_width_m']=float(np.median(widths)) if all(v is not None for v in widths) else None
                if method=='cnn':
                    variants=[]
                    for angle in [-10,0,10]:
                        vals=[]
                        for offset in [-50,0,50]:
                            weight,_=matrices[(offset,angle)]
                            if weight[~valid].sum()<1e-6 and weight.sum()>499.99:vals.append(float(weight[mask&valid].sum()))
                        if len(vals)==3:variants.append(float(np.median(vals)))
                    row['cnn_angle_sensitivity_span_m']=max(variants)-min(variants) if len(variants)==3 else None
            if point in STATIONS:
                times,obs=hydro[point];n=bisect_right(times,timestamp(r['date']))-1
                if n>=0 and 0<=timestamp(r['date'])-times[n]<=300:
                    h=obs[n];row.update(hydro_match_status='backward_within_300_seconds',observed_at=h['observed_at'],hydro_age_seconds=timestamp(r['date'])-times[n],discharge_m3_s=float(h['discharge_m3_s']) if h['discharge_m3_s'] else None,level_m=float(h['level_m']) if h['level_m'] else None,discharge_qualifier=h['discharge_qualifier'],level_qualifier=h['level_qualifier'],discharge_symbol=h['discharge_symbol'],level_symbol=h['level_symbol'],discharge_approval=h['discharge_approval'],level_approval=h['level_approval'],hydro_source_path=h['discharge_source_path'],hydro_received_at=h['discharge_received_at'],received_after_image=timestamp(h['discharge_received_at'])>timestamp(r['date']))
                else:row['hydro_match_status']='no_prior_observation_within_300_seconds'
            rows.append(row)
            if point not in [p[0] for p in panels]:
                rgb=(np.clip(np.moveaxis(data['x'][i,:3],0,-1)/.3,0,1)**(1/1.8)*255).astype('uint8');im=Image.fromarray(rgb).resize((305,305),Image.Resampling.NEAREST);draw=ImageDraw.Draw(im)
                for offset in [-50,0,50]:
                    _,line=matrices[(offset,0)];coords=[(~ds.transform)*(x,y) for x,y in line.coords];draw.line([(x*5,y*5) for x,y in coords],fill='red' if offset==0 else 'yellow',width=2)
                xy=(~ds.transform)*tuple(definition['xy']);draw.ellipse((xy[0]*5-4,xy[1]*5-4,xy[0]*5+4,xy[1]*5+4),outline='cyan',width=2);panels.append((point,im,r['date'][:10]))
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/'test_width_hydrometry.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
    reports={}
    for point in definitions:
        rr=[r for r in rows if r['point_id']==point];good=[r for r in rr if r['cnn_median_width_m'] is not None and r['weak_label_median_width_m'] is not None];pointresult=dict(test_images=len(rr),width_complete_three_transects=len(good),unknown_or_edge_rejected=len(rr)-len(good))
        if good:
            c=np.array([r['cnn_median_width_m'] for r in good]);b=np.array([r['static_median_width_m'] for r in good]);y=np.array([r['weak_label_median_width_m'] for r in good]);pointresult.update(cnn_width_range_m=[float(c.min()),float(c.max())],cnn_width_std_m=float(c.std()),static_width_std_m=float(b.std()),cnn_vs_weak_label_width_mae_m=float(np.abs(c-y).mean()),static_vs_weak_label_width_mae_m=float(np.abs(b-y).mean()),zero_cnn_width_count=int((c<1e-6).sum()),median_angle_sensitivity_span_m=float(np.median([r['cnn_angle_sensitivity_span_m'] for r in good if r['cnn_angle_sensitivity_span_m'] is not None])))
        pointresult['hydro_correlations']={}
        for variable in ['discharge_m3_s','level_m']:
            paired=[r for r in good if r.get(variable) is not None];x=[r['cnn_median_width_m'] for r in paired];y=[r[variable] for r in paired]
            if paired:
                clean=[r for r in paired if r['cloud_shadow_fraction']==0 and r['snow_fraction']==0 and r['unknown_fraction']==0]
                pointresult['hydro_correlations'][variable]=dict(n=len(paired),pearson=corr(x,y),spearman=corr(ranks(x),ranks(y)),variable_range=[min(y),max(y)],static_pearson=corr([r['static_median_width_m'] for r in paired],y),max_observation_age_seconds=max(r['hydro_age_seconds'] for r in paired),strict_clear_n=len(clean),strict_clear_spearman=corr(ranks([r['cnn_median_width_m'] for r in clean]),ranks([r[variable] for r in clean])),qualifiers=dict(Counter(r.get('discharge_qualifier' if variable=='discharge_m3_s' else 'level_qualifier','') for r in paired)))
        pointresult['season_slices']={}
        for season,months in [('winter',{'12','01','02'}),('spring',{'03','04','05'}),('summer',{'06','07','08'}),('autumn',{'09','10','11'})]:
            ss=[r for r in good if r['month'] in months];paired=[r for r in ss if r.get('discharge_m3_s') is not None]
            pointresult['season_slices'][season]=dict(n=len(ss),width_mean_m=float(np.mean([r['cnn_median_width_m'] for r in ss])) if ss else None,flow_spearman=corr(ranks([r['cnn_median_width_m'] for r in paired]),ranks([r['discharge_m3_s'] for r in paired])))
        pointresult['width_unknown_fraction_spearman']=corr(ranks([r['cnn_median_width_m'] for r in good]),ranks([r['unknown_fraction'] for r in good]))
        reports[point]=pointresult
    summary=dict(parameters=PARAMS,test_images=len(rows),observed_station_images=sum(r['point_id'] in STATIONS for r in rows),backward_matches=sum(r['hydro_match_status']=='backward_within_300_seconds' for r in rows),received_after_image_count=sum(r.get('received_after_image',False) for r in rows),hydrometry=hydroinfo,per_point=reports,cnn_result_sha256=sha(CNN/'result.json'),test_predictions_sha256=sha(CNN/'test_predictions.npz'),model_modified=False,physical_width_ground_truth_available=False,interpretation='retrospective_external_consistency_not_accuracy_or_causality')
    write_json('summary.json',summary)
    sheet=Image.new('RGB',(1005,1100),'white');draw=ImageDraw.Draw(sheet)
    for k,(point,im,day) in enumerate(panels):
        x=(k%3)*335;y=(k//3)*365;draw.text((x+5,y+5),point+' '+day,fill='black');draw.text((x+5,y+20),'Red: centre | yellow: +/-50 m',fill='black');sheet.paste(im,(x,y+40))
    sheet.save(OUT/'transect_review.png')
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
