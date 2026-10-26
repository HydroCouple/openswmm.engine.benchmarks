// Independent shoreline audit. Links to the immutable corrected Test 6 image.
#include "2d/data/MeshData.hpp"
#include "2d/data/SolverOptions2D.hpp"
#include "2d/data/SurfaceStateData.hpp"
#include "2d/mesh/MeshBuilder.hpp"
#include "2d/solver/ExplicitInertialSolver.hpp"
#include "2d/solver/InertialKernels.hpp"
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <vector>
using namespace openswmm::twoD;
namespace openswmm::twoD {
struct ExplicitInertialSolverTestAccess {
  static double momentum(const ExplicitInertialSolver &s, int i) {
    return std::hypot(s.qcx_[i], s.qcy_[i]);
  }
};
} // namespace openswmm::twoD
struct Point {
  double x, y, z;
};
// Clip the actual planar triangle at eta, then exactly integrate linear water
// depth over a fan triangulation. Independent of engine VFR formula/inversion.
double clippedVolume(std::vector<Point> p, double eta) {
  std::vector<Point> q;
  for (size_t i = 0; i < p.size(); ++i) {
    auto a = p[i], b = p[(i + 1) % p.size()];
    if (a.z < eta)
      q.push_back(a);
    if ((a.z < eta) != (b.z < eta)) {
      double t = (eta - a.z) / (b.z - a.z);
      q.push_back({a.x + t * (b.x - a.x), a.y + t * (b.y - a.y), eta});
    }
  }
  double v = 0;
  for (size_t i = 1; i + 1 < q.size(); ++i) {
    auto a = q[0], b = q[i], c = q[i + 1];
    double area =
        .5 * std::abs((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x));
    v += area * ((eta - a.z) + (eta - b.z) + (eta - c.z)) / 3;
  }
  return v;
}
MeshData mesh(int n, double angle) {
  MeshData m;
  m.resize_vertices((n + 1) * (n + 1));
  double co = std::cos(angle), si = std::sin(angle);
  for (int j = 0; j <= n; ++j)
    for (int i = 0; i <= n; ++i) {
      double x = double(i) / n, y = .68 * j / n;
      if (i > 0 && i < n && j > 0 && j < n) {
        x += .12 / n * std::sin(1.7 * i + 2.3 * j);
        y += .08 * .68 / n * std::cos(2.1 * i - 1.4 * j);
      }
      int v = j * (n + 1) + i;
      m.vx[v] = co * x - si * y;
      m.vy[v] = si * x + co * y;
      m.vz[v] = (.155 / .34) * y;
    }
  m.resize_triangles(2 * n * n);
  int c = 0;
  for (int j = 0; j < n; ++j)
    for (int i = 0; i < n; ++i) {
      int a = j * (n + 1) + i, b = a + 1, d = a + n + 1, e = d + 1;
      m.set_triangle(c++, a, b, e);
      m.set_triangle(c++, a, e, d);
    }
  buildMeshTopology(m);
  for (int i = 0; i < m.n_cells(); ++i)
    m.mannings_n[i] = 0;
  return m;
}
int main(int argc, char **argv) {
  if (argc == 3 && std::string(argv[2]) == "ridge") {
    std::ofstream out(argv[1]);
    out << std::setprecision(17);
    out << "momentum,order,face_mode,crest_m,eta_left_m,eta_right_m,volume_"
           "left_initial_m3,volume_left_final_m3,total_volume_error_m3,time_"
           "s\n";
    for (double left : {.1, .12, .2})
      for (bool full : {false, true})
        for (int order : {1, 2})
          for (bool edge : {false, true}) {
            MeshData m;
            m.resize_vertices(4);
            m.vx = {0, 1, 0, 1};
            m.vy = {0, 0, 1, 1};
            m.vz = {0, .155, .155, 0};
            m.resize_triangles(2);
            m.set_triangle(0, 0, 1, 2);
            m.set_triangle(1, 1, 3, 2);
            buildMeshTopology(m);
            for (int i = 0; i < 2; ++i)
              m.mannings_n[i] = 0;
            SurfaceStateData state;
            state.resize(2, 4);
            SolverOptions2D opt;
            opt.momentum =
                full ? Momentum2D::FULL_SWE : Momentum2D::LOCAL_INERTIAL;
            opt.reconstruction_order = order;
            opt.cell_closure = CellClosure2D::VFR;
            opt.face_reconstruction =
                edge ? FaceDepth2D::VFR_FACE : FaceDepth2D::MEAN;
            opt.lts_tiers = 1;
            opt.num_threads = 1;
            opt.max_timestep = .0001;
            opt.dry_depth = .0001;
            if (full) {
              opt.turbulence = Turbulence2D::SMAGORINSKY;
              opt.smagorinsky_cs = 0;
            }
            for (int i = 0; i < 2; ++i) {
              std::vector<Point> p;
              for (int k = 0; k < 3; ++k) {
                int v = m.cell_vertex(i, k);
                p.push_back({m.vx[v], m.vy[v], m.vz[v]});
              }
              state.volume[i] = clippedVolume(p, i == 0 ? left : .02);
              inertial::cellEtaDepth(m, opt, i, state.volume[i], state.head[i],
                                     state.depth[i]);
            }
            double v0 = state.volume[0], total = v0 + state.volume[1],
                   h0 = state.head[0], h1 = state.head[1];
            ExplicitInertialSolver solver;
            solver.initialize(m, state, opt);
            double t = solver.advance(0, .001);
            out << (full ? "FULL_SWE" : "LOCAL_INERTIAL") << ',' << order << ','
                << (edge ? "VFR_FACE" : "MEAN") << ",.155," << h0 << ',' << h1
                << ',' << v0 << ',' << state.volume[0] << ','
                << state.volume[0] + state.volume[1] - total << ',' << t
                << '\n';
          }
    return 0;
  }
  if (argc != 2)
    return 2;
  std::ofstream out(argv[1]);
  out << std::setprecision(17);
  out << "n,angle_deg,order,closure,initialization,kind,eta_m,initial_volume_"
         "m3,geometric_volume_m3,initial_head_error_m,final_time_s,max_"
         "momentum_m2ps,max_wet_speed_mps,max_volume_error_m3,max_volume_"
         "change_l1_m3,final_head_error_m,minimum_depth_m,steps\n";
  // All independent dimensions declared before execution. Lake tolerance is
  // 2e-11 in momentum/head; volume tolerance 2e-11 m3. Release: finiteness,
  // nonnegative water, conserved volume, duration only; no reference solution.
  for (int n : {8, 16, 32})
    for (double degrees : {0., 64.})
      for (int order : {1, 2})
        for (int mode : {0, 1, 2})
          for (int kind : {0, 1, 2}) {
            auto m = mesh(n, degrees * std::acos(-1.) / 180);
            SurfaceStateData state;
            state.resize(m.n_cells(), m.n_vertices());
            SolverOptions2D opt;
            opt.momentum = Momentum2D::FULL_SWE;
            opt.reconstruction_order = order;
            opt.lts_tiers = 1;
            opt.num_threads = 1;
            opt.cfl_number = .4;
            opt.max_timestep = .002;
            opt.dry_depth = .0001;
            opt.turbulence = Turbulence2D::SMAGORINSKY;
            opt.smagorinsky_cs = 0;
            opt.cell_closure =
                mode == 2 ? CellClosure2D::VFR : CellClosure2D::FLAT;
            std::vector<double> v0(m.n_cells()), eta0(m.n_cells()),
                physical(m.n_cells());
            double initial = 0, geometric = 0, head_error = 0;
            double eta = kind == 1 ? .4 : .1;
            for (int i = 0; i < m.n_cells(); ++i) {
              double x =
                  std::cos(degrees * std::acos(-1.) / 180) * m.tri_cx[i] +
                  std::sin(degrees * std::acos(-1.) / 180) * m.tri_cy[i];
              eta0[i] = kind == 2 && x >= .5 ? .02 : eta;
              std::vector<Point> p;
              for (int k = 0; k < 3; ++k) {
                int v = m.cell_vertex(i, k);
                p.push_back({m.vx[v], m.vy[v], m.vz[v]});
              }
              physical[i] = clippedVolume(p, eta0[i]);
              geometric += physical[i];
              state.volume[i] = v0[i] =
                  mode == 0
                      ? m.tri_area[i] * std::max(0., eta0[i] - m.tri_cz[i])
                      : physical[i];
              initial += v0[i];
              inertial::cellEtaDepth(m, opt, i, v0[i], state.head[i],
                                     state.depth[i]);
              if (physical[i] / m.tri_area[i] > .0001)
                head_error =
                    std::max(head_error, std::abs(state.head[i] - eta0[i]));
            }
            ExplicitInertialSolver solver;
            solver.initialize(m, state, opt);
            double time = 0, maxq = 0, maxspeed = 0, maxvol = 0, maxl1 = 0,
                   minh = 1e100, finalhead = 0, end = kind == 2 ? .5 : .2;
            int steps = 0;
            while (time < end - 1e-12) {
              double target = std::min(end, time + .01);
              time = solver.advance(time, target);
              ++steps;
              double volume = 0, l1 = 0;
              finalhead = 0;
              for (int i = 0; i < m.n_cells(); ++i) {
                double q =
                    ExplicitInertialSolverTestAccess::momentum(solver, i);
                if (!std::isfinite(q) || !std::isfinite(state.depth[i]))
                  return 3;
                maxq = std::max(maxq, q);
                if (state.depth[i] > opt.dry_depth)
                  maxspeed = std::max(maxspeed, q / state.depth[i]);
                volume += state.volume[i];
                l1 += std::abs(state.volume[i] - v0[i]);
                minh = std::min(minh, state.depth[i]);
                if (physical[i] / m.tri_area[i] > .0001)
                  finalhead =
                      std::max(finalhead, std::abs(state.head[i] - eta0[i]));
              }
              maxvol = std::max(maxvol, std::abs(volume - initial));
              maxl1 = std::max(maxl1, l1);
            }
            out << n << ',' << degrees << ',' << order << ','
                << (mode == 2 ? "VFR" : "FLAT") << ','
                << (mode == 0 ? "centroid" : "clipped") << ','
                << (kind == 0   ? "shoreline_lake"
                    : kind == 1 ? "fully_wet_lake"
                                : "bank_release")
                << ',' << eta << ',' << initial << ',' << geometric << ','
                << head_error << ',' << time << ',' << maxq << ',' << maxspeed
                << ',' << maxvol << ',' << maxl1 << ',' << finalhead << ','
                << minh << ',' << steps << '\n';
            out.flush();
          }
}
