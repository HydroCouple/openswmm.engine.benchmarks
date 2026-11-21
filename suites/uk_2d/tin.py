"""Test 6 PSLG, GUI mesher adapter and independent topology/geometry audit."""
from __future__ import annotations
import json
import argparse
from pathlib import Path
import subprocess
import numpy as np
from .sources import digest


def geometry():
    """Meters, transcribed from EA2DTest6 May 2010 Figure (a)."""
    angle=np.deg2rad(64.)
    along=np.array([np.cos(angle),np.sin(angle)])
    across=np.array([along[1],-along[0]])
    b1=np.array([3.44,-.05])  # 1.75 m above the -1.8 m wall
    building=np.array([b1,b1+.4*across,b1+.4*across+.8*along,b1+.8*along])
    domain=[[-7.55,-1.8],[-.8,-1.8],[-.8,-.5],[0,-.5],[0,-1.8],
            [91.45,-1.8],[91.45,1.8],[0,1.8],[0,.5],[-.8,.5],[-.8,1.8],[-7.55,1.8]]
    constraints=[dict(marker=10,tag='building-wall',points=np.vstack([building,building[0]]).tolist()),
                 dict(marker=20,tag='initial-depth-interface-NOT-a-wall',points=[[0,-.5],[0,.5]])]
    for y in [-1.46,1.46]:  # 0.34 m-wide bank slopes, 0.155 m high
        for a,b in [(-7.55,-.8),(0,91.45)]:
            constraints.append(dict(marker=30,tag='bank-toe-NOT-a-wall',points=[[a,y],[b,y]]))
    return dict(domain=domain,constraints=constraints,holes=[building.mean(0).tolist()],
                max_area=float(np.sqrt(3)/4*.1**2),min_cell_size=.025)


def bed(xy):
    """Piecewise planar cross-section from the source drawing, not raster walls."""
    return .155/.34*np.maximum(np.abs(np.asarray(xy)[:,1])-1.46,0.)


def areas(vertices,cells):
    p=vertices[cells,:2]
    return .5*np.sum(p[:,:,0]*np.roll(p[:,:,1],-1,axis=1)-p[:,:,1]*np.roll(p[:,:,0],-1,axis=1),axis=1)


def audit(vertices,cells,request):
    """Audit area, excluded obstacles, all required segments and connected topology."""
    from matplotlib.path import Path as PolygonPath
    if vertices.ndim!=2 or vertices.shape[1]!=3 or cells.ndim!=2 or cells.shape[1]!=3:
        raise ValueError('Expected XYZ vertices and triangles')
    if not np.isfinite(vertices).all() or cells.min()<0 or cells.max()>=len(vertices):raise ValueError('Invalid mesh arrays')
    if len(np.unique(cells))!=len(vertices):raise ValueError('Unused vertices')
    if not np.allclose(vertices[:,2],bed(vertices),rtol=0,atol=1e-10):raise ValueError('Bed differs from cross-section')
    xy=vertices[:,:2];p=xy[cells];centres=p.mean(1)
    a=areas(vertices,cells)
    if not np.all(a>1e-12):raise ValueError('Nonpositive triangle area')
    if not np.isclose(a.sum(),354.,rtol=0,atol=1e-7):raise ValueError('Flume-minus-obstacles area differs from drawing')
    # Independent centroid exclusions; constraint coverage below also rules out crossing cells.
    if not PolygonPath(request['domain']).contains_points(centres).all():raise ValueError('Triangle outside flume')
    building=np.array(request['constraints'][0]['points'])
    if PolygonPath(building).contains_points(centres).any():raise ValueError('Triangle inside building')
    if np.any((p[:,:,0].min(1)<-1e-8)&(p[:,:,0].max(1)>1e-8)):raise ValueError('Cell crosses initial depth interface')
    edges={}
    for ci,c in enumerate(cells):
        for slot in range(3):
            key=tuple(sorted((int(c[(slot+1)%3]),int(c[(slot+2)%3]))))
            edges.setdefault(key,[]).append((ci,slot))
    if any(len(v)>2 for v in edges.values()):raise ValueError('Nonmanifold mesh')
    endpoints=np.array(list(edges));owners=list(edges.values());counts=np.array([len(v) for v in owners])
    ep=xy[endpoints]
    segments=[('domain-wall',True,request['domain']+[request['domain'][0]])]
    segments += [(s['tag'],s['marker']==10,s['points']) for s in request['constraints']]
    coverage=[];wall_keys=set()
    for tag,wall,path in segments:
        for start,end in zip(path,path[1:]):
            start,end=np.array(start),np.array(end);d=end-start;length=np.linalg.norm(d)
            cross=d[0]*(ep[:,:,1]-start[1])-d[1]*(ep[:,:,0]-start[0])
            t=np.sum((ep-start)*d,axis=2)/length**2
            on=(np.abs(cross)<1e-8).all(1)&(t>=-1e-8).all(1)&(t<=1+1e-8).all(1)
            covered=np.linalg.norm(ep[on,1]-ep[on,0],axis=1).sum()
            if not np.isclose(covered,length,rtol=0,atol=1e-7):raise ValueError('Missing constrained segment: '+tag)
            if np.any(counts[on]!=(1 if wall else 2)):raise ValueError('Wrong wall/internal connectivity: '+tag)
            if wall:wall_keys.update(map(tuple,endpoints[on]))
            coverage.append(dict(tag=tag,length_m=float(length),covered_m=float(covered),wall=wall))
    actual_walls={tuple(k) for k in endpoints[counts==1]}
    if actual_walls!=wall_keys:raise ValueError('Unexplained exterior edge')
    # Euler characteristic for one connected component with one building hole.
    if len(xy)-len(edges)+len(cells)!=0:raise ValueError('Unexpected holes/components')
    lengths=np.linalg.norm(p-np.roll(p,-1,axis=1),axis=2)
    angles=np.rad2deg(np.arccos(np.clip((np.roll(lengths,1,axis=1)**2+lengths**2-
                                      np.roll(lengths,-1,axis=1)**2)/(2*np.roll(lengths,1,axis=1)*lengths),-1,1)))
    walls=[(*v[0],float(np.linalg.norm(xy[list(k)][1]-xy[list(k)][0]))) for k,v in edges.items() if len(v)==1]
    return dict(vertex_count=len(vertices),triangle_count=len(cells),area_m2=float(a.sum()),
                min_angle_deg=float(angles.min()),max_triangle_area_m2=float(a.max()),
                min_edge_m=float(lengths.min()),max_edge_m=float(lengths.max()),
                wall_edge_count=len(walls),constraints=coverage),walls


