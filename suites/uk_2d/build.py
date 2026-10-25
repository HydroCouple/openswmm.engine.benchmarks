"""Build source-locked UK inputs at the historical spacing; no engine execution."""
from __future__ import annotations
import argparse
import csv
import datetime as dt
from decimal import Decimal
import json
from pathlib import Path
import numpy as np
import yaml
from .sources import Sources, Raster, integral, digest, ROOT

COLLECTION = ROOT/'corpus/uk-ea-2d'
SPECS = {
 '1': dict(title='Disconnected water body', dx=10., end=72000, step=60., n=.03, bounds=[0,700,0,100], initial_stage=9.7),
 '2': dict(title='Filling floodplain depressions', dx=20., end=172800, step=300., n=.03, bounds=[0,2000,0,2000], inlet=[0,0,1900,2000], volume=97200),
 '3': dict(title='Momentum over an obstruction', dx=5., end=900, step=2., n=.01, bounds=[0,300,0,100], inlet=[0,0,0,100], volume=1310),
 '4': dict(title='Flood propagation', dx=5., end=18000, step=20., n=.05, bounds=[0,1000,0,2000], inlet=[0,0,990,1010], volume=285000),
 '5': dict(title='Valley flooding', dx=50., end=108000, step=60., n=.04, volume=9450000),
 '6a': dict(title='Laboratory dam break', dx=.1, end=120, step=.1, n=.01, bounds=[-7.6,91.5,-1.9,1.8]),
 '6b': dict(title='Scaled dam break', dx=2., end=1800, step=1., n=.05, bounds=[-152,1830,-38,36]),
}


def clock(seconds):
    # Explicit HMS is portable across readers that disagree about the units
    # of bare decimal step tokens (seconds versus decimal hours).
    value=Decimal(str(seconds))
    if not value.is_finite() or value<0:raise ValueError('Clock seconds must be finite and nonnegative')
    hours,remainder=divmod(value,Decimal(3600))
    minutes,sec=divmod(remainder,Decimal(60))
    whole=int(sec);fraction=sec-whole
    suffix=format(fraction,'f')[1:].rstrip('0') if fraction else ''
    return f'{int(hours)}:{int(minutes):02d}:{whole:02d}'+suffix


def series_clock(seconds):
    # Time-series scalars use hours. Step options use explicit clock strings.
    return f'{seconds/3600:.12g}' if seconds % 1 else clock(seconds)


def case_id(key):
    return 'uk-ea-2013-t'+(key.zfill(2) if key.isdigit() else key)


def valley_mesh(spec,raster,sources):
    import io
    import shapefile
    def shape(name):
        reader=shapefile.Reader(shp=io.BytesIO(sources.read(5,name+'.shp')),
                               shx=io.BytesIO(sources.read(5,name+'.shx')))
        shapes=reader.shapes()
        if len(shapes)!=1 or len(shapes[0].parts)!=1:raise ValueError('Expected one simple source polygon/line')
        return np.array(shapes[0].points)
    poly=shape('Test5ActiveArea_region');inlet=shape('Test5BC_polyline')
    dx=spec['dx'];lo=np.floor(poly.min(axis=0)/dx)*dx;hi=np.ceil(poly.max(axis=0)/dx)*dx
    spec['bounds']=[float(lo[0]),float(hi[0]),float(lo[1]),float(hi[1])]
    xs=np.arange(lo[0],hi[0]+dx/2,dx);ys=np.arange(lo[1],hi[1]+dx/2,dx)
    X,Y=np.meshgrid(xs,ys);vertices=np.column_stack([X.ravel(),Y.ravel(),np.zeros(X.size)])
    cells=[];nx=len(xs)-1
    for j in range(len(ys)-1):
        for i in range(nx):
            x,y=xs[i]+dx/2,ys[j]+dx/2;inside=False
            for a,b in zip(poly,np.roll(poly,-1,axis=0)):
                if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
            if inside:
                v=j*(nx+1)+i;cells.append([v,v+1,v+nx+2,v+nx+1])
    cells=np.array(cells);used=np.unique(cells);remap=np.full(len(vertices),-1);remap[used]=np.arange(len(used))
    vertices=vertices[used];vertices[:,2]=raster.sample(vertices[:,0],vertices[:,1],allow_nodata=True);cells=remap[cells]
    valid=np.isfinite(vertices[cells,2]).all(axis=1)
    spec['nodata_boundary_cells_excluded']=int((~valid).sum())
    cells=cells[valid]
    used=np.unique(cells);remap=np.full(len(vertices),-1);remap[used]=np.arange(len(used))
    vertices=vertices[used];cells=remap[cells]
    edges={}
    for ci,c in enumerate(cells):
        for edge in range(4):
            pair=tuple(sorted((c[(edge+1)%4],c[(edge+2)%4])))
            edges.setdefault(pair,[]).append((ci,edge))
    boundary=[];a,b=inlet;ab=b-a
    for pair,owners in edges.items():
        if len(owners)!=1:continue
        midpoint=vertices[list(pair),:2].mean(axis=0)
        t=np.dot(midpoint-a,ab)/np.dot(ab,ab)
        distance=np.linalg.norm(midpoint-(a+np.clip(t,0,1)*ab))
        if -.1<=t<=1.1 and distance<=.75*dx:boundary.append((*owners[0],dx))
    if not boundary:raise ValueError('No inlet edges found')
    return vertices,cells,np.zeros(len(cells)),boundary


