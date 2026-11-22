"""Copy frozen source and add observational momentum receipts, never product edits."""
from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parents[3]; E=R.parent/'openswmm.engine'; V=E/'tests/verification/g2_geometry_momentum_2026-10-25'; S=V/'audit-source'
source=E/'tests/verification/wall_friction_2026-10-24/commit-check-source'
assert not S.exists();V.mkdir(exist_ok=True);shutil.copytree(source,S)
p=S/'src/engine/2d/solver/ExplicitInertialSolver.cpp';before=p.read_text(encoding='utf-8');s=before
header=r'''
// Diagnostic-only, single-thread receipts for the frozen Test 6A experiment.
// Numerical face flux includes pressure, advection and numerical diffusion.
// All impulses are per density (m^4/s); second-order Euler stages weigh 1/2.
#include <array>
#include <fstream>
#include <iomanip>
struct G2MomentumAudit {
    bool enabled = std::getenv("OPENSWMM_G2_MOMENTUM_AUDIT") != nullptr;
    double weight=1, next=.1;
    std::ofstream out;
    std::vector<unsigned> mask;
    std::array<std::array<long double,16>,4> sums{};
    void begin(const MeshData& m, int threads, bool second, bool nonwall) {
        if (!enabled) return;
        if (threads!=1 || nonwall) throw std::runtime_error("Audit requires one thread and all-WALL boundaries");
        weight=second?.5:1;
        if (!mask.empty()) return;
        out.open(std::getenv("OPENSWMM_G2_MOMENTUM_AUDIT"));
        if (!out) throw std::runtime_error("Cannot open momentum audit");
        out<<std::setprecision(17)<<"time_s,cv,momentum_x,momentum_y,face_x,face_y,bed_x,bed_y,wall_x,wall_y,friction_x,friction_y,dry_x,dry_y,stage_delta_x,stage_delta_y,wall_begin_x,wall_begin_y,wall_difference_abs_x,wall_difference_abs_y\n";
        for(int i=0;i<m.n_cells();++i){
            double x=m.tri_cx[i], y=m.tri_cy[i]; unsigned v=1;
            if(x>=1.5 && x<=4.5) v|=2;
            if(x>=2.2 && x<=3.5 && y>=-1.3 && y<=1.3) v|=4;
            if(i==19081) v|=8;
            mask.push_back(v);
        }
    }
    void add(int i,int term,double x,double y) {
        if(!enabled) return;
        for(int c=0;c<4;++c) if(mask[i]&(1u<<c)) {
            sums[c][term]+=weight*x; sums[c][term+1]+=weight*y;
        }
    }
    void end(double time,const MeshData& m,const std::vector<double>& qx,const std::vector<double>& qy) {
        if(!enabled || time+1e-8<next) return;
        std::array<std::array<long double,2>,4> mom{};
        for(int i=0;i<m.n_cells();++i) for(int c=0;c<4;++c) if(mask[i]&(1u<<c)) {
            mom[c][0]+=m.tri_area[i]*qx[i]; mom[c][1]+=m.tri_area[i]*qy[i];
        }
        for(int c=0;c<4;++c) {out<<time<<','<<c<<','<<mom[c][0]<<','<<mom[c][1];for(auto v:sums[c])out<<','<<v;out<<'\n';}
        out.flush();next+=.1;
    }
};
G2MomentumAudit g2audit;
'''
# Standard-library includes must be outside the namespace.
s=s.replace('namespace openswmm::twoD {','#include <array>\n#include <fstream>\n#include <iomanip>\n\nnamespace openswmm::twoD {',1)
header=header.replace('#include <array>\n#include <fstream>\n#include <iomanip>\n','')
s=s.replace('namespace {\n','namespace {\n'+header,1)
def patch(a,b):
 global s
 assert s.count(a)==1,(a[:100],s.count(a));s=s.replace(a,b,1)
patch('        macc_x_L_[e] += (-fmx + cLx) * xdt;', '''        g2audit.add(a,0,-fmx*xdt,-fmy*xdt);
        g2audit.add(b,0, fmx*xdt, fmy*xdt);
        g2audit.add(a,2,cLx*xdt,cLy*xdt);
        g2audit.add(b,2,cRx*xdt,cRy*xdt);
        macc_x_L_[e] += (-fmx + cLx) * xdt;''')
