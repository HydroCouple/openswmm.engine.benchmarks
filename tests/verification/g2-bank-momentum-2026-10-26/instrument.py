"""Observational receipts on an isolated corrected-source copy; no product edits."""
from pathlib import Path
import difflib,hashlib,json,shutil
R=Path(__file__).resolve().parents[3];E=R.parent/'openswmm.engine';O=R/'results/uk_2d/g2-bank-momentum-2026-10-26';V=E/'tests/verification/g2_bank_momentum_2026-10-26';S=V/'source';F=E/'tests/verification/g2_reconstruction_2026-10-25/source'
V.mkdir(exist_ok=True);assert not S.exists();shutil.copytree(F,S)
p=S/'src/engine/2d/solver/ExplicitInertialSolver.cpp';before=p.read_text();s=before
header=r'''
// Diagnostic only: single-thread cumulative accepted-RK2 momentum receipts.
struct BankMomentumAudit {
 bool enabled=std::getenv("OPENSWMM_G2_MOMENTUM_AUDIT")!=nullptr;
 double weight=1,next=.1;
 std::ofstream out;
 std::vector<unsigned> mask;
 std::array<std::array<long double,26>,6> sums{};
 void begin(const MeshData& m,int threads,bool second,bool nonwall) {
  if(!enabled)return;
  if(threads!=1||nonwall)throw std::runtime_error("Audit requires one thread and all-WALL exterior");
  weight=second?.5:1;
  if(!mask.empty())return;
  out.open(std::getenv("OPENSWMM_G2_MOMENTUM_AUDIT"));
  if(!out)throw std::runtime_error("Cannot open audit");
  out<<std::setprecision(17)<<"time_s,cv,momentum_x,momentum_y,face_x,face_y,bed_x,bed_y,wall_flux_x,wall_flux_y,wall_bed_x,wall_bed_y,friction_x,friction_y,dry_x,dry_y,rk_final_dry_x,rk_final_dry_y,stage_delta_x,stage_delta_y,incoming_face_x,incoming_face_y,outgoing_face_x,outgoing_face_y,center_adv_x,center_adv_y,center_pressure_x,center_pressure_y,riemann_remainder_x,riemann_remainder_y\n";
  int gauge_count=0;
  for(int i=0;i<m.n_cells();++i){
   const double x=m.tri_cx[i],y=m.tri_cy[i];unsigned bits=1;
   if(x>=1.5&&x<=4.5)bits|=2;
   if(x>=2.2&&x<=3.5&&y>=-1.3&&y<=1.3)bits|=4;
   if(x>=-.8&&x<=1.5)bits|=8;
   if(x>=-7.55&&x<=8&&std::abs(y)>1.46)bits|=16;
   bool contains=true;
   for(int k=0;k<3;++k){int a=m.cell_vertex(i,k),b=m.cell_vertex(i,(k+1)%3);contains&=(m.vx[b]-m.vx[a])*(-.6-m.vy[a])-(m.vy[b]-m.vy[a])*(2.65-m.vx[a])>=-1e-12;}
   if(contains){bits|=32;++gauge_count;}mask.push_back(bits);
  }
  if(gauge_count!=1)throw std::runtime_error("Gauge cell is ambiguous");
 }
 void add(int i,int term,double x,double y){
  if(!enabled)return;
  for(int cv=0;cv<6;++cv)if(mask[i]&(1u<<cv)){sums[cv][term]+=weight*x;sums[cv][term+1]+=weight*y;}
 }
 void face(int a,int b,double mass,double fx,double fy,double ax,double ay,double px,double py,double dtL){
  if(!enabled)return;
  // Pair cancellation is exact inside a CV; sum only crossing-face transport.
  for(int cv=0;cv<6;++cv){int side=bool(mask[b]&(1u<<cv))-bool(mask[a]&(1u<<cv));if(!side)continue;
   const double w=side*weight*dtL;
   sums[cv][0]+=w*fx;sums[cv][1]+=w*fy;
   const int k=side*mass>=0?16:18;sums[cv][k]+=w*fx;sums[cv][k+1]+=w*fy;
   sums[cv][20]+=w*ax;sums[cv][21]+=w*ay;
   sums[cv][22]+=w*px;sums[cv][23]+=w*py;
   sums[cv][24]+=w*(fx-ax-px);sums[cv][25]+=w*(fy-ay-py);
  }
 }
 void end(double time,const MeshData& m,const std::vector<double>& qx,const std::vector<double>& qy){
  if(!enabled||time+1e-8<next)return;
  std::array<std::array<long double,2>,6> mom{};
  for(int i=0;i<m.n_cells();++i)for(int cv=0;cv<6;++cv)if(mask[i]&(1u<<cv)){mom[cv][0]+=m.tri_area[i]*qx[i];mom[cv][1]+=m.tri_area[i]*qy[i];}
  for(int cv=0;cv<6;++cv){out<<time<<','<<cv<<','<<mom[cv][0]<<','<<mom[cv][1];for(auto v:sums[cv])out<<','<<v;out<<'\n';}out.flush();next+=.1;
 }
};
BankMomentumAudit banka;
'''
s=s.replace('namespace openswmm::twoD {','#include <array>\n#include <fstream>\n#include <iomanip>\nnamespace openswmm::twoD {',1).replace('namespace {\n','namespace {\n'+header,1)
def patch(a,b):
 global s
 assert s.count(a)==1,(a[:90],s.count(a));s=s.replace(a,b,1)
