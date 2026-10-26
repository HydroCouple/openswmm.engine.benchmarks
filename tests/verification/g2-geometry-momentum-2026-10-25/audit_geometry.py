"""Independent physical-boundary/normal and source-DEM geometry audit."""
from pathlib import Path
import csv,hashlib,json,os,sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
OUT=ROOT/'results/uk_2d/g2-geometry-momentum-2026-10-25'
os.environ.setdefault('MPLCONFIGDIR',str(OUT/'.plot-cache'));os.environ.setdefault('XDG_CACHE_HOME',str(OUT/'.cache'))
import h5py,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as PolygonPath
from matplotlib.collections import LineCollection
from suites.uk_2d.sources import Raster

BASE=ROOT/'results/uk_2d/wall-assessment-2026-10-25/6a-cs0-none-cw0.01'
DEM=Path('/Users/calebbuahin/Downloads/UKBenchmarking/Benchmarking_Model_Data/Test6 dataset 2010/Test6ADEM.asc')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def simplify(p):
    while True:
        left=p-np.roll(p,1,axis=0);right=np.roll(p,-1,axis=0)-p
        cross=left[:,0]*right[:,1]-left[:,1]*right[:,0]
        keep=(abs(cross)>1e-7*np.linalg.norm(left,axis=1)*np.linalg.norm(right,axis=1))|(np.sum(left*right,axis=1)<=0)
        if keep.all():return p
        p=p[keep]

def signed_area(p):return float(.5*np.sum(p[:,0]*np.roll(p[:,1],-1)-p[:,1]*np.roll(p[:,0],-1)))

