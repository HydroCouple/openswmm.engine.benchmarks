"""Exact planar geometry diagnostic on completed Test 6 fields, not a flux ledger."""
from pathlib import Path
import csv,json
import h5py
import numpy as np
R=Path(__file__).resolve().parents[3]
O=R/'results/uk_2d/g2-partial-wet-2026-10-26'
P=R/'results/uk_2d/g2-reconstruction-2026-10-25/clean-combined-120'
def moments(eta,za,zb,k):
    ha=np.maximum(eta-np.minimum(za,zb),0); hb=np.maximum(eta-np.maximum(za,zb),0)
    delta=np.abs(zb-za)
    return np.divide(ha**(k+1)-hb**(k+1),(k+1)*delta,out=np.array(ha**k,copy=True),where=delta>1e-14)
def mean_depth(eta,z):
    lo,mi,hi=np.sort(z,axis=1).T
    ans=np.maximum(eta-z.mean(axis=1),0)
    ans[eta<=lo]=0
    low=(eta>lo)&(eta<hi)&(eta<=mi)
    high=(eta>lo)&(eta<hi)&(eta>mi)
    ans[low]=(eta[low]-lo[low])**3/(3*(mi[low]-lo[low])*(hi[low]-lo[low]))
    ans[high]=eta[high]-z[high].mean(axis=1)+(hi[high]-eta[high])**3/(3*(hi[high]-lo[high])*(hi[high]-mi[high]))
    return ans

def main():
    assert json.loads((P/'status.json').read_text())['state']=='COMPLETE'
    rows=[];edges=[]
    with h5py.File(P/'surface.h5') as f:
        conn=f['Mesh2_face_nodes'][:].astype(int)-int(f['Mesh2_face_nodes'].attrs.get('start_index',0))
        xyz=np.column_stack([f['Mesh2_node_'+d][:] for d in 'xyz']); xyzc=xyz[conn]
        area=f['Mesh2_face_area'][:];x=f['Mesh2_face_x'][:];y=f['Mesh2_face_y'][:];bed=f['Mesh2_face_z'][:]
        ea=conn[:,[1,2,0]];eb=conn[:,[2,0,1]]
        key=np.sort(np.stack([ea.ravel(),eb.ravel()],axis=1),axis=1)
        _,inv,count=np.unique(key,axis=0,return_inverse=True,return_counts=True)
        wall=(count[inv]==1).reshape(ea.shape)
        za=xyz[ea,2];zb=xyz[eb,2];length=f['Mesh2_edge_length'][:]
        mx=(xyz[ea,0]+xyz[eb,0])/2;my=(xyz[ea,1]+xyz[eb,1])/2
        groups={'all':wall,'gate_shoulders':wall&(abs(mx)<1e-7),'building':wall&(mx>3)&(mx<5),'outer_sides':wall&(abs(abs(my)-1.8)<1e-7),'upstream_end':wall&(abs(mx+7.55)<1e-7),'downstream_end':wall&(abs(mx-91.45)<1e-7)}
        regions={'whole_domain':np.ones(len(x),bool),'reservoir':x<0,'gate_to_building':(x>=0)&(x<=5),'G2_neighborhood':(x>=2)&(x<=3.3),'near_field':(x>=0)&(x<=8)}
        raw_times=f['time'][:];times=np.round((raw_times-np.floor(raw_times[0]))*86400,1)
        for t in [0,.1,1,5,10,20,30,120]:
            if t==0: h=np.where(x<0,.4,.02);eta=bed+h
            else:
                i=int(np.argmin(abs(times-t)));assert abs(times[i]-t)<1e-7
                h=f['Mesh2_face_depth'][i];eta=f['Mesh2_face_head'][i]
            exact=mean_depth(eta,xyzc[:,:,2]);partial=(eta>xyzc[:,:,2].min(axis=1))&(eta<xyzc[:,:,2].max(axis=1))
            for name,region in regions.items():
                mask=region&(h>.0001)
                rows.append(dict(time_s=t,region=name,cells=int(region.sum()),wet_cells=int(mask.sum()),partially_wet_cells=int((partial&mask).sum()),solver_wet_volume_m3=float(area[mask]@h[mask]),planar_wet_volume_at_saved_head_m3=float(area[mask]@exact[mask]),planar_minus_solver_m3=float(area[mask]@(exact[mask]-h[mask])),excluded_dry_volume_m3=float(area[region&~mask]@h[region&~mask])))
            et=np.where(h>.0001,eta,xyzc[:,:,2].min(axis=1)-1)[:,None];lo=np.minimum(za,zb);hi=np.maximum(za,zb)
            frac=np.divide(et-lo,hi-lo,out=np.where(et>lo,1.,0.),where=hi-lo>1e-14).clip(0,1)
            pressure=.5*9.80665*length*moments(et,za,zb,2)
            midpoint=.5*9.80665*length*np.maximum(et-(za+zb)/2,0)**2
            for name,mask in groups.items():
                edges.append(dict(time_s=t,region=name,wall_edges=int(mask.sum()),partially_wet_edges=int((mask&(frac>0)&(frac<1)).sum()),wetted_length_m=float((length*frac)[mask].sum()),physical_pressure_integral_over_rho_m4ps2=float(pressure[mask].sum()),midpoint_pressure_integral_over_rho_m4ps2=float(midpoint[mask].sum()),exact_minus_midpoint_m4ps2=float((pressure-midpoint)[mask].sum())))
        np.savez_compressed(O/'geometry-snapshot.npz',vertices=xyz,triangles=conn,head=f['Mesh2_face_head'][int(np.argmin(abs(times-20)))],partial=partial)
    for name,data in [('storage.csv',rows),('walls.csv',edges)]:
        with (O/name).open('w',newline='') as handle:
            w=csv.DictWriter(handle,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    (O/'geometry-scope.json').write_text(json.dumps(dict(scope='Only cells with mean depth > 0.0001 m contribute; dry-cell head has no water-surface interpretation. Exact planar geometry at saved cell head; no reconstructed solver-face state or momentum source is inferred. Pressure is divided by density. Scalar pressure sums are quadrature diagnostics, not net forces. Volume difference is a change of geometric interpretation at fixed head, not a conservation error.',input=str(P/'surface.h5'),times_s=[0,.1,1,5,10,20,30,120]),indent=2)+'\n')
if __name__=='__main__':main()