def mesh(spec, raster):
    dx = spec['dx']; x0,x1,y0,y1 = spec['bounds']
    xs = np.linspace(x0,x1,round((x1-x0)/dx)+1)
    ys = np.linspace(y0,y1,round((y1-y0)/dx)+1)
    X,Y = np.meshgrid(xs,ys)
    Z = np.zeros_like(X) if raster is None else raster.sample(X,Y)
    vertices = np.column_stack([X.ravel(),Y.ravel(),Z.ravel()])
    nx,ny = len(xs)-1,len(ys)-1
    cells=[]; depths=[]; boundary=[]
    for j in range(ny):
        for i in range(nx):
            cx,cy = (xs[i]+xs[i+1])/2,(ys[j]+ys[j+1])/2
            v=j*(nx+1)+i
            ids=[v,v+1,v+nx+2,v+nx+1]
            ci=len(cells);cells.append(ids)
            bed=float(vertices[ids,2].mean())
            h=max(0,spec.get('initial_stage',bed)-bed)
            depths.append(h)
            if i==0:
                # Quad edge 2 is west: (v3,v0), outward normal -x.
                if 'inlet' not in spec or spec['inlet'][2] <= cy <= spec['inlet'][3]:
                    boundary.append((ci,2,float(ys[j+1]-ys[j])))
    return vertices,np.array(cells),np.array(depths),boundary


