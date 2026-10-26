"""Isolate a coupled primitive limiter and conservative momentum reconstruction."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[3];V=R.parent/'openswmm.engine/tests/verification/g2_reconstruction_2026-10-25';O=R/'results/uk_2d/g2-reconstruction-2026-10-25';p=V/'source/src/engine/2d/solver/ExplicitInertialSolver.cpp';s=p.read_text();(O/'solver-before-momentum-controls.cpp').write_text(s)
a='''    static const bool zero_velocity=std::getenv("OPENSWMM_G2_ZERO_VELOCITY_SLOPES")!=nullptr;'''
b=a+'''
    static const bool conserved=std::getenv("OPENSWMM_G2_CONSERVED_MOMENTUM")!=nullptr;
    static const bool coupled_velocity=std::getenv("OPENSWMM_G2_COUPLED_VELOCITY_LIMITER")!=nullptr;''';assert s.count(a)==1;s=s.replace(a,b)
a='''        const double wi[4]={state_->head[i],qcx_[i]/hi,qcy_[i]/hi,hi};''';b='''        const double wi[4]={state_->head[i],conserved?qcx_[i]:qcx_[i]/hi,conserved?qcy_[i]:qcy_[i]/hi,hi};''';assert s.count(a)==1;s=s.replace(a,b)
a='''            const double wj[4]={ej,qcx_[j]/hj,qcy_[j]/hj,hj};''';b='''            const double wj[4]={ej,conserved?qcx_[j]:qcx_[j]/hj,conserved?qcy_[j]:qcy_[j]/hj,hj};''';assert s.count(a)==1;s=s.replace(a,b)
a='''        gux_[i]=phi[1]*gx[1];guy_[i]=phi[1]*gy[1];''';b='''        if(coupled_velocity)phi[1]=phi[2]=std::min(phi[1],phi[2]);
'''+a;assert s.count(a)==1;s=s.replace(a,b)
a='''        if(zero_velocity)gux_[i]=guy_[i]=gvx_[i]=gvy_[i]=0;''';b='''        if(conserved&&(shore||zero_velocity)) {
            gux_[i]=(qcx_[i]/hi)*gex_[n+i];guy_[i]=(qcx_[i]/hi)*gey_[n+i];
            gvx_[i]=(qcy_[i]/hi)*gex_[n+i];gvy_[i]=(qcy_[i]/hi)*gey_[n+i];
        } else if(zero_velocity)gux_[i]=guy_[i]=gvx_[i]=gvy_[i]=0;''';assert s.count(a)==1;s=s.replace(a,b)
for name in ['uLf','vLf','uRf','vRf']:s=s.replace('const double '+name+' =','double '+name+' =',1)
a='''            const double zRf=fixed_bed?(hb>dry?edge_bed:zb):etaRf-hRf;''';b=a+'''
            static const bool conserved=std::getenv("OPENSWMM_G2_CONSERVED_MOMENTUM")!=nullptr;
            if(conserved) {
                const double hl=std::max(0.,etaLf-zLf),hr=std::max(0.,etaRf-zRf);
                uLf=hl>dry?(qcx_[a]+gux_[a]*axa+guy_[a]*aya)/hl:0;
                vLf=hl>dry?(qcy_[a]+gvx_[a]*axa+gvy_[a]*aya)/hl:0;
                uRf=hr>dry?(qcx_[b]+gux_[b]*axb+guy_[b]*ayb)/hr:0;
                vRf=hr>dry?(qcy_[b]+gvx_[b]*axb+gvy_[b]*ayb)/hr:0;
            }''';assert s.count(a)==1;s=s.replace(a,b)
a='''                        ux+=gux_[i]*ax+guy_[i]*ay;uy+=gvx_[i]*ax+gvy_[i]*ay;''';b='''                        static const bool conserved=std::getenv("OPENSWMM_G2_CONSERVED_MOMENTUM")!=nullptr;
                        if(conserved) {
                            double hv=hf;
                            static const bool fixed_bed=std::getenv("OPENSWMM_G2_FIXED_FACE_BED")!=nullptr;
                            if(fixed_bed) {int a,b;mesh_->cell_edge_vertices(i,MeshData::slot_local(slot),a,b);hv=std::max(0.,eta-.5*(mesh_->vz[a]+mesh_->vz[b]));}
                            ux=hv>dry?(qcx_[i]+gux_[i]*ax+guy_[i]*ay)/hv:0;
                            uy=hv>dry?(qcy_[i]+gvx_[i]*ax+gvy_[i]*ay)/hv:0;
                        } else {
                            ux+=gux_[i]*ax+guy_[i]*ay;uy+=gvx_[i]*ax+gvy_[i]*ay;
                        }''';assert s.count(a)==1;s=s.replace(a,b);p.write_text(s)
(O/'momentum-controls-source.json').write_text(json.dumps(dict(solver_sha256=hashlib.sha256(s.encode()).hexdigest(),controls=['Common scalar factor for x/y velocity slopes','LS/BJ reconstruction of conserved qx/qy, preserving cell velocity at shoreline faces']),indent=2)+'\n')
print('Prepared momentum controls')
