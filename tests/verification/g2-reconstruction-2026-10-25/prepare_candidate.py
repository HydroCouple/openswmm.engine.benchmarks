"""Isolated native corrections; diagnostic switches never enter product defaults."""
from pathlib import Path
import difflib,hashlib,json
B=Path(__file__).resolve().parents[3];E=B.parent/'openswmm.engine';V=E/'tests/verification/g2_reconstruction_2026-10-25';S=V/'source';O=B/'results/uk_2d/g2-reconstruction-2026-10-25'
p=S/'src/engine/2d/solver/ExplicitInertialSolver.cpp';original=p.read_text(encoding='utf-8');s=original
start=s.index('void ExplicitInertialSolver::computeLimitedGradientsSwe()');end=s.index('\n/**',start);old=s[start:end].rstrip()
new=r'''void ExplicitInertialSolver::computeLimitedGradientsSwe() {
    const auto n=state_->depth.size();
    const auto& ed=edges_;
    const double dry=opts_->dry_depth;
#pragma omp parallel for schedule(static) num_threads(opts_->num_threads)
    for(int k=0;k<int(active_cells_.size());++k) {
        const int i=active_cells_[k];
        gex_[n+i]=gey_[n+i]=gex_[i]=gey_[i]=gux_[i]=guy_[i]=gvx_[i]=gvy_[i]=0;
        const double hi=state_->depth[i];
        if(hi<=10*dry)continue;
        const double wi[4]={state_->head[i],qcx_[i]/hi,qcy_[i]/hi,hi};
        double lo[4]={wi[0],wi[1],wi[2],wi[3]},hiw[4]={wi[0],wi[1],wi[2],wi[3]};
        double xx=0,xy=0,yy=0,bx[4]={},by[4]={};
        unsigned connected=0;int count=0;bool shore=false;
        const int begin=ed.cell_ptr[i],end=ed.cell_ptr[i+1];
        for(int p=begin;p<end;++p) {
            const int e=ed.cell_edge[p],j=ed.cL[e]==i?ed.cR[e]:ed.cL[e];
            const double hj=state_->depth[j],ej=state_->head[j];
            const double sill=std::max(wi[0]-hi,ej-hj);
            if(hj<=dry||!cell_active_[j]||wi[0]-sill<=dry||ej-sill<=dry) {shore=true;continue;}
            connected|=1u<<(p-begin);++count;
            const double dx=mesh_->tri_cx[j]-mesh_->tri_cx[i],dy=mesh_->tri_cy[j]-mesh_->tri_cy[i];
            const double wt=1/(dx*dx+dy*dy);
            xx+=wt*dx*dx;xy+=wt*dx*dy;yy+=wt*dy*dy;
            const double wj[4]={ej,qcx_[j]/hj,qcy_[j]/hj,hj};
            for(int m=0;m<4;++m) {
                bx[m]+=wt*dx*(wj[m]-wi[m]);by[m]+=wt*dy*(wj[m]-wi[m]);
                lo[m]=std::min(lo[m],wj[m]);hiw[m]=std::max(hiw[m],wj[m]);
            }
        }
        if(count<2)continue;
        const double det=xx*yy-xy*xy;
        // Retain the existing shoreline conditioning bound (condition number <98).
        if(det<=1e-2*(xx+yy)*(xx+yy))continue;
        double gx[4]={},gy[4]={},phi[4]={1,1,1,1};
        for(int m=0;m<4;++m) {
            if(shore&&(m==1||m==2))continue;
            gx[m]=(yy*bx[m]-xy*by[m])/det;gy[m]=(xx*by[m]-xy*bx[m])/det;
        }
        // Keep the existing scalar BJ bounds, dry-sill exclusion and shoreline
        // velocity fallback. Only the fully-wet geometric gradient changes.
        for(int p=begin;p<end;++p) {
            if(!(connected&(1u<<(p-begin))))continue;
            for(int m=0;m<4;++m) {
                const double wf=wi[m]+gx[m]*ed.cell_arm_x[p]+gy[m]*ed.cell_arm_y[p];
                phi[m]=std::min(phi[m],swe::bjLimiter(wi[m],wf,lo[m],hiw[m]));
            }
        }
        const int nvc=mesh_->cell_vertex_count(i);
        if(count<nvc) {
            double positive=1;
            for(int e=0;e<nvc;++e) {
                const int a=mesh_->cell_vertex(i,e),b=mesh_->cell_vertex(i,(e+1)%nvc);
                const double ax=.5*(mesh_->vx[a]+mesh_->vx[b])-mesh_->tri_cx[i];
                const double ay=.5*(mesh_->vy[a]+mesh_->vy[b])-mesh_->tri_cy[i];
                const double dh=phi[3]*(gx[3]*ax+gy[3]*ay);
                if(dh < -hi)positive=std::min(positive,-hi/dh);
            }
            phi[0]*=positive;phi[3]*=positive;
        }
        gex_[i]=phi[0]*gx[0];gey_[i]=phi[0]*gy[0];
        gex_[n+i]=phi[3]*gx[3];gey_[n+i]=phi[3]*gy[3];
        gux_[i]=phi[1]*gx[1];guy_[i]=phi[1]*gy[1];
        gvx_[i]=phi[2]*gx[2];gvy_[i]=phi[2]*gy[2];
    }
}'''
(O/'gradient-correction.cpp').write_text(new+'\n',encoding='utf-8')
wrapped='''void ExplicitInertialSolver::computeLimitedGradientsSwe() {
    static const bool legacy=std::getenv("OPENSWMM_G2_LEGACY_GRADIENT")!=nullptr;
    if(legacy) {\n'''+old[old.index('{')+1:old.rfind('}')]+'''\n    } else {\n'''+new[new.index('{')+1:new.rfind('}')]+'''\n    }\n}'''
