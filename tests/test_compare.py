"""Comparison coverage — the Appendix A gap-2 work.

The historical comparison covered link {FLOW, DEPTH, VELOCITY, VOLUME} and
node {DEPTH, HEAD, VOLUME} only. A pollutant difference, a subcatchment
difference, or a system-total difference was invisible — which mattered most
for exactly the water-quality and LID cases the platform is being extended to
cover. These tests plant such differences and require them to be found.
"""
from __future__ import annotations

import pytest

from harness import compare, readers
from tests.outfixture import expected, write_out

POLLUTANTS = ["TSS", "Lead"]


def _pair(outdir, perturb=None, **kw):
    kw.setdefault("pollutants", POLLUTANTS)
    a = write_out(outdir / "a.out", **kw)
    b = write_out(outdir / "b.out", perturb=perturb, **kw)
    return a, b


def test_identical_files_are_strictly_identical(outdir):
    a, b = _pair(outdir)
    res = compare.compare_full(a, b)
    assert res["verdict"] == "PASS"
    assert res["strict_identical"] is True
    assert res["total_over_tol"] == 0
    assert res["fault"] == []
    assert res["total_exact"] == res["total_cells"]


def test_all_four_element_kinds_are_compared(outdir):
    a, b = _pair(outdir, n_sub=2, n_node=3, n_link=2)
    res = compare.compare_full(a, b)
    kinds = {k.split(".", 1)[0] for k in res["per_var"]}
    assert kinds == {"sub", "node", "link", "sys"}
    assert res["n_elements"] == {"link": 2, "node": 3, "sub": 2, "sys": 1}


@pytest.mark.parametrize("kind,var_name,var_index", [
    ("link", "POLL:TSS", 5),      # 5 standard link vars, then pollutants
    ("node", "POLL:Lead", 7),     # 6 standard node vars, then pollutants
    ("sub", "POLL:TSS", 8),       # 8 standard subcatchment vars
])
def test_pollutant_difference_is_detected(outdir, kind, var_name, var_index):
    """A pollutant concentration change must fail the comparison.

    This is the regression guard for gap 2: every one of these was previously
    unexamined, so a water-quality divergence passed silently.
    """
    perturb = {(kind, 0, var_index, 2): expected(kind, 0, var_index, 2) + 5.0}
    a, b = _pair(outdir, perturb=perturb)
    res = compare.compare_full(a, b)
    assert res["verdict"] == "FAIL"
    assert res["total_over_tol"] == 1
    key = f"{kind}.{var_name}"
    assert key in res["per_var"], f"{key} not compared"
    assert res["per_var"][key]["n_over_tol"] == 1
    assert res["per_var"][key]["first_div_period"] == 2
    assert res["worst_offenders"][0]["var"] == key


def test_subcatchment_difference_is_detected(outdir):
    perturb = {("sub", 1, 4, 1): expected("sub", 1, 4, 1) + 2.0}  # RUNOFF
    a, b = _pair(outdir, perturb=perturb)
    res = compare.compare_full(a, b)
    assert res["verdict"] == "FAIL"
    assert res["per_var"]["sub.RUNOFF"]["n_over_tol"] == 1
    assert res["per_var"]["sub.RUNOFF"]["worst_eid"] == "S2"


def test_system_variable_difference_is_detected(outdir):
    perturb = {("sys", 0, 12, 3): expected("sys", 0, 12, 3) + 1.0}
    a, b = _pair(outdir, perturb=perturb)
    res = compare.compare_full(a, b)
    assert res["verdict"] == "FAIL"
    assert res["per_var"]["sys.STORAGE_VOLUME"]["n_over_tol"] == 1


def test_tolerance_is_respected(outdir):
    """A difference below the pair's tolerance is recorded but not failed."""
    base = expected("link", 0, 0, 1)
    perturb = {("link", 0, 0, 1): base * (1 + 1e-7)}
    a, b = _pair(outdir, perturb=perturb)
    assert compare.compare_full(a, b, rtol=1e-9)["verdict"] == "FAIL"
    loose = compare.compare_full(a, b, rtol=1e-4)
    assert loose["verdict"] == "PASS"
    assert loose["strict_identical"] is False   # differs, but within tolerance


