"""Apply only the qualified reconstruction/wall changes to a supplied source copy."""
from pathlib import Path
import sys,json,hashlib
R=Path(__file__).resolve().parents[3];E=R.parent/'openswmm.engine';O=R/'results/uk_2d/g2-reconstruction-2026-10-25';F=E/'tests/verification/wall_friction_2026-10-24/commit-check-source';root=Path(sys.argv[1]);rel=Path('src/engine/2d/solver/ExplicitInertialSolver.cpp');s=(root/rel).read_text();old=(F/rel).read_text();new=(O/'solver-clean.cpp').read_text()
def block(text,start,end):
 a=text.index(start);b=text.index(end,a);return text[a:b]
def replace(a,b):
 global s
 assert s.count(a)==1,(a[:100],s.count(a));s=s.replace(a,b,1)
replace('#include "../data/MeshData.hpp"','#include "../data/MeshData.hpp"\n#include "../mesh/VertexReconstruction.hpp"')
replace('        if (second_order_) {\n            const auto un', '        if (second_order_) {\n            if (mesh.vert_stencil_ptr.size() != std::size_t(mesh.n_vertices() + 1))\n                buildVertexStencils(mesh);\n            const auto un')
replace(block(old,'// RECONSTRUCTION_ORDER 2: limited Green-Gauss','\n/**'),block(new,'// RECONSTRUCTION_ORDER 2: conditioned','\n/**'))
replace("        // ONE walk of this cell's CSR row:","""        // Keep the wall flux at the same Euler-stage state as interior faces.
        const double wall_h0 = kSwe ? state_->depth[i] : 0;
        const double wall_eta0 = kSwe ? state_->head[i] : 0;
        // ONE walk of this cell's CSR row:""")
replace(block(old,'            // WALL boundary faces (every boundary slot','            if (h_new > dry) {\n                double qx'),block(new,'            if (wall_h0 > dry)','            if (h_new > dry) {\n                double qx'))
start='void ExplicitInertialSolver::fireFacesSwe(';a=s.index('    const auto& ed = edges_;',s.index(start));guard=block(new,'    // A finite water proposal','    const auto& ed = edges_;');s=s[:a]+guard+s[a:];(root/rel).write_text(s)
p=root/'src/engine/2d/solver/ExplicitInertialSolver.hpp';s=p.read_text();a=s.index('     * connected wet interiors use Green-Gauss');b=s.index('     */',a);s=s[:a]+"""     * wet stencils use conditioned inverse-distance fitting of eta/depth/velocity.
     * Dry sills exclude neighbors; shoreline velocity stays cell-centered. Bounds at connected
     * face midpoints and vertex wet-cell rings limit velocity; face positivity jointly scales
     * eta/depth. Vertex CSR is prepared in initialize(), before any checkpoint fingerprint.
     * Allocates per-vertex bounds outside the cell loop; static workers write disjoint cells.
     * Does not change water/momentum inventories, receipts, mesh identity or clocks.
"""+s[b:];p.write_text(s)
p=root/'tests/unit/engine/CMakeLists.txt';s=p.read_text();a='    add_gtest_unit(test_engine_2d_cpu_correctness test_2d_cpu_correctness.cpp)';assert s.count(a)==1;s=s.replace(a,a+'\n    add_gtest_unit(test_engine_2d_swe_reconstruction test_2d_swe_reconstruction.cpp)');p.write_text(s)