s=s[:start]+wrapped+'\n'+s[end:]
# Snapshot this cell before the interior volume update; its momentum is still
# beginning-of-stage until the later momentum gather/friction assignment.
needle='''        // ONE walk of this cell's CSR row:'''
assert s.count(needle)==1
s=s.replace(needle,'''        const double wall_h0=kSwe?state_->depth[i]:0;
        const double wall_eta0=kSwe?state_->head[i]:0;
'''+needle)
a=s.index('            // WALL boundary faces (every boundary slot');b=s.index('            if (h_new > dry) {\n                double qx',a)
oldwall=s[a:b]
wall=r'''            if(wall_h0>dry) {
                static const bool muscl_off=std::getenv("OPENSWMM_2D_MUSCL_OFF")!=nullptr;
                const bool so=second_order_&&!muscl_off;
                for(int w=wall_ptr_[i];w<wall_ptr_[i+1];++w) {
                    const int slot=wall_slot_[w];
                    const double nx=mesh_->edge_nx[slot],ny=mesh_->edge_ny[slot];
                    double eta=wall_eta0,hf=wall_h0,ux=qcx_[i]/wall_h0,uy=qcy_[i]/wall_h0;
                    if(so) {
                        const double ax=mesh_->edge_mx[slot]-mesh_->tri_cx[i];
                        const double ay=mesh_->edge_my[slot]-mesh_->tri_cy[i];
                        const auto n=state_->depth.size();
                        eta+=gex_[i]*ax+gey_[i]*ay;
                        hf=std::max(0.,hf+gex_[n+i]*ax+gey_[n+i]*ay);
                        ux+=gux_[i]*ax+guy_[i]*ay;uy+=gvx_[i]*ax+gvy_[i]*ay;
                    }
                    const double un=ux*nx+uy*ny,ut=-ux*ny+uy*nx;
                    const double ug=-un*nx-ut*ny,vg=-un*ny+ut*nx;
                    swe::FaceFlux F;double cLx,cLy,cRx,cRy;bool wet;
                    if(so) {
                        const double z=wall_eta0-wall_h0,zf=eta-hf;
                        wet=swe::faceFluxReconBed(eta,ux,uy,z,wall_h0,eta,ug,vg,z,wall_h0,
                            nx,ny,dry,F,cLx,cLy,cRx,cRy,zf,zf);
                    } else
                        wet=swe::faceFlux(eta,wall_h0,qcx_[i],qcy_[i],eta,wall_h0,
                            wall_h0*ug,wall_h0*vg,nx,ny,dry,F,cLx,cLy,cRx,cRy);
                    if(wet) {
                        const double xdt=mesh_->edge_length[slot]*dt_c;
                        dmx+=(-F.mx+cLx)*xdt;dmy+=(-F.my+cLy)*xdt;
                    }
                }
            }
'''
(O/'wall-correction.cpp').write_text(wall,encoding='utf-8')
s=s[:a]+'''            static const bool legacy_wall=std::getenv("OPENSWMM_G2_LEGACY_WALL")!=nullptr;
            if(legacy_wall) {
'''+oldwall+'''            } else {
'''+wall+'''            }
'''+s[b:]
p.write_text(s,encoding='utf-8')
(O/'diagnostic-candidate.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='a/src/engine/2d/solver/ExplicitInertialSolver.cpp',tofile='b/src/engine/2d/solver/ExplicitInertialSolver.cpp')),encoding='utf-8')
(O/'candidate-source.json').write_text(json.dumps(dict(original_solver_sha256=hashlib.sha256(original.encode()).hexdigest(),candidate_solver_sha256=hashlib.sha256(s.encode()).hexdigest(),diagnostic_switches=['OPENSWMM_G2_LEGACY_GRADIENT','OPENSWMM_G2_LEGACY_WALL'],qualification='Isolated experimental source only. Legacy switches enable one-factor attribution; no product options or defaults changed.'),indent=2)+'\n',encoding='utf-8')
print('Prepared independent native gradient and wall candidates')
