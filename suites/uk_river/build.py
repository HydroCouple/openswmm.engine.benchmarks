"""Author deterministic source-derived SWMM2D river cases."""
from __future__ import annotations
import argparse
import csv
import datetime as dt
from pathlib import Path
import numpy as np
import yaml
from .references import CORPUS,write_json,write_csv,digest
from suites.uk_2d.build import clock,series_clock

KEYS=['a1','a2','a3','a4','a5','e','f-mean','f-high','l','l-fine','j']


def reference(key):
    key='f' if key.startswith('f-') else 'l' if key.startswith('l') else key
    return CORPUS/('uk-river-'+key)/'reference'


def spec(key):
    if key.startswith('a'):
        return dict(title='Test A Part '+key[1:]+' quasi-steady flow',length=100.,width=10.,nx=100,ny=2,end=3600.,step=20.,n=.03,
            deviations=['A transient SWMM2D march initialized from the analytical profile reproduces the source quasi-steady duration; no independent direct steady solver is claimed.',
            'SWMM2D applies bed Manning friction using depth; the source 1D solution includes finite-width hydraulic radius. Sidewall shear is not added or calibrated.',
            'The 1 m source spacing is retained along the flow; two 5 m-wide cells span the uniform 10 m section.',
            'Source cross sections/analytical levels are tabulated at 1 m. Linear interpolation onto cell centres is disclosed, especially across hydraulic jumps.'])
    if key=='e':
        return dict(title='Test E Ippen tidal-wave scenario',length=100000.,width=1000.,nx=200,ny=2,end=14400.,step=60.,n=.025,
            deviations=['Full nonlinear SWE with quadratic Manning friction; Ippen\'s linearized equation is an approximate comparator.',
            'Use the specified sine stage forcing and initial 20 m still water. Published reference phase/linear-friction ambiguity remains unresolved; no analytical accuracy verdict is issued.'])
    if key.startswith('f-'):
        return dict(title='Test F monoclinal wave, Manning '+('0.0241' if key=='f-mean' else '0.0256'),
            length=1000000.,width=1000.,nx=200,ny=2,end=108000.,step=360.,n=.0241 if key=='f-mean' else .0256,
            deviations=['Reference is the published analytical initial profile translated at 3.7989396 m/s, using linear interpolation of its 5 km samples.',
            'Constant Manning roughness reproduces the reported variants but differs from the constant Chezy law defining the analytical wave. Reference errors include this model-form difference.'])
    if key.startswith('l'):
        dx=.025 if key=='l-fine' else .05
        return dict(title='Test L CADAM constricted-channel dam break'+(' (finer mesh)' if key=='l-fine' else ''),
            length=19.3,width=.5,nx=round(19.3/dx),ny=round(.5/dx),end=10.,step=.04,n=.01,
            deviations=['The physical 19.3 m laboratory channel is represented directly. This differs from the result report\'s extended 40 m reservoir and delayed analytical initialization.',
            'The initial dam is removed instantaneously at t=0; the physical gate opened in approximately 0.2 s. No fitted time shift.',
            'The 45-degree constriction tapers are fitted by nonrectangular quads; no staircase or artificial raised terrain substitutes for the walls.',
            'Gauge predictions use the containing cell. Instrument spatial averaging and uncertainty are not supplied.'])
    raise ValueError('No executable bridge representation for '+key)


