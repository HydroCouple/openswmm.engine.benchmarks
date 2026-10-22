"""Geometry-aware face probes and bounded field extraction."""
from __future__ import annotations
import csv
import json
from pathlib import Path
import numpy as np


def locate_probes(vertices, cells, probes):
    """Containing convex polygon; deterministic lowest-index tie on a face."""
    result=[]
    for probe in probes:
        p=np.array([float(probe['x']),float(probe['y'])])
        hits=[]
        for i,cell in enumerate(cells):
            poly=vertices[np.array(cell)[np.array(cell)>=0],:2]
            a=poly; b=np.roll(poly,-1,axis=0)
            cross=(b[:,0]-a[:,0])*(p[1]-a[:,1])-(b[:,1]-a[:,1])*(p[0]-a[:,0])
            if np.all(cross>=-1e-8) or np.all(cross<=1e-8):hits.append(i)
        if not hits:raise ValueError(f'Probe {probe["id"]} is outside active mesh')
        result.append(dict(id=probe['id'],x=float(p[0]),y=float(p[1]),face=min(hits),
                           boundary_tie=len(hits)>1,operator='containing_face_constant_lowest_index_tie'))
    return result


def extract(h5, case, probes, output):
    import h5py
    output=Path(output)
    with h5py.File(h5,'r') as f:
        times=np.asarray(f['time'])
        units=f['time'].attrs.get('units',b'')
        units=units.decode() if isinstance(units,bytes) else str(units)
        if units=='days since 1899-12-30 00:00:00':
            import datetime as dt
            origin=(dt.datetime(2026,1,1)-dt.datetime(1899,12,30)).days
            times=(times-origin)*86400
        elif units!='seconds since 2026-01-01 00:00:00':
            raise ValueError('Unrecognized output time units: '+units)
        clock_tolerance=min(.02,case['step']*.05)
        if not np.isfinite(times).all() or len(times)<2 or np.any(np.diff(times)<=0):
            raise ValueError('Invalid output time axis')
        if not np.isclose(times[-1],case['end'],atol=clock_tolerance,rtol=0):
            raise ValueError(f'Incomplete run: last output {times[-1]}, expected {case["end"]}')
        # t=0 is not guaranteed by the writer; subsequent output must be complete.
        expected=np.arange(case['step'],case['end']+case['step']/2,case['step'])
        if len(times)!=len(expected) or not np.allclose(times,expected,atol=clock_tolerance,rtol=0):
            raise ValueError('Missing or misaligned required output times')
        clock_error=float(np.max(abs(times-expected)))
        times=expected
        verts=np.column_stack([f['Mesh2_node_x'][:],f['Mesh2_node_y'][:]])
        conn=f['Mesh2_face_nodes'][:]
        conn=conn-int(f['Mesh2_face_nodes'].attrs.get('start_index',0))
        located=locate_probes(verts,conn,probes)
        (output/'probe-map.json').write_text(json.dumps(located,indent=2)+'\n', encoding='utf-8')
        z=f['Mesh2_face_z'][:]; area=f['Mesh2_face_area'][:]
        if len(z)!=case['cell_count'] or not np.isclose(area.sum(),case['area_m2'],rtol=1e-8):
            raise ValueError('Output mesh differs from case geometry')
        minimum=float('inf'); volumes=[]; values=[]
        max_depth=np.zeros(len(z));max_speed=np.zeros(len(z))
        with (output/'probes.csv').open('w',newline='', encoding='utf-8') as stream:
            writer=csv.writer(stream);writer.writerow(['time_s','probe','depth_m','level_m','speed_mps','vx_mps','vy_mps'])
            for i,t in enumerate(times):
                h=np.asarray(f['Mesh2_face_depth'][i]);u=np.asarray(f['Mesh2_face_vx'][i]);v=np.asarray(f['Mesh2_face_vy'][i])
                if not all(np.isfinite(a).all() for a in [h,u,v]):raise ValueError('NaN/Inf in fields')
                minimum=min(minimum,float(h.min()));speed=np.hypot(u,v)
                volumes.append(float(np.dot(area,h)))
                max_depth=np.maximum(max_depth,h);max_speed=np.maximum(max_speed,speed)
                row=[]
                for probe in located:
                    c=probe['face']; row.extend([float(h[c]),float(z[c]+h[c]),float(speed[c])])
                    writer.writerow([f'{t:.12g}',probe['id'],h[c],z[c]+h[c],speed[c],u[c],v[c]])
                values.append(row)
        ledger={}
        group=f.get('mass_balance_2d')
        if group is not None:
            ledger={k:float(v) for k,v in group.attrs.items() if np.asarray(v).size==1 and np.issubdtype(np.asarray(v).dtype,np.number)}
            for k in group:
                if group[k].size==1:ledger[k]=float(np.asarray(group[k]).item())
        if not ledger:raise ValueError('Missing 2D conservation ledger')
        snapshots={}
        requests=([1800,3600,7200,10800,14400] if case['uk_test']=='4' else
                  [1,2,3,4,5,10,15,20,25,30] if case['uk_test']=='6a' else
                  [60,120,180,240,300,600,900,1200] if case['uk_test']=='6b' else [])
        for t in requests:
            i=int(np.argmin(abs(times-t)))
            if abs(times[i]-t)>1e-5:raise ValueError(f'Missing snapshot at {t}')
            snapshots[f'depth_{t}s']=f['Mesh2_face_depth'][i]
            snapshots[f'speed_{t}s']=np.hypot(f['Mesh2_face_vx'][i],f['Mesh2_face_vy'][i])
        # Writer envelopes are cumulative at output updates, not independently
        # established internal-step extrema. Label sampled maxima explicitly.
        np.savez_compressed(output/'fields.npz',x=f['Mesh2_face_x'][:],y=f['Mesh2_face_y'][:],z=z,area=area,
                            vertices=verts,cells=conn,max_depth=max_depth,max_speed=max_speed,
                            final_depth=h,**snapshots)
    with (output/'volume.csv').open('w',newline='', encoding='utf-8') as stream:
        writer=csv.writer(stream);writer.writerow(['time_s','volume_m3']);writer.writerows(zip(times,volumes))
    return dict(times=times,values=np.asarray(values),minimum_depth_m=minimum,final_volume_m3=volumes[-1],ledger=ledger,
                peak_scope='maxima over saved output times',probe_map=located,clock_rounding_max_s=clock_error)
