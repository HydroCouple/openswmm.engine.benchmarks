"""Depth-gradient front geometry and normal-flow diagnostics; no measured spatial reference."""
from pathlib import Path
import argparse,csv,json,os
import h5py,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.tri as tri
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[3];O=R/'results/uk_2d/g2-bank-momentum-2026-10-26'
G=9.80665


def locate(xs,ys,depth):
    step=float(xs[1]-xs[0]);sigma=.02/step;radius=int(round(4*sigma));k=np.arange(-radius,radius+1)
    kernel=np.exp(-.5*(k/sigma)**2);kernel/=kernel.sum()
    smooth=np.array([np.convolve(np.pad(row,radius,mode='edge'),kernel,mode='valid') for row in depth])
    dx=np.gradient(smooth,step,axis=1);inside=(xs>=2.2)&(xs<=3.5)
    index=np.where(inside)[0][np.argmax(dx[:,inside],axis=1)];peak=dx[np.arange(len(ys)),index];xp=xs[index]
    good=(peak>.05)&(xp>2.225)&(xp<3.475)
    if good.sum()<10:return None
    coef=np.polyfit(ys[good]+.6,xp[good],1);residual=xp-(coef[0]*(ys+.6)+coef[1]);good&=abs(residual)<.08
    if good.sum()<10:return None
    slope,intercept=np.polyfit(ys[good]+.6,xp[good],1)
    rms=np.sqrt(np.mean((xp[good]-(slope*(ys[good]+.6)+intercept))**2))
    return slope,intercept,rms,xp,good

def inspect(name,path):
 assert json.loads((path/'status.json').read_text())['state']=='COMPLETE'
 rows=[]
 with h5py.File(path/'surface.h5') as f:
  c=f['Mesh2_face_nodes'][:].astype(int)-int(f['Mesh2_face_nodes'].attrs.get('start_index',0));x=f['Mesh2_node_x'][:];y=f['Mesh2_node_y'][:]
  finder=tri.Triangulation(x,y,c).get_trifinder();xs=np.arange(2.,3.65001,.005);ys=np.arange(-.8,-.3999,.01);xx,yy=np.meshgrid(xs,ys);cell=finder(xx,yy);assert (cell>=0).all()
  times=np.round((f['time'][:]-46023)*86400,1)
  for t in np.arange(5.,30.001,.5):
   frame=int(np.argmin(abs(times-t)));assert abs(times[frame]-t)<1e-8
   h=f['Mesh2_face_depth'][frame];u=f['Mesh2_face_vx'][frame];v=f['Mesh2_face_vy'][frame]
   depth=h[cell]; fit=locate(xs,ys,depth)
   if fit is None:
    rows.append(dict(time_s=float(t),valid=False,reason='Insufficient interior depth-gradient peaks or retained fit rows'));continue
   slope,intercept,rms,xp,good=fit;nx=1/np.sqrt(1+slope*slope);ny=-slope*nx
   row=dict(time_s=float(t),valid=True,front_x_at_G2_y_m=float(intercept),dx_dy=float(slope),normal_x=float(nx),normal_y=float(ny),fit_rms_m=float(rms),rows_used=int(good.sum()))
   for side,sign in [('up',-1),('down',1)]:
    # Average over a short band parallel to the fitted front, at fixed normal distance.
    tangent=np.linspace(-.04,.04,9);px=intercept+sign*.10*nx-tangent*ny;py=-.6+sign*.10*ny+tangent*nx;ids=finder(px,py)
    if (ids<0).any():row['valid']=False;row['reason']='Sampling band outside fluid';break
    dh=float(np.mean(h[ids]));uu=float(np.mean(u[ids]));vv=float(np.mean(v[ids]));un=uu*nx+vv*ny;ut=-uu*ny+vv*nx
    row.update({side+'_depth_m':dh,side+'_u_mps':uu,side+'_v_mps':vv,side+'_un_mps':un,side+'_ut_mps':ut,side+'_normal_Fr_stationary':abs(un)/np.sqrt(G*dh)})
   rows.append(row)
   if t==20:
    fig,ax=plt.subplots(figsize=(10,3.4),layout='constrained');art=ax.pcolormesh(xx,yy,depth,shading='auto',vmin=0,vmax=.16,cmap='viridis');ax.plot(xp[good],ys[good],'w.',label='Detected depth-gradient ridge');ax.plot(slope*(ys+.6)+intercept,ys,'r-',label='Local front fit');ax.plot(2.65,-.6,'kx',ms=10,label='G2');ax.arrow(intercept,-.6,.18*nx,.18*ny,color='red',width=.003,head_width=.025,length_includes_head=True);ax.plot([intercept-.1*nx,intercept+.1*nx],[-.6-.1*ny,-.6+.1*ny],'ro',mfc='none');ax.set(xlabel='x (m)',ylabel='y (m)',title=name+': depth-gradient front and sampling normal at 20 s',aspect='equal');ax.legend(loc='upper left',fontsize=8);fig.colorbar(art,ax=ax,label='Depth (m)');fig.savefig(O/(name+'-front-20s.png'),dpi=160);plt.close(fig)
  # Fit-local normal speed uses central temporal differences only where adjacent fits exist.
  for i in range(1,len(rows)-1):
   a,b,d=rows[i-1:i+2]
   if not all(r.get('valid') for r in [a,b,d]):continue
   speed=(d['front_x_at_G2_y_m']-a['front_x_at_G2_y_m'])/(d['time_s']-a['time_s'])*b['normal_x'];b['front_normal_speed_mps']=speed
   for side in ['up','down']:
    h=b[side+'_depth_m'];un=b[side+'_un_mps']-speed;ut=b[side+'_ut_mps'];b[side+'_relative_normal_Fr']=abs(un)/np.sqrt(G*h);b[side+'_relative_mass_m2ps']=h*un;b[side+'_relative_normal_momentum_m3ps2']=h*un*un+.5*G*h*h;b[side+'_relative_specific_energy_m']=h+(un*un+ut*ut)/(2*G)
   b['relative_specific_energy_drop_m']=b['up_relative_specific_energy_m']-b['down_relative_specific_energy_m']
 (O/(name+'-front.json')).write_text(json.dumps(dict(method='Cell-constant depth sampled on .005m grid; Gaussian derivative smoothing sigma .02m; largest rising depth gradient x[2.2,3.5] per y[-.8,-.4]. Robust line rejects >.08m residual; >=10 rows, slope>.05m/m. Normal states average a .08m tangent band at +/- .10m. Diagnostic orientation/speed, not a measured shock map or exact Rankine-Hugoniot test. Centered differences give front speed; tangential flow and unsteadiness can violate 1D jump assumptions.',rows=rows),indent=2,allow_nan=False)+'\n')
 return rows
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('name');ap.add_argument('path',type=Path);a=ap.parse_args();rows=inspect(a.name,a.path);print(json.dumps(next(r for r in rows if r['time_s']==20),indent=2))
