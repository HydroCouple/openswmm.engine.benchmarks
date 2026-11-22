"""Retain v1, then account explicitly for the existing final RK2 dry reset."""
from pathlib import Path
import difflib,hashlib,json,shutil
R=Path(__file__).resolve().parents[3];O=R/'results/uk_2d/g2-geometry-momentum-2026-10-25';E=R.parent/'openswmm.engine';S=E/'tests/verification/g2_geometry_momentum_2026-10-25/audit-source';B=S.parent/'audit-build'
old=O/'incomplete-euler-only-ledger';old.mkdir(exist_ok=False)
for n in ['momentum-audit.json','instrumentation-equivalence.json','momentum-receipts.patch','instrumentation-source.json']:shutil.copy2(O/n,old/n)
for src,dst in [(B/'src/cli/openswmm',old/'openswmm'),(B/'src/engine/libopenswmm.engine.6.0.0.dylib',old/'libopenswmm.engine.6.0.0.dylib')]:shutil.copy2(src,dst)
p=S/'src/engine/2d/solver/ExplicitInertialSolver.cpp';s=p.read_text(encoding='utf-8');(old/'ExplicitInertialSolver.cpp').write_text(s,encoding='utf-8')
s=s.replace('std::array<long double,16>','std::array<long double,18>')
s=s.replace('wall_difference_abs_y\\n"','wall_difference_abs_y,rk_final_dry_x,rk_final_dry_y\\n"')
a='''                if (state_->depth[i] <= opts_->dry_depth) {
                    qcx_[i] = 0.0;'''
b='''                if (state_->depth[i] <= opts_->dry_depth) {
                    if (g2audit.enabled)
                        g2audit.add(i,16,-mesh_->tri_area[i]*qcx_[i]/g2audit.weight,
                            -mesh_->tri_area[i]*qcy_[i]/g2audit.weight);
                    qcx_[i] = 0.0;'''
assert s.count(a)==1;s=s.replace(a,b);p.write_text(s,encoding='utf-8')
f='src/engine/2d/solver/ExplicitInertialSolver.cpp';base=E/'tests/verification/wall_friction_2026-10-24/commit-check-source'/f
(O/'momentum-receipts.patch').write_text(''.join(difflib.unified_diff(base.read_text(encoding='utf-8').splitlines(True),s.splitlines(True),fromfile='a/'+f,tofile='b/'+f)),encoding='utf-8')
info=json.loads((O/'instrumentation-source.json').read_text(encoding='utf-8'));info['audit_solver_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();info['amendment']='Explicit final RK2 dry-momentum reset receipt; physical equations unchanged. V1 missing-receipt record retained.';(O/'instrumentation-source.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
(old/'rejection.json').write_text(json.dumps(dict(reason='Euler-stage receipts omitted the final accepted RK2 dry reset. This is incomplete diagnostic instrumentation, not a solver-physics failure.',max_unaccounted_momentum_m4_s=.00010756115826726642,action='Add the exact existing final-reset receipt, retain all old results, require amended-enabled fields to match original enabled fields bit for bit.'),indent=2)+'\n',encoding='utf-8')
print('Amended receipts only')
