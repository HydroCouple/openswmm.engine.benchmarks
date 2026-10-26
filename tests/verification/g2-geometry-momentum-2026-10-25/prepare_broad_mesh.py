"""Preregistered broader .05 m GUI refinement, including reservoir and gate."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(R));os.chdir(R)
from suites.uk_2d import tin
import numpy as np
O=R/'results/uk_2d/g2-geometry-momentum-2026-10-25/broad-mesh';O.mkdir(exist_ok=False)
X=R/'tests/verification/g2-diagnosis-2026-10-25/mesher-build/uk_gui_mesher'
request=tin.geometry();request['min_cell_size']=.0125
request['refinement_boxes']=[dict(xmin=-7.55,xmax=8.,ymin=-1.8,ymax=1.8,max_area=float(np.sqrt(3)/4*.05**2),transition_width=2.)]
(O/'mesh-request.json').write_text(json.dumps(request,indent=2)+'\n')
with (O/'mesher.log').open('w') as f:subprocess.run([str(X),str(O/'mesh-request.json'),str(O/'mesh-output.json')],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1800)
v=json.loads((O/'mesh-output.json').read_text());xy=np.array(v['vertices']);xyz=np.column_stack([xy,tin.bed(xy)]);c=np.array(v['triangles'],int)
audit,walls=tin.audit(xyz,c,request);assert not v['stats']['refine_capped']
np.savez_compressed(O/'mesh.npz',vertices=xyz,cells=c)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
provenance=dict(request=request,audit=audit,stats=v['stats'],mesher_executable=str(X),mesher_sha256=sha(X),adapter_sha256=sha(R/'suites/uk_2d/mesher/main.cpp'),parent_gui_provenance=json.loads((R/'results/uk_2d/g2-jump-assessment-2026-10-25/local-mesh/mesh-provenance.json').read_text()),geometry='Exact drawing unchanged. Broad refinement covers reservoir, throat, gate and building. Not a formal convergence sequence.')
(O/'mesh-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');print(audit,flush=True)
