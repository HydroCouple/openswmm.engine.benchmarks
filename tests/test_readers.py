"""Reader coverage: all four element kinds, pollutants, and both dialects.

Guards the Appendix A gap-1/gap-3 work: before this, the reader exposed node
and link series only, and nothing derived the output dialect.
"""
from __future__ import annotations

import pytest

from harness import readers
from tests.outfixture import expected, write_out


@pytest.fixture
def out53(outdir):
    return readers.Out(write_out(outdir / "a.out", n_sub=2, n_node=3, n_link=2,
                                 pollutants=["TSS", "Lead"], n_periods=4,
                                 sys_vars=15))


def test_header_and_counts(out53):
    o = out53
    assert (o.n_sub, o.n_node, o.n_link, o.n_pollut) == (2, 3, 2, 2)
    # standard variables plus one per pollutant
    assert (o.sub_vars, o.node_vars, o.link_vars) == (10, 8, 7)
    assert o.sys_vars == 15
    assert o.n_periods == 4
    assert o.flow_units == "CFS"


def test_ids(out53):
    assert out53.subcatch_ids == ["S1", "S2"]
    assert out53.node_ids == ["N1", "N2", "N3"]
    assert out53.link_ids == ["L1", "L2"]
    assert out53.pollut_ids == ["TSS", "Lead"]


@pytest.mark.parametrize("kind", ["sub", "node", "link"])
def test_element_series_round_trip(out53, kind):
    o = out53
    nvars = {"sub": o.sub_vars, "node": o.node_vars, "link": o.link_vars}[kind]
    for e, eid in enumerate(o.ids(kind)):
        for v in range(nvars):
            series = o.series(kind, eid, v)
            assert len(series) == o.n_periods
            for p in range(o.n_periods):
                assert series[p] == expected(kind, e, v, p)


def test_system_series_round_trip(out53):
    """System variables were previously unreachable: no accessor existed."""
    for v in range(out53.sys_vars):
        series = out53.sys_series(v)
        for p in range(out53.n_periods):
            assert series[p] == expected("sys", 0, v, p)


def test_system_series_bounds(out53):
    with pytest.raises(IndexError):
        out53.sys_series(out53.sys_vars)
    with pytest.raises(IndexError):
        out53.sys_series(-1)


def test_pollutant_variables_are_named_by_id(out53):
    """Pollutant variables are matched by name, never by storage index."""
    assert out53.var_names("link") == [
        "FLOW", "DEPTH", "VELOCITY", "VOLUME", "CAPACITY", "POLL:TSS", "POLL:Lead"]
    assert out53.var_names("node")[-2:] == ["POLL:TSS", "POLL:Lead"]
    assert out53.var_names("sub")[-2:] == ["POLL:TSS", "POLL:Lead"]


def test_dialect_is_derived_from_layout_not_version(outdir):
    """A 5.2-era file (14 system vars) must be recognized even though the
    engine version integer says otherwise — versions and layouts vary
    independently across engines."""
    old = readers.Out(write_out(outdir / "old.out", sys_vars=14, version=60000))
    new = readers.Out(write_out(outdir / "new.out", sys_vars=15, version=52000))
    assert old.dialect == "swmm52"
    assert new.dialect == "swmm53"
    assert old.sys_var_names()[-1] == "EVAP_RATE"
    assert new.sys_var_names()[-1] == "PET_RATE"
    assert len(old.sys_var_names()) == 14
    assert len(new.sys_var_names()) == 15


def test_unknown_dialect_degrades_gracefully(outdir):
    """An unfamiliar system-variable count must not crash the reader — a future
    engine may write a layout we have never seen."""
    weird = readers.Out(write_out(outdir / "weird.out", sys_vars=17))
    assert weird.dialect == "unknown17"
    assert weird.sys_var_names() == [f"SYS_{i}" for i in range(17)]


def test_no_pollutants(outdir):
    o = readers.Out(write_out(outdir / "clean.out", pollutants=[]))
    assert o.n_pollut == 0
    assert "POLL:" not in "".join(o.var_names("link"))


def test_bad_magic_rejected(outdir):
    path = write_out(outdir / "bad.out")
    data = bytearray(path.read_bytes())
    data[0:4] = b"\x00\x00\x00\x00"
    path.write_bytes(bytes(data))
    with pytest.raises(ValueError, match="bad magic"):
        readers.Out(path)


def test_raw_byte_accessors_agree(outdir):
    """Byte-level parity accessors must see identical files as identical."""
    a = readers.Out(write_out(outdir / "x.out"))
    b = readers.Out(write_out(outdir / "y.out"))
    assert a.results_bytes() == b.results_bytes()
    assert a.body_after_version() == b.body_after_version()