def build_case(key, sources, dest=COLLECTION, tin_mesh=None, test6b_elevations=None):
    spec=dict(SPECS[key]); dam=key.startswith('6')
    test=6 if dam else int(key)
    raster=None if key=='4' else Raster(sources.read(test,f'Test{key.upper() if dam else key}DEM.asc'))
    mesh_provenance=None
    if dam:
        if key=='6b' and test6b_elevations not in ('specification','dem'):
            raise ValueError('Test 6B DEM elevations are unchanged from 6A despite the written scaling instruction; select --test6b-elevations explicitly')
        if tin_mesh is None:raise ValueError('Test 6 requires --tin-mesh generated by the GUI mesher; Cartesian fallback is disabled')
        from .tin import audit, geometry
        data=np.load(tin_mesh,allow_pickle=False)
        vertices=np.array(data['vertices']);cells=np.array(data['cells'])
        review,walls=audit(vertices,cells,geometry())
        mesh_provenance=json.loads(Path(tin_mesh).with_name('mesh-provenance.json').read_text(encoding='utf-8'))
        if mesh_provenance['audit']!=review:raise ValueError('Mesh differs from audited GUI output')
        if (mesh_provenance['vertices_sha256']!=digest(vertices.tobytes()) or
            mesh_provenance['cells_sha256']!=digest(cells.tobytes()) or
            mesh_provenance['geometry_request']!=geometry()):raise ValueError('Mesh array/source geometry hash mismatch')
        scale=20 if key=='6b' else 1
        vertices*=scale
        if key=='6b' and test6b_elevations=='dem':vertices[:,2]/=scale
        depths=np.where(vertices[cells,0].mean(1)<0,.4,.02)*scale
        boundary=[]
        spec['bounds']=[-7.55*scale,91.45*scale,-1.8*scale,1.8*scale]
        # Read the locked specification as well as the DEM/probe sources.
        sources.read(6,'EA2DTest6 - May2010.pdf')
    else:
        vertices,cells,depths,boundary=valley_mesh(spec,raster,sources) if key=='5' else mesh(spec,raster)
    forcing=None
    if not dam:
        forcing=sources.forcing(test, f'Test{key}_BC.csv' if key=='2' else f'Test{key}BC.csv')
        if 'volume' in spec and abs(integral(forcing)-spec['volume'])>1e-6:
            raise ValueError('Forcing integral mismatch')
    probes=([dict(id='1',x=150.,y=50.),dict(id='2',x=250.,y=50.)] if key=='3' else
            sources.probes(test,f'Test{key.upper() if dam else key}output.csv'))
    ident=case_id(key); path=Path(dest)/ident; path.mkdir(parents=True,exist_ok=True)
    start=dt.datetime(2026,1,1); end=start+dt.timedelta(seconds=spec['end'])
    options=dict(FLOW_UNITS='CMS',INFILTRATION='HORTON',FLOW_ROUTING='DYNWAVE',LINK_OFFSETS='DEPTH',
                 ALLOW_PONDING='NO',THREADS='1',START_DATE='01/01/2026',START_TIME='00:00:00',
                 REPORT_START_DATE='01/01/2026',REPORT_START_TIME='00:00:00',
                 END_DATE=end.strftime('%m/%d/%Y'),END_TIME=end.strftime('%H:%M:%S'),
                 REPORT_STEP=clock(spec['step']),WET_STEP=clock(spec['step']),DRY_STEP=clock(spec['step']),ROUTING_STEP=str(min(10.,spec['step'])))
    lines=['[TITLE]',f';; UK EA 2013 Test {key}: {spec["title"]}',
           ';; Independent-reference assessment and SWMM2D regression only.','[OPTIONS]']
    lines += [f'{k} {v}' for k,v in options.items()]
    lines += ['[JUNCTIONS]','JD1 0 10 0 0 0','[OUTFALLS]','OD1 0 FREE NO','[CONDUITS]',
              'CD1 JD1 OD1 100 .01 0 0 0','[XSECTIONS]','CD1 CIRCULAR 1 0 0 0 1',
              '[REPORT]','INPUT NO','CONTROLS NO','SUBCATCHMENTS NONE','NODES NONE','LINKS NONE',
              '[2D_OPTIONS]','INTEGRATOR EXPLICIT','BACKEND CPU','MOMENTUM_EQUATION FULL_SWE',
              'RECONSTRUCTION_ORDER 2','LTS_TIERS 1','CFL_NUMBER .4','MAX_TIMESTEP 10',
              'DRY_DEPTH .0001','H_MOVE .0001','RAINFALL_MODE NONE','REPORT_2D NO',
              'OUTPUT_PRECISION FLOAT64','OUTPUT_COMPRESSION 1','REPORT_2D_VARIABLES DEPTH VELOCITY ENVELOPES','OUTPUT_FILE surface.h5',
              '[2D_VERTICES]']
    lines += [' '.join(f'{v:.12g}' for v in row) for row in vertices]
    lines += ['[2D_TRIANGLES]' if dam else '[2D_QUADS]']
    lines += [f'{" ".join(map(str,c))} {spec["n"]} {h:.12g}' for c,h in zip(cells,depths)]
    if dam:
        lines += ['[2D_BOUNDARY_CONDITIONS]']
        lines += [f'{ci} {edge} WALL * * wall' for ci,edge,_ in walls]
    if boundary:
        width=sum(b[2] for b in boundary)
        if 'inlet' in spec and abs(width-(spec['inlet'][3]-spec['inlet'][2]))>1e-8:
            raise ValueError('Inlet width differs from specification')
        lines += ['[2D_BOUNDARY_CONDITIONS]']
        lines += [f'{ci} {edge} {"TS_STAGE" if key=="1" else "TS_FLOW"} UKBC * inlet' for ci,edge,_ in boundary]
        lines += ['[TIMESERIES]']
        values=forcing[:,1] if key=='1' else -forcing[:,1]/width
        lines += [f'UKBC {series_clock(t)} {v:.12g}' for t,v in zip(forcing[:,0],values)]
    (path/'model.inp').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    with (path/'probes.csv').open('w',newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['id','x','y']);w.writeheader();w.writerows(probes)
    notes=[]
    if key=='5':
        notes=['Active cells selected by centre inside supplied polygon; boundary is a nominal 50 m Cartesian staircase.',
               'Inlet is mapped to exposed staircase edges near source line; total discharge normalized by selected edge length.',
               f'{spec["nodata_boundary_cells_excluded"]} boundary cells excluded because their corners intersect source NODATA.',
               'Polygon area, inlet geometry and refinement sensitivity remain to be qualified.']
    if dam:
        notes=['GUI constrained Delaunay triangles follow the dimensioned flume, dam abutments, 1 m opening and 0.8 by 0.4 m building rotated 64 degrees (all lengths scaled by 20 for 6B).',
               'Figure (a) defines exact straight wall geometry and 0.34 m wide / 0.155 m high side-bank slopes; pixelated DEM barrier transitions are not fitted. This is a drawing-based geometric reconstruction, not a vertexwise reproduction of the supplied DEM.',
               'Bank toes and X=0 depth discontinuity are internal mesh constraints, not walls. All exposed edges are explicit reflective WALL boundaries.',
               'Initial conditions are uniform water depths, as specified, including over the bank slopes; no fitted time shift or roughness calibration.',
               'Original measured series missing; recovered isolated UCL markers provide exploratory 6A comparison only.']
        if key=='6b':
            notes.append('Supplied 6B DEM elevations are numerically identical to 6A despite the written instruction to scale all physical dimensions by 20. '
                         +('This input follows the written vertical scaling (side banks 3.1 m high).' if test6b_elevations=='specification' else
                           'This input follows the unscaled vertical dimensions of the supplied DEM (drawing-based side banks 0.155 m high).'))
    if dam:
        from .tin import areas
        cell_areas=areas(vertices,cells)
    else:cell_areas=np.full(len(cells),spec['dx']**2)
    case=dict(schema_version=1,id=ident,uk_test=key,**spec,cell_count=len(cells),
              area_m2=float(cell_areas.sum()),initial_volume_m3=float(np.dot(depths,cell_areas)),
              probe_count=len(probes),reference_class='self_consistency',
              observed_status='missing' if key=='6a' else 'not_applicable',deviations=notes,
              source_hashes={k:r['sha256'] for k,r in sources.used.items() if f'Test{test}_dataset' in k},
              model_sha256=digest((path/'model.inp').read_bytes()),probes_sha256=digest((path/'probes.csv').read_bytes()),
              numerical_limits=dict(continuity_pct=.5,min_depth_m=-1e-10))
    if forcing is not None:
        case['forcing']=[list(map(float,row)) for row in forcing]
        case['boundary_kind']='stage' if key=='1' else 'flow'
        case['boundary_width_m']=sum(b[2] for b in boundary)
    (path/'case.json').write_text(json.dumps(case,indent=2)+'\n', encoding='utf-8')
    if dam:
        mesh_provenance=dict(mesh_provenance,scale=scale,model_sha256=case['model_sha256'])
        column=round((10*scale-raster.x0)/raster.dx)
        yz=np.column_stack([raster.y0+np.arange(raster.ny)*raster.dx,raster.z[:,column]])
        yz=yz[np.isfinite(yz[:,1])&(yz[:,1]<1.)&(abs(yz[:,0])<=1.8*scale+1e-9)]
        zscale=1 if key=='6b' and test6b_elevations=='dem' else scale
        drawing=.155/.34*np.maximum(abs(yz[:,0]/scale)-1.46,0)*zscale
        if key=='6b':
            mesh_provenance['vertical_interpretation']=test6b_elevations
            mesh_provenance['source_conflict']='The locked 6A and 6B DEM elevation arrays are numerically identical; only XY is scaled. This conflicts with literal all-physical-dimensions scaling in the written specification.'
        mesh_provenance['source_dem_cross_section_audit']=dict(
            source=f'Test{key.upper()}DEM.asc, checksum in case.json; elevated wall pixels excluded',
            x_m=float(raster.x0+column*raster.dx),
            max_absolute_bed_difference_m=float(np.max(abs(drawing-yz[:,1]))),
            columns=['y_m','supplied_dem_m','drawing_bed_m'],samples=np.column_stack([yz,drawing]).tolist(),
            scope='Source-interpretation diagnostic at one unobstructed cross-section, not a global DEM error bound or a fit to hydraulic measurements.')
        (path/'mesh-provenance.json').write_text(json.dumps(mesh_provenance,indent=2)+'\n', encoding='utf-8')
    tags=['hydraulics','2d','finite_volume_2d','regression','uk_ea_2d']
    if key=='6a': tags+=['physical_model']
    meta=dict(id=ident,title='UK EA 2013 Test '+key+': '+spec['title'],tags=tags,units='SI',routing='DYNWAVE',
              size_class='S' if len(cells)<100 else 'M' if len(cells)<1000 else 'L' if len(cells)<10000 else 'XL',
              tiers=['nightly','weekly'],reference={'class':'self_consistency'},
              notes='Dedicated uk_2d suite; excluded from engine-to-engine parity. See case.json for geometry and source identity.')
    prov=dict(source='Environment Agency SC120002/R Appendix A and Benchmarking_Model_Data.zip',
              citation='Neelz and Pender (2013), SC120002/R, Appendix A',
              url='https://www.gov.uk/flood-and-coastal-erosion-risk-management-research-reports/2d-benchmarking-evaluating-the-latest-generation-of-the-hydraulic-models-for-fcrm',
              license='unverified',contributed_by='HydroCouple',date_added='2026-10-22',original_units='SI',
              modifications=('GUI constrained Delaunay triangulation of specification geometry; SI depths. ' if dam else
                             'Deterministic bilinear DEM sampling onto nominal Cartesian quads; SI forcing. ')+ ' '.join(notes))
    for name,data in [('metadata.yaml',meta),('provenance.yaml',prov)]:
        (path/name).write_text(yaml.safe_dump(data,sort_keys=False,allow_unicode=True), encoding='utf-8')
    print(ident,len(cells),'cells',flush=True)
    return case


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive',type=Path,required=True)
    ap.add_argument('--only',default=','.join(SPECS))
    ap.add_argument('--destination',type=Path,default=COLLECTION)
    ap.add_argument('--tin-mesh',type=Path,help='Audited GUI mesh.npz at 6A scale, used for both Test 6 variants')
    ap.add_argument('--test6b-elevations',choices=['specification','dem'],
                    help='Required for 6B: scale Z by 20 per written specification, or retain the supplied DEM vertical dimensions')
    args=ap.parse_args(argv)
    keys=args.only.split(',')
    if set(keys)-SPECS.keys():ap.error('Unknown case selection')
    sources=Sources(args.archive)
    if '6b' in keys and args.test6b_elevations is None:ap.error('Test 6B source conflict requires --test6b-elevations')
    for key in keys:build_case(key,sources,args.destination,args.tin_mesh,args.test6b_elevations)
    if set(keys)&{'5','6b'}:
        from .profiles import import_profiles
        from .sources import INVENTORY
        import_profiles(args.archive,INVENTORY,args.destination)

if __name__=='__main__':main()