def geometry(key,s):
    if key.startswith('l'):
        # Physical reservoir 0..6.1 m; taper 13.8..14.0; throat ..15.0; expansion ..15.2.
        # Piecewise-linear boundary is represented exactly by quad vertices.
        xs=np.linspace(0,s['length'],s['nx']+1)
        width=np.interp(xs,[0,13.8,14.,15.,15.2,19.3],[.5,.5,.1,.1,.5,.5])
        yy=np.linspace(-.5,.5,s['ny']+1)
        vertices=np.array([[x,y*w,0] for y in yy for x,w in zip(xs,width)])
    else:
        xs=np.linspace(0,s['length'],s['nx']+1);ys=np.linspace(0,s['width'],s['ny']+1)
        z=np.zeros_like(xs)
        if key.startswith('a'):
            r=np.genfromtxt(reference(key)/'reference.csv',delimiter=',',names=True)
            z=np.interp(100-xs,r['chainage_m'],r['bed_m'])
        if key.startswith('f-'):z=400-.0004*xs
        vertices=np.array([[x,y,zz] for y in ys for x,zz in zip(xs,z)])
    cells=[]
    for j in range(s['ny']):
        for i in range(s['nx']):
            v=j*(s['nx']+1)+i;cells.append([v,v+1,v+s['nx']+2,v+s['nx']+1])
    cells=np.array(cells);poly=vertices[cells];centre=poly.mean(axis=1)
    area=.5*abs(np.sum(poly[:,:,0]*np.roll(poly[:,:,1],-1,axis=1)-poly[:,:,1]*np.roll(poly[:,:,0],-1,axis=1),axis=1))
    if np.any(area<=0):raise ValueError('Nonpositive mesh cell area')
    return vertices,cells,centre,area