patch('        // ONE walk of this cell\'s CSR row:', '''        const double audit_qx = swe && g2audit.enabled ? qcx_[i] : 0.;
        const double audit_qy = swe && g2audit.enabled ? qcy_[i] : 0.;
        const double audit_h = swe && g2audit.enabled ? state_->depth[i] : 0.;
        const double audit_eta = swe && g2audit.enabled ? state_->head[i] : 0.;
        // ONE walk of this cell's CSR row:''')
patch('            if (h_new > dry) {\n                // WALL slots', '''            if (g2audit.enabled && audit_h > dry) {
                for (int w=wall_ptr_[i];w<wall_ptr_[i+1];++w) {
                    const int slot=wall_slot_[w];
                    const double nx=mesh_->edge_nx[slot],ny=mesh_->edge_ny[slot];
                    const double ux=audit_qx/audit_h,uy=audit_qy/audit_h;
                    const double un=ux*nx+uy*ny,ut=-ux*ny+uy*nx;
                    swe::FaceFlux F; double a,b,c,d;
                    if(swe::faceFlux(audit_eta,audit_h,audit_qx,audit_qy,audit_eta,audit_h,
                        audit_h*(-un*nx-ut*ny),audit_h*(-un*ny+ut*nx),nx,ny,dry,F,a,b,c,d))
                        g2audit.add(i,12,(-F.mx+a)*mesh_->edge_length[slot]*dt_c,(-F.my+b)*mesh_->edge_length[slot]*dt_c);
                }
            }
            if (h_new > dry) {
                // WALL slots''')
patch('                        dmx += (-F.mx + cLx) * xdt;', '''                        g2audit.add(i,4,(-F.mx+cLx)*xdt,(-F.my+cLy)*xdt);
                        if(g2audit.enabled) {
                            swe::FaceFlux B{}; double a=0,b=0,c=0,d=0;
                            if(audit_h>dry) {
                                const double un0=(audit_qx*nx+audit_qy*ny)/audit_h;
                                const double ut0=(-audit_qx*ny+audit_qy*nx)/audit_h;
                                swe::faceFlux(audit_eta,audit_h,audit_qx,audit_qy,audit_eta,audit_h,
                                    audit_h*(-un0*nx-ut0*ny),audit_h*(-un0*ny+ut0*nx),nx,ny,dry,B,a,b,c,d);
                            }
                            g2audit.add(i,14,std::abs((-F.mx+cLx)-(-B.mx+a))*xdt,std::abs((-F.my+cLy)-(-B.my+b))*xdt);
                        }
                        dmx += (-F.mx + cLx) * xdt;''')
patch('                swe::frictionUpdate(qx, qy, h_new, mesh_->mannings_n[i], dt_c);', '''                const double audit_prex=qx,audit_prey=qy;
                swe::frictionUpdate(qx, qy, h_new, mesh_->mannings_n[i], dt_c);
                g2audit.add(i,6,A*(qx-audit_prex),A*(qy-audit_prey));''')
patch('                qcx_[i] = 0.0;\n                qcy_[i] = 0.0;\n            }\n        }\n    }\n\n    front_breach_', '''                g2audit.add(i,8,-A*audit_qx-dmx,-A*audit_qy-dmy);
                qcx_[i] = 0.0;
                qcy_[i] = 0.0;
            }
            g2audit.add(i,10,A*(qcx_[i]-audit_qx),A*(qcy_[i]-audit_qy));
        }
    }

    front_breach_''')
patch('    if (second_order_) runRk2Step(dt, time);', '''    g2audit.begin(*mesh_,opts_->num_threads,second_order_,!bc_cell_.empty());
    if (second_order_) runRk2Step(dt, time);''')
patch('    applyMomentumPhysics(.5 * dt);\n    return dt;', '''    applyMomentumPhysics(.5 * dt);
    g2audit.end(time+dt,*mesh_,qcx_,qcy_);
    return dt;''')
p.write_text(s,encoding='utf-8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(Path(__file__).parent/'instrumentation.json').write_text(json.dumps(dict(source=str(source),original_solver_sha256=hashlib.sha256(before.encode()).hexdigest(),audit_solver_sha256=sha(p),source_copy=str(S),qualification='Diagnostic receipts only; no scientific interpretation before enabled/disabled and frozen equivalence checks.'),indent=2)+'\n',encoding='utf-8')
print(S)
