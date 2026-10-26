"""Seal a portable website evidence package after scientific/visual review."""
from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parents[3];O=R/'results/uk_2d/g2-geometry-momentum-2026-10-25';V=Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert json.loads((O/'momentum-audit.json').read_text())['status']=='PASS'
assert json.loads((O/'instrumentation-equivalence.json').read_text())['status']=='PASS'
old=O.parent/'g2-jump-assessment-2026-10-25/local005';thin=O/'previous-local';thin.mkdir(exist_ok=True)
for name in ['model.inp','case.json','manifest.json','metrics.json','probes.csv','probe-locations.csv','probe-map.json','volume.csv','mesh-provenance.json','status.json']:shutil.copy2(old/name,thin/name)
shutil.copytree(old/'reference',thin/'reference',dirs_exist_ok=True)
original=O/'original120';original.mkdir(exist_ok=True)
base=O.parent/'wall-assessment-2026-10-25/6a-cs0-none-cw0.01'
for n in ['model.inp','manifest.json','case.json','metrics.json']:shutil.copy2(base/n,original/n)
source=O/'verification-source';source.mkdir(exist_ok=True)
for p in V.glob('*.py'):shutil.copy2(p,source/p.name)
files=set()
for n in ['audit-design.json','gate-clock-followup.json','linear-reconstruction-audit.json','geometry-audit.json','momentum-audit.json','instrumentation-equivalence.json','mesh-resolution.json','instrumentation-source.json','momentum-receipts.patch','configure.log','build.log','build-v2.log','audit-build-revisions.json','summary.json','interpretation.json','review.json','report-provenance.json','report.html','front-positions.csv','G2-state-20s.json']:files.add(n)
provenance=json.loads((O/'report-provenance.json').read_text());files.update(provenance['figures'])
cases=['frozen30','audit-disabled','audit-enabled','audit-enabled-v2','order1-30','muscl-off-30','broad005-30','broad005-muscloff-30','previous-local']
for case in cases:
 w=O/case;assert json.loads((w/'status.json').read_text())['state']=='COMPLETE'
 manifest=json.loads((w/'manifest.json').read_text());assert sha(w/'model.inp')==manifest['input_sha256']
 for n in ['model.inp','case.json','manifest.json','metrics.json','probes.csv','probe-locations.csv','probe-map.json','volume.csv','status.json','driver.py','mesh-provenance.json','momentum-ledger.csv']:
  if (w/n).exists():files.add(case+'/'+n)
 files.update(str(p.relative_to(O)) for p in (w/'reference').rglob('*') if p.is_file())
files.update(str(p.relative_to(O)) for p in source.glob('*.py'))
files.update('original120/'+n for n in ['model.inp','manifest.json','case.json','metrics.json'])
files.update(['incomplete-euler-only-ledger/rejection.json','incomplete-euler-only-ledger/momentum-audit.json','incomplete-euler-only-ledger/momentum-receipts.patch','incomplete-euler-only-ledger/check_momentum.py'])
files.update(['broad-mesh/mesh-request.json','broad-mesh/mesh-provenance.json'])
(O/'publication-manifest.json').write_text(json.dumps(dict(duration_s=30,qualification='diagnostic',cases=cases,files={n:sha(O/n) for n in sorted(files)}),indent=2)+'\n')
print('Sealed',len(files),'reviewed artifacts; raw HDF fields remain local.')