def build_case(key):
    s=spec(key);path=CORPUS/('uk-river-'+key);path.mkdir(parents=True,exist_ok=True)
    vertices,cells,centre,area=geometry(key,s);x=centre[:,0];z=centre[:,2]
    u=np.zeros(len(cells));h=np.full(len(cells),20.)
    if key.startswith('a'):
        r=np.genfromtxt(reference(key)/'reference.csv',delimiter=',',names=True)
        h=np.interp(100-x,r['chainage_m'],r['level_m'])-z;u=2/h
        probes=[dict(id=f'C{c:g}',x=100-c,y=5.) for c in range(1,100)]
    elif key.startswith('f-'):
        r=np.genfromtxt(reference(key)/'reference.csv',delimiter=',',names=True)
        h=np.interp(x,r['distance_from_upstream_m'],r['depth_m'])
        q=np.interp(x,r['distance_from_upstream_m'],r['discharge_m3s']);u=q/(1000*h)
        probes=[dict(id=f'X{c}',x=c,y=500.) for c in [50000,250000,500000,750000,950000]]
    elif key.startswith('l'):
        h=np.where(x<6.1,.3,.003)
        probes=[dict(id=name,x=6.1+offset,y=0.) for name,offset in zip(['S1','S2','S3','S4'],[-1.,6.1,8.8,10.5])]
    else:probes=[dict(id=f'C{c}',x=c,y=500.) for c in [0,25000,50000,75000]]
    if np.any(h<=0):raise ValueError('Nonpositive initial water depth')
    end=dt.datetime(2026,1,1)+dt.timedelta(seconds=s['end'])
    options=dict(FLOW_UNITS='CMS',FLOW_ROUTING='DYNWAVE',THREADS='1',START_DATE='01/01/2026',START_TIME='00:00:00',
        REPORT_START_DATE='01/01/2026',REPORT_START_TIME='00:00:00',END_DATE=end.strftime('%m/%d/%Y'),END_TIME=end.strftime('%H:%M:%S'),
        REPORT_STEP=clock(s['step']),ROUTING_STEP=str(min(20,s['step'])),WET_STEP=clock(s['step']),DRY_STEP=clock(s['step']))
    lines=['[TITLE]',';; W5-105 river '+s['title'],';; Independent references only; see case.json for representation differences.','[OPTIONS]']
    lines += [f'{k} {v}' for k,v in options.items()]
    lines += ['[JUNCTIONS]','JD1 0 10 0 0 0','[OUTFALLS]','OD1 0 FREE NO','[CONDUITS]','CD1 JD1 OD1 100 .01 0 0 0',
        '[XSECTIONS]','CD1 CIRCULAR 1 0 0 0 1','[REPORT]','NODES NONE','LINKS NONE','[2D_OPTIONS]',
        'INTEGRATOR EXPLICIT','BACKEND CPU','MOMENTUM_EQUATION FULL_SWE','RECONSTRUCTION_ORDER 2','LTS_TIERS 1','CFL_NUMBER .4',
        'MAX_TIMESTEP 20','DRY_DEPTH .00001','H_MOVE .00001','RAINFALL_MODE NONE','REPORT_2D NO','OUTPUT_PRECISION FLOAT64',
        'OUTPUT_COMPRESSION 1','REPORT_2D_VARIABLES DEPTH VELOCITY ENVELOPES','OUTPUT_FILE surface.h5','[2D_VERTICES]']
    lines += [' '.join(f'{v:.12g}' for v in row) for row in vertices]
    lines += ['[2D_QUADS]']+[' '.join(map(str,c))+f' {s["n"]} {hh:.12g}' for c,hh in zip(cells,h)]
    lines += ['[2D_INITIAL_VELOCITY]']+[f'{i} {uu:.12g} 0' for i,uu in enumerate(u)]
    lines += ['[2D_BOUNDARY_CONDITIONS]']
    for j in range(s['ny']):
        west=j*s['nx'];east=west+s['nx']-1
        if key.startswith('a'):
            lines += [f'{west} 2 SPECIFIED_FLOW -2 * upstream',f'{east} 0 SPECIFIED_STAGE {r["level_m"][0]} * downstream']
        elif key.startswith('f-'):
            lines += [f'{west} 2 SPECIFIED_FLOW -24.693395 * upstream',f'{east} 0 SPECIFIED_STAGE 3 * downstream']
        elif key=='e':lines += [f'{east} 0 TS_STAGE TIDE * open']
        else:lines += [f'{east} 0 SPECIFIED_STAGE .003 * downstream']
    if key=='e':
        lines += ['[TIMESERIES]']+[f'TIDE {series_clock(t)} {20+np.sin(2*np.pi*t/7200):.12g}' for t in np.arange(0,14401,60)]
    (path/'model.inp').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write_csv(path/'probes.csv',['id','x','y'],[[p['id'],p['x'],p['y']] for p in probes])
    case=dict(id=path.name,key=key,**s,uk_test='river',cell_count=len(cells),area_m2=float(area.sum()),initial_volume_m3=float(area@h),
        initial_state='Source analytical depth and discharge' if key.startswith(('a','f-')) else 'Physical still-water initial state',
        source_reference=reference(key).relative_to(CORPUS).as_posix(),model_sha256=digest((path/'model.inp').read_bytes()),
        probes_sha256=digest((path/'probes.csv').read_bytes()),numerical_limits=dict(continuity_pct=.5,min_depth_m=-1e-10))
    write_json(path/'case.json',case)
    tags=['hydraulics','2d','finite_volume_2d','regression','uk_ea_river']
    tags+=['physical_model'] if key.startswith('l') else ['analytical'] if key!='e' else []
    meta=dict(id=path.name,title=s['title'],tags=tags,units='SI',routing='DYNWAVE',size_class='L' if len(cells)>1000 else 'M',tiers=['nightly','weekly'],
        reference={'class':'observed' if key.startswith('l') else 'self_consistency' if key=='e' else 'analytic'},
        notes='Dedicated uk_river suite; never engine-to-engine parity. '+ ' '.join(s['deviations']))
    for name,value in [('metadata.yaml',meta),('provenance.yaml',dict(source='Environment Agency W5-105/TR1 and TR2',citation='Crowder et al. (2004), W5-105 river benchmarks',license='unverified',contributed_by='HydroCouple',date_added='2026-10-22',original_units='SI',modifications='SWMM2D representation; see case.json.'))]:
        (path/name).write_text(yaml.safe_dump(value,sort_keys=False),encoding='utf-8')
    print(path.name,len(cells),'cells',flush=True)
    return case


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--only',default=','.join(k for k in KEYS if k!='j'))
    for key in ap.parse_args().only.split(','):build_case(key)
