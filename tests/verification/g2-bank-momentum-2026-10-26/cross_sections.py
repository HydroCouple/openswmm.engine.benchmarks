"""Independent stage-area curves for the exact planar bed and cell-centred surrogate."""
from pathlib import Path
import csv,json,sys
import h5py,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[3];O=R/'results/uk_2d/g2-bank-momentum-2026-10-26'
sys.path.insert(0,str(R/'tests/verification/g2-partial-wet-2026-10-26'))
from geometry import mean_depth

def getmesh(name):
 if name.startswith('bank'):
  a=np.load(O/name/'mesh/mesh.npz');return a['vertices'],a['cells']
 folder=R/'results/uk_2d/g2-reconstruction-2026-10-25'/('clean-combined' if name=='coarse' else 'clean-broad005-30')
 with h5py.File(folder/'surface.h5') as f:return np.column_stack([f['Mesh2_node_'+s][:] for s in 'xyz']),f['Mesh2_face_nodes'][:].astype(int)-int(f['Mesh2_face_nodes'].attrs.get('start_index',0))

def main():
 rows=[];resolution=[];volumes=[]
 for name in ['coarse','bank005','bank0025','broad005']:
  v,c=getmesh(name);p=v[c];mid=p.mean(axis=1);area=.5*abs((p[:,1,0]-p[:,0,0])*(p[:,2,1]-p[:,0,1])-(p[:,1,1]-p[:,0,1])*(p[:,2,0]-p[:,0,0]));relief=np.ptp(p[:,:,2],axis=1)
  for region,mask in [('target_banks',(abs(mid[:,1])>1.46)&(mid[:,0]<=8)),('G2_flat',(mid[:,0]>=2)&(mid[:,0]<=3.3)&(abs(mid[:,1])<1.3)),('far_field',mid[:,0]>10)]:
   edge=np.sqrt(np.sum(np.diff(np.concatenate([p[:,:,:2],p[:,:1,:2]],axis=1),axis=1)**2,axis=2))
   resolution.append(dict(case=name,region=region,cells=int(mask.sum()),median_edge_m=float(np.median(edge[mask])),bed_relief_p95_m=float(np.percentile(relief[mask],95))))
  for level in [.005,.01,.02,.04,.06,.1,.155,.2,.4]:
   eta=np.full(len(c),level);exact=mean_depth(eta,p[:,:,2]);flat=np.maximum(eta-mid[:,2],0)
   near=(mid[:,0]>=0)&(mid[:,0]<=8)
   volumes.append(dict(case=name,stage_m=level,region='x0_to8',exact_planar_volume_m3=float(area[near]@exact[near]),flat_volume_m3=float(area[near]@flat[near])))
  for station in [-5.,-.4,.1,2.65,3.2,5.]:
   eligible=(p[:,:,0].min(axis=1)<station)&(p[:,:,0].max(axis=1)>station);width=[];bed=[]
   for poly,z in zip(p[eligible],mid[eligible,2]):
    ys=[]
    for a,b in zip(poly,np.roll(poly,-1,axis=0)):
     if (a[0]<=station<b[0]) or (b[0]<=station<a[0]):ys.append(a[1]+(station-a[0])/(b[0]-a[0])*(b[1]-a[1]))
    if len(ys)==2:width.append(abs(ys[1]-ys[0]));bed.append(z)
   width=np.array(width);bed=np.array(bed);assert abs(width.sum()-(1 if station==-.4 else 3.6))<1e-8
   for level in [.005,.01,.02,.04,.06,.1,.155,.2,.4]:
    exact=level if station==-.4 else 2.92*level+(level*level/(.155/.34) if level<=.155 else .68*(level-.155/2))
    flat=float(width@np.maximum(level-bed,0));rows.append(dict(case=name,x_m=station,stage_m=level,exact_area_m2=exact,flat_area_m2=flat,relative_area_error_pct=100*(flat-exact)/exact))
 for filename,data in [('cross-sections.csv',rows),('mesh-resolution.csv',resolution),('stage-volumes.csv',volumes)]:
  with (O/filename).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 fig,axs=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
 for name in ['coarse','bank005','bank0025','broad005']:
  sub=[r for r in rows if r['case']==name and r['x_m']==2.65];axs[0].plot([r['stage_m'] for r in sub],[r['relative_area_error_pct'] for r in sub],'o-',label=name)
  sub=[r for r in rows if r['case']==name and r['stage_m']==.02];axs[1].plot([r['x_m'] for r in sub],[r['relative_area_error_pct'] for r in sub],'o-',label=name)
 axs[0].set(xlabel='Uniform stage (m)',ylabel='Cell-centred cross-section area error (%)',title='Cross-section at G2, x=2.65 m',xlim=(0,.2));axs[1].set(xlabel='Cross-section station x (m)',ylabel='Cell-centred cross-section area error (%)',title='Stage 0.02 m');axs[0].legend(fontsize=9);axs[1].legend(fontsize=9);fig.savefig(O/'cross-section-errors.png',dpi=160);plt.close(fig)
 print(json.dumps([r for r in rows if r['x_m']==2.65 and r['stage_m']==.02],indent=2))
if __name__=='__main__':main()
