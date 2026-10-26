"""One-second fixed-physics controls to isolate the initial bank instability."""
from pathlib import Path
import concurrent.futures as cf,hashlib,json,os,re,subprocess
R=Path(__file__).resolve().parents[3];V=R.parent/'openswmm.engine/tests/verification/g2_reconstruction_2026-10-25';O=R/'results/uk_2d/g2-reconstruction-2026-10-25';X=O/'pinned-clean/bin/openswmm';LIB=O/'pinned-clean/engine/libopenswmm.engine.6.0.0.dylib'
import h5py,numpy as np
variants={'clean-equivalence':{},'integration-equivalence':{},'prototype-equivalence':{'OPENSWMM_G2_VERTEX_VELOCITY_LIMITER':'1'}}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def run(item):
 name,flags=item;P=O/('pinned-integration' if name.startswith('integration') else 'pinned-vertex-init' if name.startswith('prototype') else 'pinned-clean');X=P/'bin/openswmm';LIB=P/'engine/libopenswmm.engine.6.0.0.dylib';W=O/('stability-'+name);W.mkdir(exist_ok=False);text=(O/'combined/model.inp').read_text();text=re.sub(r'^END_TIME\s+.*$','END_TIME 00:00:01',text,flags=re.M);(W/'model.inp').write_text(text)
 env=os.environ.copy();env['DYLD_LIBRARY_PATH']=str(LIB.parent);env['OMP_NUM_THREADS']='1'
 for k in list(env):
  if k.startswith('OPENSWMM_G2_') or k=='OPENSWMM_2D_MUSCL_OFF':env.pop(k,None)
 env.update(flags);identity=dict(executable_sha256=sha(X),library_sha256=sha(LIB),flags=flags,input_sha256=sha(W/'model.inp'),purpose='Numerical stability only, no observed comparison');(W/'manifest.json').write_text(json.dumps(identity,indent=2)+'\n')
 with (W/'process.log').open('w') as f:
  try:r=subprocess.run([str(X),str(W/'model.inp'),str(W/'model.rpt'),str(W/'model.out')],cwd=W,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=120);code=r.returncode
  except subprocess.TimeoutExpired:code='TIMEOUT'
 result=dict(name=name,returncode=code,completed=False)
 if code==0:
  with h5py.File(W/'surface.h5') as f:
   result['frames']=len(f['time']);h=f['Mesh2_face_depth'][:];u=f['Mesh2_face_vx'][:];v=f['Mesh2_face_vy'][:];a=f['Mesh2_face_area'][:];z=f['Mesh2_face_z'][:];cx=f['Mesh2_face_x'][:];h0=np.where(cx<0,.4,.02);initial=float(a@h0);energy0=float(a@(9.80665*(.5*h0*h0+z*h0)));kinetic=.5*h*(u*u+v*v);energy=(kinetic+9.80665*(.5*h*h+z*h))@a
   result.update(completed=result['frames']==10,finite=bool(np.isfinite(h).all() and np.isfinite(u).all() and np.isfinite(v).all()),minimum_depth=float(h.min()),max_speed=float(np.max(np.hypot(u,v))),max_energy_ratio=float(np.max(energy)/energy0),max_volume_relative_error=float(np.max(abs(h@a-initial))/initial))
 assert sha(X)==identity['executable_sha256'] and sha(LIB)==identity['library_sha256']
 (W/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(result,flush=True);return result
with cf.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(run,variants.items()))
(O/'equivalence-stability.json').write_text(json.dumps(rows,indent=2)+'\n')
