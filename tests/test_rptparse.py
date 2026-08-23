"""Report-file parsing — the universal, engine-agnostic contract.

Fixtures are inline text in the exact column layout SWMM writes, so these tests
run with no engine present.
"""
from __future__ import annotations

import textwrap

import pytest

from harness import rptparse

CONTINUITY = """\
  *************************
  Flow Routing Continuity            acre-feet
  *************************    ----------
  Dry Weather Inflow .......         0.000
  External Inflow ..........        33.471
  Flooding Loss ............         1.200
  Continuity Error (%) .....        -4.052


  **************************
  Runoff Quantity Continuity        acre-feet
  **************************    ----------
  Total Precipitation ......         2.500
  Continuity Error (%) .....         0.114


  *************************
  Routing Time Step Summary
  *************************
  Minimum Time Step           :    12.50 sec
  Average Time Step           :    20.00 sec
  Maximum Time Step           :    30.00 sec
  Average Iterations per Step :     2.37
  Percent Not Converging      :     3.68
"""

QUALITY_ONE = """\
  **************************           TSS
  Quality Routing Continuity           lbs
  **************************    ----------
  Dry Weather Inflow .......       179.599
  Continuity Error (%) .....        -2.140


  ********************************
  Highest Flow Instability Indexes
  ********************************
"""

QUALITY_MULTI = """\
  **************************            TN          Lead           BOD
  Quality Routing Continuity           lbs           lbs           lbs
  **************************    ----------    ----------    ----------
  Dry Weather Inflow .......    913791.663         0.000        12.500
  Continuity Error (%) .....         0.102        -1.750         0.004


  *************************
  Routing Time Step Summary
"""

LID = """\
  ***********************
  LID Performance Summary
  ***********************

  --------------------------------------------------------------------------------------------------
                                         Total      Evap     Infil   Surface    Drain   Initial  Final
  Subcatchment      LID Control         Inflow      Loss      Loss   Outflow  Outflow   Storage  Storage
  --------------------------------------------------------------------------------------------------
  S1                RB1                   9.59      0.00      0.00      0.00     0.00      0.00    6.50
  S2                GR1                  12.40      1.25      3.10      0.50     2.00      0.00    5.55
"""


def test_continuity_and_stability_scalars(tmp_path):
    p = tmp_path / "m.rpt"
    p.write_text(CONTINUITY, encoding="utf-8")
    got = rptparse.parse(p)
    assert got["routing_err"] == -4.052
    assert got["runoff_err"] == 0.114
    assert got["avg_iter"] == 2.37
    assert got["pct_not_converging"] == 3.68
    assert got["min_dt"] == 12.50
    assert got["avg_dt"] == 20.00
    assert got["max_dt"] == 30.00
    assert got["ext_inflow"] == 33.471
    assert got["had_error"] is False


def test_single_pollutant_continuity(tmp_path):
    p = tmp_path / "m.rpt"
    p.write_text(QUALITY_ONE, encoding="utf-8")
    got = rptparse.parse(p)
    assert got["quality_err"] == {"TSS": -2.140}
    assert got["worst_quality_err"] == pytest.approx(2.140)


def test_multi_pollutant_continuity(tmp_path):
    """One column per pollutant; names sit on the line ABOVE the section title."""
    p = tmp_path / "m.rpt"
    p.write_text(QUALITY_MULTI, encoding="utf-8")
    got = rptparse.parse(p)
    assert got["quality_err"] == {"TN": 0.102, "Lead": -1.750, "BOD": 0.004}
    assert got["worst_quality_err"] == pytest.approx(1.750)


def test_quality_regex_does_not_wander_to_an_earlier_banner():
    """Regression guard. Under re.S a dot crosses newlines, so a `.*?` in the
    pollutant-name group matched an unrelated banner far earlier in the file
    and the function silently returned {} — indistinguishable from 'this model
    has no pollutants'."""
    text = textwrap.dedent("""\
          *************
          Analysis Options       Volume        Volume
          *************
          Flow Routing Method ..... DYNWAVE

          **************************            TN
          Quality Routing Continuity           lbs
          **************************    ----------
          Continuity Error (%) .....         0.102


          *****
        """)
    assert rptparse.quality_continuity(text) == {"TN": 0.102}


def test_no_quality_section(tmp_path):
    p = tmp_path / "m.rpt"
    p.write_text(CONTINUITY, encoding="utf-8")
    assert rptparse.quality_continuity(CONTINUITY) == {}
    assert "quality_err" not in rptparse.parse(p)


def test_lid_performance_summary():
    """Parsed from text because the C API exposes no LID Performance table —
    so for an arbitrary engine this is the only way to see LID behavior."""
    rows = rptparse.lid_performance(LID)
    assert len(rows) == 2
    assert rows[0]["subcatchment"] == "S1"
    assert rows[0]["lid"] == "RB1"
    assert rows[0]["inflow"] == 9.59
    assert rows[0]["final_storage"] == 6.50
    assert rows[1]["lid"] == "GR1"
    assert rows[1]["infil"] == 3.10


def test_lid_absent_returns_empty():
    assert rptparse.lid_performance(CONTINUITY) == []


def test_errors_and_warnings_are_collected(tmp_path):
    p = tmp_path / "m.rpt"
    p.write_text("ERROR 138: node N1 has invalid elevation.\n"
                 "WARNING 04: minimum elevation drop used for Conduit C1\n"
                 "WARNING 04: minimum elevation drop used for Conduit C1\n", encoding="utf-8")
    got = rptparse.parse(p)
    assert got["had_error"] is True
    assert len(got["errors"]) == 2          # deduplicated, order preserved
    assert got["errors"][0].startswith("ERROR 138")


def test_undefined_continuity_dash_is_omitted_not_zero(tmp_path):
    """SWMM writes a bare '-' when a continuity value is undefined (a model
    with no runoff at all). Recording 0.0 would read as perfect continuity;
    absent is the honest representation."""
    p = tmp_path / "m.rpt"
    p.write_text("  Runoff Quantity Continuity        acre-feet\n"
                 "  Continuity Error (%) .....             -\n\n\n"
                 "  Flow Routing Continuity           acre-feet\n"
                 "  Continuity Error (%) .....        -0.500\n", encoding="utf-8")
    got = rptparse.parse(p)
    assert "runoff_err" not in got
    assert got["routing_err"] == -0.500


def test_missing_file_is_not_an_exception(tmp_path):
    assert rptparse.parse(tmp_path / "nope.rpt") == {}


def test_truncated_report_degrades_gracefully(tmp_path):
    p = tmp_path / "m.rpt"
    p.write_text("  Flow Routing Continuity\n  Dry Weather Inflow ..\n", encoding="utf-8")
    got = rptparse.parse(p)
    assert "routing_err" not in got         # absent, not zero
    assert got["had_error"] is False
