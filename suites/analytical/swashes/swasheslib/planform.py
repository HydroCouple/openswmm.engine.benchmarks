#!/usr/bin/env python3
"""Planform geometry for the bend family: a single mitered deflection.

A MiterPlanform maps centerline arc length s (and lateral offset w measured
LEFT of the tangent, w in [-W/2, +W/2]) to plan XY. Leg A runs from the
origin along +x to the corner at s_bend; leg B leaves the corner rotated by
theta_deg (positive = left turn). theta_deg = 0 degenerates to the identity
strip (xy(s, w) = (s, w)) so control cases exercise the same code path.

The 2D mesh uses row_map: rows near the corner shear progressively from
perpendicular-to-the-leg into the miter half-angle plane, so the corner row
lies exactly on the miter line and wall vertices stay on the straight
L-walls (lateral offset exactly +-W/2). Taper: tan(alpha_i) =
tan(theta/2) * max(0, 1 - |s_i - s_bend| / T), T = m*dx with
m = ceil(W*tan(theta/2)/dx), which keeps inside-of-bend row spacing >= dx/2.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MiterPlanform:
    theta_deg: float          # deflection angle (positive = left turn)
    s_bend: float             # corner arc-length position (must be a node)
    L: float                  # total centerline length
    W: float                  # channel width (w in [-W/2, +W/2])
    taper_mult: float = 1.0   # spread the shear over taper_mult x more rows
                              # (gentler per-cell skew; corner row unchanged)

    # ---- leg frames -------------------------------------------------------
    @property
    def _th(self) -> float:
        return math.radians(self.theta_deg)

    @property
    def t_a(self):
        return np.array([1.0, 0.0])

    @property
    def t_b(self):
        return np.array([math.cos(self._th), math.sin(self._th)])

    @property
    def n_a(self):
        return np.array([0.0, 1.0])

    @property
    def n_b(self):
        return np.array([-math.sin(self._th), math.cos(self._th)])

    @property
    def corner(self):
        return self.s_bend * self.t_a

    # ---- centerline / node coordinates ------------------------------------
    def xy(self, s, w=0.0):
        """Plan position of (arc length s, lateral offset w). Vectorized in s."""
        s = np.asarray(s, dtype=float)
        w = np.asarray(w, dtype=float)
        d = s - self.s_bend
        on_b = d > 0.0
        px = np.where(on_b, self.corner[0] + d * self.t_b[0] + w * self.n_b[0],
                      self.corner[0] + d * self.t_a[0] + w * self.n_a[0])
        py = np.where(on_b, self.corner[1] + d * self.t_b[1] + w * self.n_b[1],
                      self.corner[1] + d * self.t_a[1] + w * self.n_a[1])
        return px, py

    def node_xy(self, s):
        return self.xy(s, 0.0)

    # ---- mesh row mapping --------------------------------------------------
    def taper_rows(self, dx: float) -> int:
        """m — number of taper rows per leg (0 for theta = 0)."""
        t2 = math.tan(0.5 * self._th)
        if t2 <= 0.0:
            return 0
        return int(math.ceil(self.W * t2 / dx * self.taper_mult))

    def row_map(self, s_i: float, w, dx: float):
        """Vertex XY for the mesh row at station s_i, offsets w (array).

        Vertices shear along the local tangent by -w*tan(alpha_i) (leg A) /
        +w*tan(alpha_i) (leg B) so the corner row (alpha = theta/2) lies on
        the miter line and the two legs share it exactly.
        """
        w = np.asarray(w, dtype=float)
        t2 = math.tan(0.5 * self._th)
        m = self.taper_rows(dx)
        d = s_i - self.s_bend
        if m == 0 or t2 <= 0.0:
            tan_a = 0.0
        else:
            T = m * dx
            tan_a = t2 * max(0.0, 1.0 - abs(d) / T)
        if d <= 0.0:
            t, n, sgn = self.t_a, self.n_a, -1.0
        else:
            t, n, sgn = self.t_b, self.n_b, +1.0
        base = self.corner + d * t
        px = base[0] + w * n[0] + sgn * w * tan_a * t[0]
        py = base[1] + w * n[1] + sgn * w * tan_a * t[1]
        return px, py

    # ---- inverse mapping (extraction) --------------------------------------
    def s_of(self, x, y):
        """Arc length of plan points. Leg ownership by the miter-plane side
        test: sign of (P - corner) . (t_a + t_b)."""
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        cx, cy = self.corner
        bis = self.t_a + self.t_b
        side = (x - cx) * bis[0] + (y - cy) * bis[1]
        s_a = self.s_bend + (x - cx) * self.t_a[0] + (y - cy) * self.t_a[1]
        s_b = self.s_bend + (x - cx) * self.t_b[0] + (y - cy) * self.t_b[1]
        return np.where(side > 0.0, s_b, s_a)

    def tangent_of(self, x, y):
        """Unit tangent components (tx, ty) at plan points."""
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        cx, cy = self.corner
        bis = self.t_a + self.t_b
        side = (x - cx) * bis[0] + (y - cy) * bis[1]
        tx = np.where(side > 0.0, self.t_b[0], self.t_a[0])
        ty = np.where(side > 0.0, self.t_b[1], self.t_a[1])
        return tx, ty
