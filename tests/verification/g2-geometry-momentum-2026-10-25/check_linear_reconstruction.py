"""Independent constant/linear patch audit of the frozen fully-wet gradient formula.
Boundary and shoreline cells are excluded from linear consistency conclusions.
No hydraulic solution, roughness or observed marker is used by this check.
"""
from pathlib import Path
import hashlib,json,os
R=Path(__file__).resolve().parents[3];os.chdir(R)
import h5py,numpy as np
O=R/'results/uk_2d/g2-geometry-momentum-2026-10-25'
records={}
os.environ.setdefault('MPLCONFIGDIR',str(O/'.plot-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.tri import Triangulation
fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
for name in ['control','broad']:
 if name=='control':
  with h5py.File(O.parent/'wall-assessment-2026-10-25/6a-cs0-none-cw0.01/surface.h5') as f:v=np.column_stack([f['Mesh2_node_x'][:],f['Mesh2_node_y'][:],f['Mesh2_node_z'][:]]);c=f['Mesh2_face_nodes'][:]-int(f['Mesh2_face_nodes'].attrs.get('start_index',0))
 else:z=np.load(O/'broad-mesh/mesh.npz');v=z['vertices'];c=z['cells']
 pts=v[c];centres=pts.mean(1);a=.5*np.sum(pts[:,:,0]*np.roll(pts[:,:,1],-1,axis=1)-pts[:,:,1]*np.roll(pts[:,:,0],-1,axis=1),axis=1)
 nei=np.full((len(c),3),-1,int);owners={};normals=np.zeros((len(c),3,2));mid=np.zeros_like(normals)
 for cell,row in enumerate(c):
  for slot in range(3):
   i,j=int(row[(slot+1)%3]),int(row[(slot+2)%3]);d=v[j,:2]-v[i,:2];normals[cell,slot]=[d[1],-d[0]];mid[cell,slot]=.5*(v[i,:2]+v[j,:2]);key=tuple(sorted((i,j)))
   if key in owners:
    other,edge=owners.pop(key);nei[cell,slot]=other;nei[other,edge]=cell
   else:owners[key]=(cell,slot)
 # Surface integral approximation: arithmetic average of cell/neighbour samples.
 values=centres[:,:2];safe=np.where(nei>=0,nei,np.arange(len(c))[:,None]);face=.5*(values[:,None,:]+values[safe]);grad=np.einsum('nsm,nsd->nmd',face,normals)/a[:,None,None]
 const=np.sum(normals,axis=1)/a[:,None]
 arms=mid-centres[:,None,:2];delta=np.einsum('nmd,nsd->nsm',grad,arms)
 lo=np.minimum(values,np.min(values[safe],axis=1));hi=np.maximum(values,np.max(values[safe],axis=1));phi=np.ones((len(c),2))
 for slot in range(3):
  d=delta[:,slot,:];positive=d>1e-14;negative=d< -1e-14;ratio=np.ones_like(d);np.divide(hi-values,d,out=ratio,where=positive);np.divide(lo-values,d,out=ratio,where=negative);phi=np.minimum(phi,ratio)
 limited=grad*phi[:,:,None];error=np.linalg.norm(grad-np.eye(2),axis=(1,2));limitederror=np.linalg.norm(limited-np.eye(2),axis=(1,2))
 interior=(nei>=0).all(1)&(abs(centres[:,2])<1e-12)&(abs(centres[safe,2])<1e-12).all(1)
 zones={}
 for zone,mask in [('fully_interior_flat',interior),('building_reach_interior_flat',interior&(centres[:,0]>1.5)&(centres[:,0]<4.5)&(abs(centres[:,1])<1.2))]:
  zones[zone]=dict(cells=int(mask.sum()),unlimited_gradient_identity_error=dict(median=float(np.median(error[mask])),p95=float(np.quantile(error[mask],.95)),maximum=float(error[mask].max())),limited_gradient_identity_error=dict(median=float(np.median(limitederror[mask])),p95=float(np.quantile(limitederror[mask],.95)),maximum=float(limitederror[mask].max())),fraction_unlimited_error_above_1_percent=float(np.mean(error[mask]>.01)))
 ax=axes[0 if name=='control' else 1];tri=Triangulation(v[:,0],v[:,1],c);art=ax.tripcolor(tri,facecolors=np.where(interior,error,np.nan),vmin=0,vmax=.5,cmap='magma',rasterized=True);p=np.array(json.loads((O/'geometry-audit.json').read_text(encoding='utf-8'))['obstacle']['corners']);ax.fill(p[:,0],p[:,1],color='.65',edgecolor='black');ax.plot(2.65,-.6,'wo',mec='black');ax.set(xlim=(1.5,4.5),ylim=(-1.2,1.2),aspect='equal',title=name+' TIN: fully interior flat cells',xlabel='x (m)',ylabel='y (m)')
 g2=19081 if name=='control' else None
 records[name]=dict(constant_gradient_max_abs=float(abs(const).max()),zones=zones,G2_cell_unlimited_gradient_matrix=grad[g2].tolist() if g2 is not None else None,G2_cell_neighbours=nei[g2].tolist() if g2 is not None else None)
fig.colorbar(art,ax=list(axes),label='Linear-gradient error (Frobenius norm)',shrink=.8);fig.suptitle('Offline linear-field patch audit of frozen Green–Gauss formula\nBoundary/shoreline cells excluded; G2 shown in white');fig.savefig(O/'linear-reconstruction-patch.png',dpi=150,bbox_inches='tight');plt.close(fig)
source=R.parent/'openswmm.engine/tests/verification/wall_friction_2026-10-24/commit-check-source/src/engine/2d/solver/ExplicitInertialSolver.cpp'
result=dict(source_solver_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),status='COMPLETED',definition='For analytic scalar fields w=x and w=y, exact gradient matrix is identity. Errors are Frobenius norms, dimensionless.',scope='Offline reproduction of frozen fully-wet arithmetic Green-Gauss face samples and BJ scalar limiter on actual TIN geometry. No boundary or shoreline cells are scored. This identifies linear-consistency limitations, not proof of the G2 cause or qualification of a replacement reconstruction.',meshes=records)
(O/'linear-reconstruction-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
