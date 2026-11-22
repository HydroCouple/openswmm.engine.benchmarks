"""Measure realised mesh resolution, rather than equating target size with edges."""
from pathlib import Path
import json,os
R=Path(__file__).resolve().parents[3];os.chdir(R)
import h5py,numpy as np
O=R/'results/uk_2d/g2-geometry-momentum-2026-10-25'
records={}
for name,p in [('control',O.parent/'wall-assessment-2026-10-25/6a-cs0-none-cw0.01/surface.h5'),('previous-local',O.parent/'g2-jump-assessment-2026-10-25/local005/surface.h5'),('broad',O/'broad-mesh/mesh.npz')]:
 if p.suffix=='.h5':
  with h5py.File(p) as f:v=np.column_stack([f['Mesh2_node_x'][:],f['Mesh2_node_y'][:]]);c=f['Mesh2_face_nodes'][:]-int(f['Mesh2_face_nodes'].attrs.get('start_index',0))
 else:z=np.load(p);v=z['vertices'][:,:2];c=z['cells']
 pts=v[c];centre=pts.mean(1);edges=np.linalg.norm(pts-np.roll(pts,-1,axis=1),axis=2);result={}
 for region,mask in [('reservoir',centre[:,0]<-.8),('throat',(centre[:,0]>=-.8)&(centre[:,0]<0)),('building',(centre[:,0]>1.5)&(centre[:,0]<5)&(abs(centre[:,1])<1.2))]:
  result[region]=dict(cells=int(mask.sum()),median_edge_m=float(np.median(edges[mask])),p95_edge_m=float(np.quantile(edges[mask],.95)))
 records[name]=result
(O/'mesh-resolution.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8');print(json.dumps(records,indent=2))