def generate(exe,gui_source,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    request=geometry();(output/'mesh-request.json').write_text(json.dumps(request,indent=2)+'\n', encoding='utf-8')
    process=subprocess.run([str(Path(exe).resolve()),str(output/'mesh-request.json'),str(output/'mesh-output.json')],
                           capture_output=True,text=True,timeout=600)
    (output/'mesher.log').write_text(process.stdout+'\n'+process.stderr, encoding='utf-8')
    process.check_returncode()
    result=json.loads((output/'mesh-output.json').read_text(encoding='utf-8'))
    xy=np.array(result['vertices']);vertices=np.column_stack([xy,bed(xy)])
    cells=np.array(result['triangles'],dtype=int)
    review,walls=audit(vertices,cells,request)
    gui_source=Path(gui_source)
    files=sorted((gui_source/'include/mesh').glob('*.h'))+sorted((gui_source/'src/mesh').glob('*.cpp'))
    files += [gui_source/'src/core/editgeometry.cpp',gui_source/'include/core/editgeometry.h',
              gui_source/'vendor/predicates/predicates.c',gui_source/'vendor/predicates/predicates.h']
    provenance=dict(generator='openswmm.gui mesh::MeshGenerator / ConstrainedDelaunay',
        generator_executable_sha256=digest(Path(exe).read_bytes()),
        gui_source_hashes={str(p.relative_to(gui_source)):digest(p.read_bytes()) for p in files},
        adapter_hashes={p.name:digest(p.read_bytes()) for p in [Path(__file__),Path(__file__).with_name('mesher')/'main.cpp',Path(__file__).with_name('mesher')/'CMakeLists.txt']},
        vertices_sha256=digest(vertices.tobytes()),cells_sha256=digest(cells.tobytes()),geometry_request=request,
        request_sha256=digest((output/'mesh-request.json').read_bytes()),stats=result['stats'],audit=review,
        geometry_source='EA2DTest6 - May2010.pdf, Figure (a); exact dimensioned straight boundaries and planar bank slopes',
        interpretation='Drawing geometry is used rather than fitting pixelated DEM barrier transitions. Initial values are depths, as specified, not uniform water-surface elevations. The 6B vertical interpretation must be explicitly selected when its deck is built; no dynamic similarity claim.')
    (output/'mesh-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n', encoding='utf-8')
    np.savez_compressed(output/'mesh.npz',vertices=vertices,cells=cells)
    return vertices,cells,provenance


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--gui-source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    _,_,record=generate(args.exe,args.gui_source,args.output)
    print(json.dumps(record['audit'],indent=2))