patch('        bool wet;\n        if (so) {','        bool wet;\n        double audit_ax=0,audit_ay=0,audit_px=0,audit_py=0;\n        if (so) {')
a='''            wet = swe::faceFluxReconBed(etaLf, uLf, vLf, za, ha, etaRf, uRf, vRf, zb, hb, ed.nx[e],'''
b='''            if(banka.enabled){
                const double crest=std::max(etaLf-hLf,etaRf-hRf);
                const double hl=std::max(0.,etaLf-crest),hr=std::max(0.,etaRf-crest);
                const double ul=ha>dry?uLf:0.,vl=ha>dry?vLf:0.,ur=hb>dry?uRf:0.,vr=hb>dry?vRf:0.;
                const double unL=ul*ed.nx[e]+vl*ed.ny[e],unR=ur*ed.nx[e]+vr*ed.ny[e];
                audit_ax=.5*(hl*unL*ul+hr*unR*ur);audit_ay=.5*(hl*unL*vl+hr*unR*vr);
                const double pressure=.25*9.80665*(hl*hl+hr*hr);audit_px=pressure*ed.nx[e];audit_py=pressure*ed.ny[e];
            }
'''+a
patch(a,b)
patch('        double fh = F.mass * conv, fmx = F.mx * conv, fmy = F.my * conv;', '        double fh = F.mass * conv, fmx = F.mx * conv, fmy = F.my * conv;\n        double audit_scale=conv;')
# This sequence is unique in the full-SWE positivity pass.
patch('                fmy *= lam;','                fmy *= lam;\n                audit_scale*=lam;')
patch('        macc_x_L_[e] += (-fmx + cLx) * xdt;', '''        banka.face(a,b,fh,fmx,fmy,audit_ax*audit_scale,audit_ay*audit_scale,audit_px*audit_scale,audit_py*audit_scale,xdt);
        banka.add(a,2,cLx*xdt,cLy*xdt);banka.add(b,2,cRx*xdt,cRy*xdt);
        macc_x_L_[e] += (-fmx + cLx) * xdt;''')
patch("        // ONE walk of this cell's CSR row:","        const double audit_qx=kSwe&&banka.enabled?qcx_[i]:0.,audit_qy=kSwe&&banka.enabled?qcy_[i]:0.;\n        // ONE walk of this cell's CSR row:")
patch('                        dmx += (-F.mx + cLx) * xdt;', '''                        banka.add(i,4,-F.mx*xdt,-F.my*xdt);
                        banka.add(i,6,cLx*xdt,cLy*xdt);
                        dmx += (-F.mx + cLx) * xdt;''')
patch('                swe::frictionUpdate(qx, qy, h_new, mesh_->mannings_n[i], dt_c);', '''                const double audit_prex=qx,audit_prey=qy;
                swe::frictionUpdate(qx, qy, h_new, mesh_->mannings_n[i], dt_c);
                banka.add(i,8,A*(qx-audit_prex),A*(qy-audit_prey));''')
patch('''                qcx_[i] = 0.0;
                qcy_[i] = 0.0;
            }
        }
    }

    front_breach_''','''                banka.add(i,10,-A*audit_qx-dmx,-A*audit_qy-dmy);
                qcx_[i] = 0.0;
                qcy_[i] = 0.0;
            }
            banka.add(i,14,A*(qcx_[i]-audit_qx),A*(qcy_[i]-audit_qy));
        }
    }

    front_breach_''')
patch('''                if (state_->depth[i] <= opts_->dry_depth) {
                    qcx_[i] = 0.0;''','''                if (state_->depth[i] <= opts_->dry_depth) {
                    if(banka.enabled)banka.add(i,12,-mesh_->tri_area[i]*qcx_[i]/banka.weight,-mesh_->tri_area[i]*qcy_[i]/banka.weight);
                    qcx_[i] = 0.0;''')
patch('    if (second_order_) runRk2Step(dt, time);','    banka.begin(*mesh_,opts_->num_threads,second_order_,!bc_cell_.empty());\n    if (second_order_) runRk2Step(dt, time);')
patch('    applyMomentumPhysics(.5 * dt);\n    return dt;','    applyMomentumPhysics(.5 * dt);\n    banka.end(time+dt,*mesh_,qcx_,qcy_);\n    return dt;')
p.write_text(s)
(O/'momentum-receipts.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),s.splitlines(True),fromfile='original/ExplicitInertialSolver.cpp',tofile='audit/ExplicitInertialSolver.cpp')))
(O/'instrumentation.json').write_text(json.dumps(dict(source_copy=str(S),original_cpp_sha256=hashlib.sha256(before.encode()).hexdigest(),instrumented_cpp_sha256=hashlib.sha256(s.encode()).hexdigest(),qualification='Unqualified until enabled/disabled/frozen field identity checks; no product edit. Centered advective and pressure face terms are a defined diagnostic split, remainder includes Riemann upwinding and is not uniquely an energy dissipation.'),indent=2)+'\n')
print(S)
