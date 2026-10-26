"""Extract the qualified method from the isolated experiment; no diagnostic switches."""
from pathlib import Path
import hashlib,json,difflib,shutil
R=Path(__file__).resolve().parents[3];E=R.parent/'openswmm.engine';V=E/'tests/verification/g2_reconstruction_2026-10-25';O=R/'results/uk_2d/g2-reconstruction-2026-10-25';F=E/'tests/verification/wall_friction_2026-10-24/commit-check-source'
rel=Path('src/engine/2d/solver/ExplicitInertialSolver.cpp');old=(F/rel).read_text();proto=(O/'solver-vertex-init.cpp').read_text();s=old
# Starting from the frozen source keeps all unrelated experimental flux formulas out.
s=s.replace('#include "../data/MeshData.hpp"','#include "../data/MeshData.hpp"\n#include "../mesh/VertexReconstruction.hpp"',1)
s=s.replace('        if (second_order_) {\n','        if (second_order_) {\n            if (mesh.vert_stencil_ptr.size() != std::size_t(mesh.n_vertices() + 1))\n                buildVertexStencils(mesh);\n',1)
a=proto.index('    const auto n=state_->depth.size();',proto.index('void ExplicitInertialSolver::computeLimitedGradientsSwe()'));b=proto.index('\n    }\n}',a);g=proto[a:b]
g='\n'.join(line for line in g.split('\n') if not any(x in line for x in ['static const bool zero_velocity','static const bool conserved','static const bool coupled_velocity','static const bool vertex_limit']))
g=g.replace('if(vertex_limit) {','{').replace('if(vertex_limit&&!shore)','if(!shore)')
for x in ['i','j']:
 g=g.replace(f'conserved?qcx_[{x}]:qcx_[{x}]/',f'qcx_[{x}]/').replace(f'conserved?qcy_[{x}]:qcy_[{x}]/',f'qcy_[{x}]/')
a=g.index('        if(coupled_velocity)');b=g.index('        gux_[i]',a);g=g[:a]+g[b:]
a=g.index('        if(conserved&&(shore||zero_velocity))');b=g.index('\n    }',a);g=g[:a]+g[b:]
a=s.index('// RECONSTRUCTION_ORDER 2: limited Green-Gauss');b=s.index('\n/**',a)
s=s[:a]+"""// RECONSTRUCTION_ORDER 2: conditioned, linear-exact wet-neighbour gradients.
// Bound velocity at both face midpoints and cell vertices. Thin cells,
// ill-conditioned stencils and shoreline velocity retain first-order fallback.
void ExplicitInertialSolver::computeLimitedGradientsSwe() {
"""+g+'\n}\n'+s[b:]
needle="        // ONE walk of this cell's CSR row:"
assert s.count(needle)==1;s=s.replace(needle,'        // Keep the wall flux at the same Euler-stage state as interior faces.\n        const double wall_h0 = kSwe ? state_->depth[i] : 0;\n        const double wall_eta0 = kSwe ? state_->head[i] : 0;\n'+needle)
a=s.index('            // WALL boundary faces (every boundary slot');b=s.index('            if (h_new > dry) {\n                double qx',a)
s=s[:a]+(O/'wall-correction.cpp').read_text()+s[b:]
a=proto.index('    // A finite water proposal');b=proto.index('    const auto& ed = edges_;',a);guard=proto[a:b]
a=s.index('    const auto& ed = edges_;',s.index('void ExplicitInertialSolver::fireFacesSwe('));s=s[:a]+guard+s[a:]
assert 'OPENSWMM_G2_' not in s
(V/'source'/rel).write_text(s)
shutil.copy2(F/'src/engine/2d/solver/SweKernels.hpp',V/'source/src/engine/2d/solver/SweKernels.hpp')
(O/'solver-clean-unformatted.cpp').write_text(s)
