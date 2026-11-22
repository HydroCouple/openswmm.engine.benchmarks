"""A vertex-bounded velocity control on the linear-exact gradient prototype."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[3];V=R.parent/'openswmm.engine/tests/verification/g2_reconstruction_2026-10-25';O=R/'results/uk_2d/g2-reconstruction-2026-10-25';p=V/'source/src/engine/2d/solver/ExplicitInertialSolver.cpp';s=p.read_text(encoding='utf-8');(O/'solver-before-vertex-limiter.cpp').write_text(s,encoding='utf-8')
s=s.replace('#include "../data/MeshData.hpp"','#include "../data/MeshData.hpp"\n#include "../mesh/VertexReconstruction.hpp"',1)
a='''    static const bool coupled_velocity=std::getenv("OPENSWMM_G2_COUPLED_VELOCITY_LIMITER")!=nullptr;
#pragma omp parallel'''
b='''    static const bool coupled_velocity=std::getenv("OPENSWMM_G2_COUPLED_VELOCITY_LIMITER")!=nullptr;
    static const bool vertex_limit=std::getenv("OPENSWMM_G2_VERTEX_VELOCITY_LIMITER")!=nullptr;
    std::vector<std::array<double,4>> vertex_bounds;
    if(vertex_limit) {
        if(mesh_->vert_stencil_ptr.size()!=std::size_t(mesh_->n_vertices()+1))buildVertexStencils(*mesh_);
        vertex_bounds.resize(mesh_->n_vertices());
#pragma omp parallel for schedule(static) num_threads(opts_->num_threads)
        for(int v=0;v<mesh_->n_vertices();++v) {
            double ulo=1e300,uhi=-1e300,vlo=1e300,vhi=-1e300;
            for(int p=mesh_->vert_stencil_ptr[v];p<mesh_->vert_stencil_ptr[v+1];++p) {
                const int j=mesh_->vert_stencil_idx[p];const double h=state_->depth[j];
                if(!cell_active_[j]||h<=dry||state_->head[j]-mesh_->vz[v]<=dry)continue;
                const double u=conserved?qcx_[j]:qcx_[j]/h,w=conserved?qcy_[j]:qcy_[j]/h;
                ulo=std::min(ulo,u);uhi=std::max(uhi,u);vlo=std::min(vlo,w);vhi=std::max(vhi,w);
            }
            vertex_bounds[v]={ulo,uhi,vlo,vhi};
        }
    }
#pragma omp parallel'''
assert s.count(a)==1;s=s.replace(a,b)
a='''        const int nvc=mesh_->cell_vertex_count(i);
        if(count<nvc) {'''
b='''        const int nvc=mesh_->cell_vertex_count(i);
        if(vertex_limit&&!shore) {
            for(int k=0;k<nvc;++k) {
                const int v=mesh_->cell_vertex(i,k);
                if(state_->head[i]-mesh_->vz[v]<=dry) {phi[1]=phi[2]=0;break;}
                const double ax=mesh_->vx[v]-mesh_->tri_cx[i],ay=mesh_->vy[v]-mesh_->tri_cy[i];
                const auto& b=vertex_bounds[v];
                phi[1]=std::min(phi[1],swe::bjLimiter(wi[1],wi[1]+gx[1]*ax+gy[1]*ay,std::min(wi[1],b[0]),std::max(wi[1],b[1])));
                phi[2]=std::min(phi[2],swe::bjLimiter(wi[2],wi[2]+gx[2]*ax+gy[2]*ay,std::min(wi[2],b[2]),std::max(wi[2],b[3])));
            }
        }
        if(count<nvc) {'''
assert s.count(a)==1;s=s.replace(a,b);p.write_text(s,encoding='utf-8')
(O/'vertex-limiter-source.json').write_text(json.dumps(dict(solver_sha256=hashlib.sha256(s.encode()).hexdigest(),method='Additional velocity bounds at every cell vertex, from incident active wet cells. Geometrically dry vertices revert velocity slopes to zero; existing face BJ/shoreline/positivity controls retained.'),indent=2)+'\n',encoding='utf-8')
