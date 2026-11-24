"""Quality sensitivity and plots for frozen point-width indirect validation."""
import csv
from collections import Counter
import json
import numpy as np
from PIL import Image,ImageDraw
from cv_tools.validate_point_widths import OUT,STATIONS,corr,ranks

def number(r,key):return float(r[key]) if r.get(key) not in ('',None) else None

def main():
    rows=list(csv.DictReader((OUT/'test_width_hydrometry.csv').open()));summary=json.loads((OUT/'summary.json').read_text())
    for point,report in summary['per_point'].items():
        rr=[r for r in rows if r['point_id']==point];report['centre_width_correlations']={}
        for var in ['discharge_m3_s','level_m']:
            paired=[r for r in rr if number(r,'cnn_width_offset_0_m') is not None and number(r,var) is not None]
            if paired:report['centre_width_correlations'][var]=dict(n=len(paired),pearson=corr([number(r,'cnn_width_offset_0_m') for r in paired],[number(r,var) for r in paired]),spearman=corr(ranks([number(r,'cnn_width_offset_0_m') for r in paired]),ranks([number(r,var) for r in paired])))
        if point not in STATIONS:continue
        good=[r for r in rr if number(r,'cnn_median_width_m') is not None]
        for var in ['discharge_m3_s','level_m']:
            paired=[r for r in good if number(r,var) is not None]
            clean=[r for r in paired if number(r,'cloud_shadow_fraction')==0 and number(r,'snow_fraction')==0 and number(r,'unknown_fraction')==0]
            report['hydro_correlations'][var]['spearman']=corr(ranks([number(r,'cnn_median_width_m') for r in paired]),ranks([number(r,var) for r in paired]))
            report['hydro_correlations'][var]['strict_clear_spearman']=corr(ranks([number(r,'cnn_median_width_m') for r in clean]),ranks([number(r,var) for r in clean]))
        for season,months in [('winter',{'12','01','02'}),('spring',{'03','04','05'}),('summer',{'06','07','08'}),('autumn',{'09','10','11'})]:
            ss=[r for r in good if r['month'] in months]
            report['season_slices'][season]['flow_spearman']=corr(ranks([number(r,'cnn_median_width_m') for r in ss]),ranks([number(r,'discharge_m3_s') for r in ss]))
        ungraded=[r for r in good if not r['discharge_qualifier']]
        report['ungraded_discharge_sensitivity']=dict(n=len(ungraded),pearson=corr([number(r,'cnn_median_width_m') for r in ungraded],[number(r,'discharge_m3_s') for r in ungraded]),spearman=corr(ranks([number(r,'cnn_median_width_m') for r in ungraded]),ranks([number(r,'discharge_m3_s') for r in ungraded])))
        report['hydro_stage_discharge_spearman']=corr(ranks([number(r,'discharge_m3_s') for r in rr]),ranks([number(r,'level_m') for r in rr]))
        report['approval_counts']=dict(Counter(r['discharge_approval'] for r in rr))
        report['width_brightness_spearman']=corr(ranks([number(r,'cnn_median_width_m') for r in good]),ranks([number(r,'mean_visible_brightness') for r in good]))
    summary['all_point_width_complete_count']=sum(p['width_complete_three_transects'] for p in summary['per_point'].values())
    summary['station_width_complete_count']=sum(summary['per_point'][p]['width_complete_three_transects'] for p in STATIONS)
    summary['quality_approval_counts']=dict(Counter(r['discharge_approval'] for r in rows if r['point_id'] in STATIONS))
    summary['scope_limitations']=['No observed P01-P05 hydrometry or verified arrival matching exists in project_etl.', 'All matched observations were archived after the image date; historical real-time availability and revisions are not validated.', 'No physical-width ground truth, no winter test scenes, small seasonal subsets, no parameter tuning from these correlations.']
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    canvas=Image.new('RGB',(1100,1340),'white');draw=ImageDraw.Draw(canvas)
    draw.text((20,10),'Frozen test CNN: indirect water-width / hydrometry consistency',fill='black')
    draw.text((20,28),'Green spring | orange summer | blue autumn | gray fixed-mask width; NOT width ground truth',fill='black')
    colours={'spring':'#2c8a51','summer':'#d78a1e','autumn':'#316daf','winter':'#666666'}
    for row,point in enumerate(STATIONS):
        rr=[r for r in rows if r['point_id']==point and number(r,'cnn_median_width_m') is not None]
        for col,(var,label) in enumerate([('discharge_m3_s','Q (m3/s)'),('level_m','Gauge stage (m)')]):
            x0=col*550+65;y0=row*315+100;w=440;h=220
            xs=np.array([number(r,var) for r in rr]);ys=np.array([number(r,'cnn_median_width_m') for r in rr]);static=np.array([number(r,'static_median_width_m') for r in rr]);xmin,xmax=float(xs.min()),float(xs.max());ymin=0;ymax=max(float(ys.max()),float(static.max()))*1.15
            def px(x):return x0+(x-xmin)/max(xmax-xmin,1e-9)*w
            def py(y):return y0+h-y/max(ymax,1)*h
            rho=summary['per_point'][point]['hydro_correlations'][var]['spearman'];draw.text((x0,y0-35),f'{point} | n={len(rr)} | Spearman={rho:.3f}' if rho is not None else f'{point} | n={len(rr)} | Spearman undefined',fill='black')
            draw.line((x0,y0,x0,y0+h,x0+w,y0+h),fill='black',width=1)
            draw.line((x0,py(float(static.mean())),x0+w,py(float(static.mean()))),fill='#999999',width=2)
            for r,x,y in zip(rr,xs,ys):
                month=int(r['month']);season='spring' if month in [3,4,5] else 'summer' if month in [6,7,8] else 'autumn' if month in [9,10,11] else 'winter';xx,yy=px(x),py(y);draw.ellipse((xx-4,yy-4,xx+4,yy+4),fill=colours[season])
            draw.text((x0,y0+h+8),f'{xmin:.3g}',fill='black');draw.text((x0+w-35,y0+h+8),f'{xmax:.3g}',fill='black');draw.text((x0+160,y0+h+25),label,fill='black');draw.text((x0-55,y0),f'{ymax:.0f} m',fill='black');draw.text((x0-20,y0+h-8),'0',fill='black');draw.text((x0,y0-18),'Width: median of 3 fixed transects',fill='black')
    canvas.save(OUT/'hydrometry_width_scatter.png')
    lines=['# Indirect width validation','', 'Frozen 132-image CNN test set; no retraining or threshold changes.','', '| Station | usable widths / images | Q Spearman | stage Spearman |','|---|---:|---:|---:|']
    for point in STATIONS:
        r=summary['per_point'][point];lines.append(f"| {point} | {r['width_complete_three_transects']} / {r['test_images']} | {r['hydro_correlations']['discharge_m3_s']['spearman']:.3f} | {r['hydro_correlations']['level_m']['spearman']:.3f} |")
    lines += ['', '70/70 station images match a past observation within 300 seconds; 68 have all three transects free of unknown pixels. There is no consistent positive width-flow relationship across stations. These checks do not validate the current width output as a physical measurement or downstream MLP target.', '', 'The 05CC007 CNN median width is zero for five scenes despite positive observed discharge (0.107, 0.780, 0.399, 0.174 and 0.137 m3/s). This is a resolution/occlusion/detection warning, not evidence of a dry channel. P04 has large apparent width variation and poorer weak-label width agreement than the fixed mask. Neither phenomenon should be interpreted as observed flooding.', '', 'Baseline widths are constant, so their correlation is undefined rather than zero. No observed physical width is available; MAE in summary.json compares CNN/static widths with automatic mask widths only. P01-P05 have no independent local hydrometry or verified arrival alignment, so no neighboring-station substitution is made.', '', 'Quality: 65 provisional and 5 final archived station observations. Numeric Q grade codes 10/20/30 have no verified local meaning; blank-code sensitivity is reported without calling it authoritative truth. All records were received after acquisition, so this is retrospective consistency, not a historical operational replay.', '', 'There are no winter scenes. Seasonal subsets are small; direction changes within seasons and after clear-only selection show potential confounding. Native 10 m pixels, bridge overlap, planned/translated transects and +/-10 degree orientation sensitivity limit precision. Correlation is neither ground truth nor causality.', '', 'Reproduce: python -B run.py -m cv_tools.validate_point_widths; python -B run.py -m cv_tools.summarize_point_widths. Raw and derived data remain Git-ignored.']
    (OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({p:{'centre':summary['per_point'][p]['centre_width_correlations'],'ungraded':summary['per_point'][p]['ungraded_discharge_sensitivity'],'Q_H':summary['per_point'][p]['hydro_stage_discharge_spearman'],'brightness':summary['per_point'][p]['width_brightness_spearman']} for p in STATIONS},indent=2))

if __name__=='__main__':main()
