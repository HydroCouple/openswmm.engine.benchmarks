// SPDX-License-Identifier: Apache-2.0
//
// Copyright 2026 Caleb Buahin
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * @file cheb_xsect_prototype.hpp
 * @brief Chebyshev feasibility study, phase B2 — STUDY-ONLY prototype.
 *        Never included from src/engine.
 *
 * @details B1 established that global Chebyshev series CANNOT replace the
 *          51-row table evaluators at parity tolerance (error frontier
 *          ~1e-3..1e-2 normalized vs the 1e-8 bar; forward fits mostly
 *          non-monotone from Gibbs ringing around the tables' corners). What
 *          remains viable is the SEED role: a low-degree inverse fit provides
 *          the starting point, and a short Newton polish against the EXACT
 *          table evaluators carries it to the same tolerance the shipped
 *          root-finders use. The answer converges on the exact functions —
 *          only the iteration count changes — so this slots into the
 *          tolerance-gated fast tier (OPENSWMM_FAST_XSECT_LOOKUP family),
 *          not the bit-exact default.
 *
 *          Fitting here is Chebyshev-node interpolation (numerically stable
 *          for the piecewise-linear targets, no least squares), evaluated by
 *          Clenshaw. No FMA anywhere: the engine builds with
 *          -ffp-contract=off, so the honest cost of degree N is ~2N mul+add.
 *
 * @author   Caleb Buahin <caleb.buahin@gmail.com>
 * @copyright Copyright (c) 2026 Caleb Buahin. All rights reserved.
 * @license  Apache-2.0
 */

#ifndef OPENSWMM_CHEB_XSECT_PROTOTYPE_HPP
#define OPENSWMM_CHEB_XSECT_PROTOTYPE_HPP

#include <cmath>
#include <functional>
#include <vector>

#include "../../../src/engine/hydraulics/XSectBatch.hpp"
#include "../../../src/engine/hydraulics/XSectKernels.hpp"

namespace cheb_study {

/// One Chebyshev series on [0, 1], Clenshaw-evaluated.
struct ChebFit {
    std::vector<double> c;   // Chebyshev coefficients, c[0]..c[deg]

    double operator()(double x) const {
        // map [0,1] -> [-1,1]
        const double t = 2.0 * x - 1.0;
        const double t2 = 2.0 * t;
        double b1 = 0.0, b2 = 0.0;
        for (std::size_t k = c.size(); k-- > 1;) {
            const double b0 = c[k] + t2 * b1 - b2;
            b2 = b1;
            b1 = b0;
        }
        return c[0] + t * b1 - b2;
    }
};

/// Interpolate f (defined on [0,1]) at the deg+1 Chebyshev points.
inline ChebFit fit_on_unit(const std::function<double(double)>& f, int deg) {
    const int n = deg + 1;
    std::vector<double> fx(static_cast<std::size_t>(n));
    for (int k = 0; k < n; ++k) {
        const double theta = M_PI * (k + 0.5) / n;
        const double t = std::cos(theta);          // node in [-1,1]
        fx[static_cast<std::size_t>(k)] = f(0.5 * (t + 1.0));
    }
    ChebFit fit;
    fit.c.assign(static_cast<std::size_t>(n), 0.0);
    for (int j = 0; j < n; ++j) {
        double s = 0.0;
        for (int k = 0; k < n; ++k)
            s += fx[static_cast<std::size_t>(k)] *
                 std::cos(M_PI * j * (k + 0.5) / n);
        fit.c[static_cast<std::size_t>(j)] = (j == 0 ? 1.0 : 2.0) * s / n;
    }
    return fit;
}

/// Per-link seed fits for the two expensive inversions.
struct SeededInverter {
    ChebFit y_of_a;     // normalized y(a) seed
    ChebFit a_of_s;     // normalized a(s) seed on the primary branch
    double s_primary;   // absolute S at the top of the monotone branch

    static SeededInverter build(const openswmm::xsect::XsectEval& ev,
                                const openswmm::XSectParams& xs, int deg) {
        SeededInverter si;
        si.y_of_a = fit_on_unit(
            [&](double an) { return ev.getYofA(xs, an * xs.a_full) / xs.y_full; },
            deg);
        // primary branch of S: monotone from 0 up to s_full (top-of-section
        // non-monotonicity lives in (s_full, s_max), which keeps the shipped
        // bracket special-case)
        si.s_primary = xs.s_full;
        si.a_of_s = fit_on_unit(
            [&](double sn) { return ev.getAofS(xs, sn * si.s_primary) / xs.a_full; },
            deg);
        return si;
    }

    /// depthOfArea replacement: Chebyshev seed + Newton polish on the EXACT
    /// A(y) with dA/dy = W(y) (both plain table lookups), FV exit tolerance.
    /// Returns depth; *evals counts exact-evaluator calls.
    double depth_of_area(const openswmm::xsect::XsectEval& ev,
                         const openswmm::XSectParams& xs, double a,
                         int* evals) const {
        if (a <= 0.0) return 0.0;
        if (a >= xs.a_full) return xs.y_full;
        double y = y_of_a(a / xs.a_full) * xs.y_full;
        if (y < 0.0) y = 0.0;
        if (y > xs.y_full) y = xs.y_full;
        const double tol = 1e-10 * xs.a_full;
        for (int it = 0; it < 20; ++it) {
            const double f = ev.getAofY(xs, y) - a;
            ++*evals;
            if (std::fabs(f) <= tol) return y;
            const double w = ev.getWofY(xs, y);
            ++*evals;
            if (w <= 0.0) break;
            double ynew = y - f / w;
            if (ynew < 0.0) ynew = 0.5 * y;
            if (ynew > xs.y_full) ynew = 0.5 * (y + xs.y_full);
            y = ynew;
        }
        return y;
    }

    /// getAofS replacement on the primary branch: seed + Newton polish with
    /// the exact getSofA/getdSdA and the shipped tolerance (1e-4 * a_full on
    /// the step, findroot_Newton's criterion).
    double area_of_s(const openswmm::xsect::XsectEval& ev,
                     const openswmm::XSectParams& xs, double s,
                     int* iters) const {
        if (s <= 0.0) return 0.0;
        if (s > s_primary) return ev.getAofS(xs, s);   // shipped path for the top branch
        double a = a_of_s(s / s_primary) * xs.a_full;
        if (a < 0.0) a = 0.0;
        if (a > xs.a_full) a = xs.a_full;
        const double tol = 0.0001 * xs.a_full;
        for (int it = 0; it < 20; ++it) {
            ++*iters;
            double f = ev.getSofA(xs, a) - s;
            double df = ev.getdSdA(xs, a);
            if (df == 0.0) break;
            const double da = f / df;
            a -= da;
            if (a < 0.0) a = 0.0;
            if (a > xs.a_full) a = xs.a_full;
            if (std::fabs(da) < tol) break;
        }
        return a;
    }
};

}  // namespace cheb_study

#endif  // OPENSWMM_CHEB_XSECT_PROTOTYPE_HPP
