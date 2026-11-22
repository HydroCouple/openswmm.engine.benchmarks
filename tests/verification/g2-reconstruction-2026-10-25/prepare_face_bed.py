"""Diagnostic isolation of velocity slopes and reconstructed versus actual face bed."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[3];V=R.parent/'openswmm.engine/tests/verification/g2_reconstruction_2026-10-25';O=R/'results/uk_2d/g2-reconstruction-2026-10-25';p=V/'source/src/engine/2d/solver/ExplicitInertialSolver.cpp';s=p.read_text(encoding='utf-8');(O/'solver-trace-before-face-bed.cpp').write_text(s,encoding='utf-8')
s=s.replace('''    const double dry=opts_->dry_depth;
#pragma omp parallel''','''    const double dry=opts_->dry_depth;
    static const bool zero_velocity=std::getenv("OPENSWMM_G2_ZERO_VELOCITY_SLOPES")!=nullptr;
#pragma omp parallel''',1)
s=s.replace('''        gvx_[i]=phi[2]*gx[2];gvy_[i]=phi[2]*gy[2];''','''        gvx_[i]=phi[2]*gx[2];gvy_[i]=phi[2]*gy[2];
        if(zero_velocity)gux_[i]=guy_[i]=gvx_[i]=gvy_[i]=0;''',1)
a='''            wet = swe::faceFluxReconBed(etaLf, uLf, vLf, za, ha, etaRf, uRf, vRf, zb, hb, ed.nx[e],
                                        ed.ny[e], dry, F, cLx, cLy, cRx, cRy, etaLf - hLf,
                                        etaRf - hRf);'''
b='''            static const bool fixed_bed=std::getenv("OPENSWMM_G2_FIXED_FACE_BED")!=nullptr;
            static const bool eta_source=std::getenv("OPENSWMM_G2_ETA_SOURCE")!=nullptr;
            const double edge_bed=.5*(ed.ze_lo[e]+ed.ze_hi[e]);
            const double zLf=fixed_bed?(ha>dry?edge_bed:za):etaLf-hLf;
            const double zRf=fixed_bed?(hb>dry?edge_bed:zb):etaRf-hRf;
            wet = swe::faceFluxReconBed(etaLf, uLf, vLf, za, ha, etaRf, uRf, vRf, zb, hb, ed.nx[e],
                                        ed.ny[e], dry, F, cLx, cLy, cRx, cRy, zLf,zRf,eta_source);'''
assert s.count(a)==1;s=s.replace(a,b)
a='''                        const double z=wall_eta0-wall_h0,zf=eta-hf;
                        wet=swe::faceFluxReconBed(eta,ux,uy,z,wall_h0,eta,ug,vg,z,wall_h0,
                            nx,ny,dry,F,cLx,cLy,cRx,cRy,zf,zf);'''
b='''                        const double z=wall_eta0-wall_h0;
                        double zf=eta-hf;
                        static const bool fixed_bed=std::getenv("OPENSWMM_G2_FIXED_FACE_BED")!=nullptr;
                        static const bool eta_source=std::getenv("OPENSWMM_G2_ETA_SOURCE")!=nullptr;
                        if(fixed_bed) {
                            int a,b;mesh_->cell_edge_vertices(i,MeshData::slot_local(slot),a,b);
                            zf=.5*(mesh_->vz[a]+mesh_->vz[b]);
                        }
                        wet=swe::faceFluxReconBed(eta,ux,uy,z,wall_h0,eta,ug,vg,z,wall_h0,
                            nx,ny,dry,F,cLx,cLy,cRx,cRy,zf,zf,eta_source);'''
assert s.count(a)==1;s=s.replace(a,b);p.write_text(s,encoding='utf-8')
k=V/'source/src/engine/2d/solver/SweKernels.hpp';t=k.read_text(encoding='utf-8');(O/'SweKernels-before-face-bed.hpp').write_text(t,encoding='utf-8')
a='''                                         double zLf, double zRf) noexcept {''';b='''                                         double zLf, double zRf, bool eta_source=false) noexcept {''';assert t.count(a)==1;t=t.replace(a,b)
a='''    const double cL = 0.5 * kGravity * (L.h * L.h - hLf * hLf - (hL_cell + hLf) * (zLf - zL));
    const double cR = 0.5 * kGravity * (R.h * R.h - hRf * hRf - (hR_cell + hRf) * (zRf - zR));'''
b='''    const double cL = 0.5 * kGravity * (eta_source ?
        L.h*L.h-hL_cell*hL_cell-(hL_cell+hLf)*(etaLf-(zL+hL_cell)) :
        L.h * L.h - hLf * hLf - (hL_cell + hLf) * (zLf - zL));
    const double cR = 0.5 * kGravity * (eta_source ?
        R.h*R.h-hR_cell*hR_cell-(hR_cell+hRf)*(etaRf-(zR+hR_cell)) :
        R.h * R.h - hRf * hRf - (hR_cell + hRf) * (zRf - zR));'''
assert t.count(a)==1;t=t.replace(a,b);k.write_text(t,encoding='utf-8')
(O/'face-bed-source.json').write_text(json.dumps(dict(solver_sha256=hashlib.sha256(s.encode()).hexdigest(),kernel_sha256=hashlib.sha256(t.encode()).hexdigest(),qualification='Experimental one-second stability controls only. Fixed bed means actual edge-midpoint terrain, with original mean-bed dry-side barrier. Eta-source form is algebraically equivalent when uncut face depth is nonnegative, and preserves hydrostatic balance if a true face lies above the water.'),indent=2)+'\n',encoding='utf-8')
