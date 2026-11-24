"""Explicit-input screening calculations; no implicit datum, bank or runoff assumptions."""
from math import isfinite, hypot


def section_geometry(profile, water_surface_m, *, connected_offset_m=None):
    """Integrate piecewise-linear bed geometry, including partial wet triangles.

    Without a documented main-channel seed, report all wet components separately.
    Open survey edges flag a truncated cross-section, not an infinite vertical bank.
    """
    h=float(water_surface_m)
    if not isfinite(h):raise ValueError('Finite water surface elevation required')
    points=sorted((float(x),float(z)) for x,z in profile)
    if len(points)<2 or any(not isfinite(x) or not isfinite(z) for x,z in points):
        raise ValueError('At least two finite surveyed points required')
    if any(b[0]<=a[0] for a,b in zip(points,points[1:])):
        raise ValueError('Profile offsets must be unique and strictly increasing')
    components=[]
    for (x1,z1),(x2,z2) in zip(points,points[1:]):
        if z1>=h and z2>=h:continue
        left,right=x1,x2;zl,zr=z1,z2
        if z1>h:left=x1+(h-z1)*(x2-x1)/(z2-z1);zl=h
        if z2>h:right=x1+(h-z1)*(x2-x1)/(z2-z1);zr=h
        area=(right-left)*(max(0,h-zl)+max(0,h-zr))/2
        perimeter=hypot(right-left,zr-zl)
        if components and abs(components[-1]['end_m']-left)<1e-8 and z1<h:
            c=components[-1];c['end_m']=right;c['area_m2']+=area;c['wetted_perimeter_m']+=perimeter
        else:components.append({'start_m':left,'end_m':right,'area_m2':area,'wetted_perimeter_m':perimeter})
    if connected_offset_m is not None:
        components=[c for c in components if c['start_m']<=connected_offset_m<=c['end_m']]
    area=sum(c['area_m2'] for c in components)
    width=sum(c['end_m']-c['start_m'] for c in components)
    perimeter=sum(c['wetted_perimeter_m'] for c in components)
    return {'water_surface_elevation_m':h,'area_m2':area,'surface_width_m':width,
            'wetted_perimeter_m':perimeter,'hydraulic_radius_m':area/perimeter if perimeter else None,
            'wet_components':len(components),'components':components,
            'profile_truncated':h>points[0][1] or h>points[-1][1]}


def screen_section(profile, *, level_m, gauge_zero_m, discharge_m3_s=None,
                   bank_elevations_m=None, datum_verified=False, transfer_verified=False,
                   profile_verified=False, banks_verified=False, connected_offset_m=None):
    missing=[]
    for condition,name in [(datum_verified and gauge_zero_m is not None,'datum'),
                            (transfer_verified,'gauge_to_section_transfer'),(profile_verified,'profile'),
                            (level_m is not None,'water_level')]:
        if not condition:missing.append(name)
    if missing:return {'status':'indeterminate','missing':missing,'risk_level':None}
    result=section_geometry(profile,float(level_m)+float(gauge_zero_m),connected_offset_m=connected_offset_m)
    q=None if discharge_m3_s is None else float(discharge_m3_s)
    if q is not None and (not isfinite(q) or q<0):raise ValueError('Nonnegative finite discharge required')
    result['mean_velocity_m_s']=q/result['area_m2'] if q is not None and result['area_m2']>0 else None
    result['status']='geometry_only';result['risk_level']=None
    if (result['profile_truncated'] or result['wet_components']>1 and connected_offset_m is None
            or connected_offset_m is not None and not result['wet_components']
            or q is not None and q>0 and result['area_m2']<=0):
        result['status']='geometry_requires_review';result['mean_velocity_m_s']=None;return result
    if banks_verified and bank_elevations_m and len(bank_elevations_m)==2 and all(isfinite(float(z)) for z in bank_elevations_m):
        result['bank_freeboards_m']=[float(z)-result['water_surface_elevation_m'] for z in bank_elevations_m]
        result['freeboard_m']=min(result['bank_freeboards_m'])
        f=result['freeboard_m']
        result['risk_level']='red' if f<=0 else 'orange' if f<=0.5 else 'yellow' if f<=1 else 'green'
        result['status']='screening_only'
        result['threshold_basis']='Adjustable project demonstration thresholds, not official warnings'
    return result


def reach_storage(area_up_m2,area_down_m2,length_m):
    values=[float(area_up_m2),float(area_down_m2),float(length_m)]
    if any(not isfinite(x) or x<0 for x in values):raise ValueError('Nonnegative finite inputs required')
    return (values[0]+values[1])/2*values[2]


def travel_time_seconds(length_m,velocity_m_s):
    if not isfinite(length_m) or length_m<0 or not isfinite(velocity_m_s) or velocity_m_s<=0:
        raise ValueError('Nonnegative distance and positive velocity required')
    return length_m/velocity_m_s


def routed_discharge(contributions, *, target_time, incremental_runoff_m3_s=0):
    """Combine explicit lag-aligned, nonoverlapping sources; no automatic rainfall-to-Q conversion."""
    from API.observations import parse_time
    if not contributions:raise ValueError('At least one documented contributing source is required')
    sources=set();q=0.0
    if not isfinite(incremental_runoff_m3_s) or incremental_runoff_m3_s<0:raise ValueError('Invalid local inflow')
    for c in contributions:
        area=set(c['contributing_area_ids'])
        if not area or sources & area:raise ValueError('Missing or overlapping contributing areas')
        sources.update(area)
        lag=c['lag_seconds']
        if not isfinite(lag) or lag<0:raise ValueError('Invalid propagation lag')
        if abs((parse_time(target_time)-parse_time(c['observed_at'])).total_seconds()-lag)>1:
            raise ValueError('Flows are not aligned to the target arrival time')
        flow=float(c['discharge_m3_s'])
        if not isfinite(flow) or flow<0:raise ValueError('Invalid discharge')
        q+=flow
    return q+incremental_runoff_m3_s


def rating_level(discharge_m3_s, rating_pairs):
    """Interpolate a caller-validated local Q-H relation; forbid extrapolation."""
    pairs=sorted((float(q),float(h)) for q,h in rating_pairs)
    if len(pairs)<2 or any(not isfinite(x) for pair in pairs for x in pair):raise ValueError('Invalid rating relation')
    if any(q2<=q1 or h2<h1 for (q1,h1),(q2,h2) in zip(pairs,pairs[1:])):raise ValueError('Rating relation must be monotonic')
    if not isfinite(discharge_m3_s) or not pairs[0][0]<=discharge_m3_s<=pairs[-1][0]:raise ValueError('Discharge outside validated range')
    for (q1,h1),(q2,h2) in zip(pairs,pairs[1:]):
        if q1<=discharge_m3_s<=q2:return h1+(h2-h1)*(discharge_m3_s-q1)/(q2-q1)