def main():
    with h5py.File(BASE/'surface.h5') as f:
        xyz=np.column_stack([f['Mesh2_node_x'][:],f['Mesh2_node_y'][:],f['Mesh2_node_z'][:]])
        c=f['Mesh2_face_nodes'][:]-int(f['Mesh2_face_nodes'].attrs.get('start_index',0))
        actual_n=np.stack([f['Mesh2_edge_nx'][:],f['Mesh2_edge_ny'][:]],axis=-1);actual_length=f['Mesh2_edge_length'][:]
    # Rebuild oriented edge ownership directly from the saved cell-node geometry.
    owners={};normal_error=0.;length_error=0.;norm_length_error=0.
    for cell,ids in enumerate(c):
        centre=xyz[ids,:2].mean(0)
        for edge in range(3):
            a,b=int(ids[(edge+1)%3]),int(ids[(edge+2)%3]);p,q=xyz[[a,b],:2];d=q-p;length=float(np.linalg.norm(d));n=np.array([d[1],-d[0]])/length
            assert np.dot(n,(p+q)/2-centre)>0
            normal_error=max(normal_error,float(np.max(abs(n-actual_n[cell,edge]))));length_error=max(length_error,abs(length-actual_length[cell,edge]));norm_length_error=max(norm_length_error,abs(float(np.linalg.norm(actual_n[cell,edge]))-1))
            owners.setdefault(tuple(sorted((a,b))),[]).append((cell,edge,a,b))
    boundary=[v[0] for v in owners.values() if len(v)==1];assert all(len(v) in [1,2] for v in owners.values())
    assignments=set();section=''
    for raw in (BASE/'model.inp').read_text().splitlines():
        row=raw.split(';')[0].split()
        if not row:continue
        if row[0].startswith('['):section=row[0];continue
        if section=='[2D_BOUNDARY_CONDITIONS]':assert row[2]=='WALL';assignments.add((int(row[0]),int(row[1])))
    assert assignments=={(cell,edge) for cell,edge,a,b in boundary}
    next_vertex={a:b for cell,edge,a,b in boundary};assert len(next_vertex)==len(boundary)
    unused=set(next_vertex);loops=[]
    while unused:
        start=min(unused);ids=[];v=start
        while v not in ids:ids.append(v);unused.remove(v);v=next_vertex[v]
        assert v==start;p=xyz[ids,:2];corners=simplify(p);loops.append(dict(ids=ids,corners=corners,signed_area=signed_area(p)))
    assert len(loops)==2
    obstacle=next(v for v in loops if v['signed_area']<0);outer=next(v for v in loops if v['signed_area']>0)
    p=obstacle['corners'];edges=np.roll(p,-1,axis=0)-p;lengths=np.linalg.norm(edges,axis=1);angles=np.degrees(np.arctan2(edges[:,1],edges[:,0]))%180
    assert len(p)==4 and np.allclose(np.sort(lengths),[.4,.4,.8,.8],rtol=0,atol=1e-9)
    assert np.allclose(angles[lengths>.6],64,rtol=0,atol=1e-7)
    assert np.min(np.linalg.norm(p-[3.44,-.05],axis=1))<1e-9
    obstacle_ids=set(obstacle['ids']);wall_records=[(cell,edge,a,b) for cell,edge,a,b in boundary if a in obstacle_ids and b in obstacle_ids]
    normal_sum=np.zeros(2);pressure_moment=np.zeros((2,2));normal_segments=[]
    for cell,edge,a,b in wall_records:
        mid=xyz[[a,b],:2].mean(0);normal=actual_n[cell,edge];length=actual_length[cell,edge]
        assert PolygonPath(p).contains_point(mid+normal*1e-4)
        normal_sum+=normal*length;pressure_moment+=np.outer(mid,normal)*length;normal_segments.append([mid,mid+.12*normal])
    gates=[]
    for pair,slots in owners.items():
        a,b=pair;xy=xyz[[a,b],:2]
        if np.all(abs(xy[:,0])<1e-10) and (abs(xy[:,1])<=.5+1e-10).all():
            assert len(slots)==2;gates.append(float(np.linalg.norm(xy[1]-xy[0])))
    assert abs(sum(gates)-1)<1e-9
    assert normal_error<1e-9 and length_error<1e-9
    assert np.allclose(pressure_moment,-.32*np.eye(2),atol=1e-9,rtol=0)
    dem=Raster(DEM.read_bytes());x=dem.x0+np.arange(dem.nx)*dem.dx;y=dem.y0+np.arange(dem.ny)*dem.dx;xx,yy=np.meshgrid(x,y)
    window=(xx>3)&(xx<4.6)&(abs(yy)<1.1);xy=np.column_stack([xx[window],yy[window]]);drawing=PolygonPath(p).contains_points(xy)
    thresholds=[]
    for level in [.02,.05,.1,.15,.4,1,5,9.99]:
        high=dem.z[window]>=level;thresholds.append(dict(water_level_m=level,blocked_pixel_area_m2=float(high.sum()*dem.dx**2),extra_pixel_centres=int((high&~drawing).sum()),missing_pixel_centres=int((~high&drawing).sum())))
    source_probes=DEM.with_name('Test6Aoutput.csv')
    supplied=list(csv.DictReader(source_probes.open()))
    executed=list(csv.DictReader((BASE/'probe-locations.csv').open()))
    assert [(r['Point ID'],float(r['X']),float(r['Y'])) for r in supplied]==[(r['id'],float(r['x']),float(r['y'])) for r in executed]
    probe_audit=dict(all_source_coordinates_match=True,source_sha256=sha(source_probes),G2_xy_m=[2.65,-.6])
    gate_rows=[]
    for station in [-.75,-.4,-.05,.05]:
        col=int(np.argmin(abs(x-station)))
        for level in [.02,.1,.4]:
            wet=(abs(y)<.8)&np.isfinite(dem.z[:,col])&(dem.z[:,col]<level)
            gate_rows.append(dict(requested_x_m=station,actual_pixel_x_m=float(x[col]),water_level_m=level,sample_y_window_m=[-.8,.8],section_kind='throat' if station<0 else 'post-gate truncated window',wet_pixel_count=int(wet.sum()),wet_pixel_width_m=float(wet.sum()*dem.dx),wet_pixel_min_y_m=float(y[wet].min()),wet_pixel_max_y_m=float(y[wet].max()),wet_pixel_midpoint_y_m=float((y[wet].min()+y[wet].max())/2)))
    col=int(np.argmin(abs(x-2)));bank=[]
    for side in [-1,1]:
        keep=(side*y>1.35)&(side*y<1.79)&np.isfinite(dem.z[:,col])&(dem.z[:,col]>.001)&(dem.z[:,col]<.16)
        slope,intercept=np.polyfit(abs(y[keep]),dem.z[keep,col],1)
        bank.append(dict(side='south' if side<0 else 'north',sample_x_m=float(x[col]),slope=float(slope),inferred_toe_abs_y_m=float(-intercept/slope),extrapolated_height_at_wall_m=float(slope*1.8+intercept)))
    record=dict(status='PASS',source_input_sha256=sha(BASE/'model.inp'),source_dem_sha256=sha(DEM),probe_audit=probe_audit,normal_checks=dict(max_component_error=normal_error,max_length_error_m=length_error,max_unit_length_error=norm_length_error,all_and_only_exterior_edges_are_walls=True,wall_slots=len(boundary),gate_is_internal=True,gate_open_width_m=sum(gates)),obstacle=dict(corners=p.tolist(),area_m2=-obstacle['signed_area'],side_lengths_m=lengths.tolist(),long_side_angles_from_x_deg=angles[lengths>.6].tolist(),outward_normals_point_into_solid=True,constant_pressure_normal_sum=normal_sum.tolist(),pressure_first_moment_m2=pressure_moment.tolist()),outer_boundary=dict(corners=outer['corners'].tolist(),enclosed_area_m2=outer['signed_area']),drawing_bank=dict(toe_abs_y_m=1.46,height_at_wall_m=.155),dem_bank_fits=bank,dem_gate_sections=gate_rows,dem_obstacle_thresholds=thresholds,qualification='Drawing dimensions and actual solver normals are independently verified. DEM threshold areas and widths are pixel-centre diagnostics, not a subpixel survey or proof of experimental geometry. No geometry was changed or fitted.')
    (OUT/'geometry-audit.json').write_text(json.dumps(record,indent=2)+'\n')
    fig,ax=plt.subplots(figsize=(9,6));mask=(x>3)&(x<4.6);rows=(abs(y)<1.1)
    art=ax.pcolormesh(x[mask],y[rows],np.minimum(dem.z[np.ix_(rows,mask)],.4),shading='nearest',vmin=0,vmax=.4,cmap='viridis');fig.colorbar(art,ax=ax,label='Source DEM elevation, clipped at 0.4 m')
    ring=np.vstack([p,p[0]]);ax.plot(ring[:,0],ring[:,1],'r-',lw=2,label='Executed drawing boundary');ax.add_collection(LineCollection(normal_segments,colors='white',linewidths=1));ax.plot(2.65,-.6,'wo',mec='black',label='G2');ax.set(xlim=(2.5,4.6),ylim=(-1.1,1.1),aspect='equal',xlabel='x (m)',ylabel='y (m)',title='Building footprint: source DEM and executed solid wall\nWhite segments show fluid-outward normals pointing into the building');ax.legend();fig.tight_layout();fig.savefig(OUT/'geometry-building-dem-and-normals.png',dpi=160);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(11,4.5))
    for ax,station in zip(axs,[-.4,2.]):
        col=int(np.argmin(abs(x-station)));ax.plot(y,dem.z[:,col],'o-',ms=3,label=f'DEM at x={x[col]:g} m')
        if station>0:ax.plot(y,.155/.34*np.maximum(abs(y)-1.46,0),'r--',label='Executed bank plane')
        ax.set(xlim=(-1.85,1.85),ylim=(-.01,.45),xlabel='y (m)',ylabel='Elevation (m)',title='Gate section' if station<0 else 'Bank cross-section');ax.grid(alpha=.25);ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(OUT/'geometry-gate-and-bank-sections.png',dpi=160);plt.close(fig)
    print(json.dumps(record,indent=2))

if __name__=='__main__':main()