def test_cross_dialect_compares_the_intersection(outdir):
    """swmm52 (14 system vars) vs swmm53 (15) must compare the shared 14 and
    report PET_RATE as skipped, not crash and not silently mis-align."""
    a = write_out(outdir / "old.out", sys_vars=14, pollutants=POLLUTANTS)
    b = write_out(outdir / "new.out", sys_vars=15, pollutants=POLLUTANTS)
    res = compare.compare_full(a, b)
    assert res["dialects"] == {"a": "swmm52", "b": "swmm53"}
    assert "sys.PET_RATE" not in res["per_var"]
    assert "sys.EVAP_RATE" in res["per_var"]
    assert res["skipped_vars"]["sys"] == ["PET_RATE"]
    assert any("dialect differs" in f for f in res["fault"])
    # the 14 shared system variables still line up exactly
    assert res["per_var"]["sys.EVAP_RATE"]["max_abs"] == 0.0


def test_differing_pollutant_sets_compare_the_intersection(outdir):
    a = write_out(outdir / "a.out", pollutants=["TSS", "Lead"])
    b = write_out(outdir / "b.out", pollutants=["TSS"])
    res = compare.compare_full(a, b)
    assert "link.POLL:TSS" in res["per_var"]
    assert "link.POLL:Lead" not in res["per_var"]
    assert "POLL:Lead" in res["skipped_vars"]["link"]


def test_element_mismatch_is_a_fault(outdir):
    a = write_out(outdir / "a.out", n_node=3)
    b = write_out(outdir / "b.out", n_node=4)
    res = compare.compare_full(a, b)
    assert res["verdict"] == "ERROR"
    assert any("node-id mismatch" in f for f in res["fault"])


def test_offenders_rank_by_violating_cells_not_relative_error(outdir):
    """A single near-zero cell has an enormous relative error but negligible
    absolute one; it must not outrank a systematic divergence."""
    perturb = {}
    # one near-zero blip with a huge relative error
    perturb[("link", 0, 1, 0)] = 1e3
    # a systematic difference across every period of another variable
    for p in range(4):
        perturb[("node", 0, 0, p)] = expected("node", 0, 0, p) + 1.0
    a, b = _pair(outdir, perturb=perturb, n_periods=4)
    res = compare.compare_full(a, b)
    assert res["worst_offenders"][0]["var"] == "node.DEPTH"
    assert res["worst_offenders"][0]["n_over_tol"] == 4


def test_legacy_bit_parity_ladder_still_works(outdir):
    """compare() implements the float32-ULP parity gate and must be unchanged
    by the wider coverage added alongside it."""
    a, b = _pair(outdir)
    res = compare.compare(a, b)
    assert res["verdict"] == "PARITY"
    assert res["bit_parity"] is True
    assert res["strict_identical"] is True
    assert res["bytes_results_identical"] is True


def test_common_vars_matches_by_name(outdir):
    a = readers.Out(write_out(outdir / "a.out", sys_vars=14))
    b = readers.Out(write_out(outdir / "b.out", sys_vars=15))
    shared = compare.common_vars(a, b, "sys")
    names = [n for _, n, _, _ in shared]
    assert "PET_RATE" not in names
    assert len(shared) == 14
    # indices are per-file: identical here, but the API must carry both
    for _, _, ia, ib in shared:
        assert ia == ib


def test_pollutants_in_different_order_align_by_name(outdir):
    """The decisive test for name-matching: two engines may write the same two
    pollutants in opposite order. Index-matching would compare TSS against
    Lead and report a spurious divergence in both."""
    a = readers.Out(write_out(outdir / "a.out", pollutants=["TSS", "Lead"]))
    b = readers.Out(write_out(outdir / "b.out", pollutants=["Lead", "TSS"]))
    shared = {n: (ia, ib) for _, n, ia, ib in compare.common_vars(a, b, "link")}
    assert shared["POLL:TSS"] == (5, 6)     # index differs between the files
    assert shared["POLL:Lead"] == (6, 5)

    # The stored values follow the index, so a name-matched comparison sees a
    # real difference here — the point is that it compares TSS against TSS.
    res = compare.compare_full(a.path, b.path)
    assert "link.POLL:TSS" in res["per_var"]
    assert res["per_var"]["link.POLL:TSS"]["max_abs"] == pytest.approx(10.0)
