#!/usr/bin/env python3
"""Text parsing of the SWMM ``.rpt`` report file.

The universal contract: every SWMM-compatible engine writes this text report,
so scraping it is the ONLY way to grade an arbitrary registered engine. The
openswmm Python binding offers a structured, parse-free path
(``openswmm.engine.get_report_snapshot``) with richer data, but it works for
openswmm alone and requires in-process execution — it is an enrichment, never
the critical path (see plans/BENCHMARK_PLATFORM_PLAN_2026-08-22.md, Appendix A).

Merges the two near-duplicate scrapers previously in
``epaswmm5_qa/core/runner.py`` and ``suites/epa_qa/harness/qalib.py``, and adds
quality continuity + LID performance (Appendix A gaps 4–5).
"""
from __future__ import annotations

import re
from pathlib import Path

# ── scalar scrapes: (regex, key, cast) ─────────────────────────────────────
_SCALARS: list[tuple[str, str, type]] = [
    (r"Average Iterations per Step\s*[:.]*\s*([\d.]+)", "avg_iter", float),
    (r"(?:Percent\s+)?Not Converging\s*[:.]*\s*([\d.]+)", "pct_not_converging", float),
    (r"Average Time Step\s*[:.]*\s*([\d.]+)", "avg_dt", float),
    (r"Minimum Time Step\s*[:.]*\s*([\d.]+)", "min_dt", float),
    (r"Maximum Time Step\s*[:.]*\s*([\d.]+)", "max_dt", float),
    (r"External Inflow\s*\.+\s*([-\d.]+)", "ext_inflow", float),
]

#: Summary tables whose ROW COUNT is the metric. SWMM does not write a
#: sentence like "3 links were surcharged" — it writes a table, or the phrase
#: "No conduits were surcharged." An inherited regex looking for the sentence
#: matched nothing on any real report, silently reporting zero surcharging
#: everywhere.
_TABLES: list[tuple[str, str]] = [
    ("nodes_flooded", "Node Flooding Summary"),
    ("nodes_surcharged", "Node Surcharge Summary"),
    ("conduits_surcharged", "Conduit Surcharge Summary"),
]

#: Continuity tables, by report section heading.
_CONTINUITY: list[tuple[str, str]] = [
    ("Runoff Quantity Continuity", "runoff_err"),
    ("Flow Routing Continuity", "routing_err"),
    ("Groundwater Continuity", "groundwater_err"),
]


def parse(path: str | Path) -> dict:
    """Global continuity / stability metrics from a ``.rpt`` (any engine).

    Returns a flat dict; keys are absent when the section is not present, so
    callers must use ``.get()``. Never raises on malformed input.
    """
    out: dict = {}
    path = Path(path)
    if not path.exists():
        return out
    text = path.read_text(encoding="utf-8", errors="replace")

    for label, key in _CONTINUITY:
        m = re.search(re.escape(label)
                      + r".*?Continuity Error \(%\)\s*\.+\s*([-\d.]+)",
                      text, re.S)
        if m:
            try:
                out[key] = float(m.group(1))
            except ValueError:
                # SWMM writes a bare '-' when the value is undefined (e.g. no
                # runoff at all). Absent is the honest representation; 0.0
                # would read as "perfect continuity".
                pass

    for pat, key, cast in _SCALARS:
        m = re.search(pat, text, re.S)
        if m:
            try:
                out[key] = cast(m.group(1))
            except ValueError:
                pass

    for key, title in _TABLES:
        n = table_row_count(text, title)
        if n is not None:
            out[key] = n

    m = re.search(r"Highest Flow Instability Indexes(.*?)"
                  r"(?:\n[ \t]*\n[ \t]*\n|\Z)", text, re.S)
    if m:
        body = m.group(1)
        out["links_instability"] = (
            0 if re.search(r"All links are stable", body, re.I)
            else len(re.findall(r"^\s*Link\s+\S+", body, re.M)))

    q = quality_continuity(text)
    if q:
        out["quality_err"] = q
        out["worst_quality_err"] = max(abs(v) for v in q.values())

    out["errors"] = errors(text)
    out["had_error"] = bool(out["errors"])
    return out


def quality_continuity(text: str) -> dict[str, float]:
    """Per-pollutant continuity error from the Quality Routing Continuity table.

    The table is column-per-pollutant: pollutant names appear in the header row
    and the ``Continuity Error (%)`` row carries one value per column.
    """
    # Layout (one column per pollutant; names sit on the line ABOVE the title,
    # units on the title line itself):
    #     **************************            TN          Lead
    #     Quality Routing Continuity           lbs           lbs
    #     **************************    ----------    ----------
    #     Dry Weather Inflow .......    913791.663         0.000
    #     ...
    #     Continuity Error (%) .....         0.000         0.000
    # NOTE: the names group must be [^\n]* rather than .*? — under re.S a dot
    # crosses newlines and would match an earlier banner elsewhere in the file.
    m = re.search(r"\*{10,}[ \t]+(\S[^\n]*)\n[ \t]*Quality Routing Continuity"
                  r"(.*?)(?:\n[ \t]*\n[ \t]*\n|\Z)", text, re.S)
    if not m:
        return {}
    names = m.group(1).split()
    err = re.search(r"Continuity Error \(%\)\s*\.+\s*(.+)", m.group(2))
    if not names or not err:
        return {}
    try:
        vals = [float(v) for v in err.group(1).split()]
    except ValueError:
        return {}
    return dict(zip(names, vals)) if len(names) == len(vals) else {}


def table_row_count(text: str, title: str) -> int | None:
    """Number of data rows in a named summary table.

    Returns 0 when the section says nothing qualified ("No nodes were
    surcharged."), and None when the section is absent entirely — the two are
    different: absent means the engine did not report it, zero means it did
    and found none.
    """
    m = re.search(re.escape(title) + r"(.*?)(?:\n[ \t]*\n[ \t]*\n|\Z)",
                  text, re.S)
    if not m:
        return None
    body = m.group(1)
    if re.search(r"\bNo\s+\w+\s+(?:were|was)\s+\w+", body, re.I):
        return 0
    rows = 0
    for line in body.splitlines():
        parts = line.split()
        if len(parts) < 3 or set(line.strip()) <= set("-*"):
            continue
        numeric = sum(1 for p in parts[1:] if _is_number(p))
        # a data row is an id followed by mostly numbers; header rows are words
        if numeric >= 2:
            rows += 1
    return rows


def _is_number(token: str) -> bool:
    try:
        float(token)
    except ValueError:
        return False
    return True


def lid_performance(text: str) -> list[dict]:
    """Rows of the LID Performance Summary, if the report contains one.

    Parsed from text because the C API does not expose this table (see
    ``openswmm/engine/_report.py``: "Sections not covered ... LID Performance").
    Columns follow SWMM 5.2+: subcatchment, LID control, then inflow / evap /
    infil / surface-outflow / drain-outflow / initial- and final-storage, all
    as depths in the project's unit system.
    """
    m = re.search(r"LID Performance Summary(.*?)(?:\n\s*\n\s*\*{4,}|\Z)",
                  text, re.S)
    if not m:
        return []
    cols = ["inflow", "evap", "infil", "surface_outflow", "drain_outflow",
            "initial_storage", "final_storage", "continuity_err"]
    rows: list[dict] = []
    for line in m.group(1).splitlines():
        parts = line.split()
        if len(parts) < 4 or set(line.strip()) <= set("-"):
            continue
        nums, labels = [], []
        for p in parts:
            try:
                nums.append(float(p))
            except ValueError:
                if not nums:            # labels precede the numeric columns
                    labels.append(p)
        if len(labels) < 2 or not nums:
            continue
        row = {"subcatchment": labels[0], "lid": " ".join(labels[1:])}
        row.update(dict(zip(cols, nums)))
        rows.append(row)
    return rows


def errors(text: str) -> list[str]:
    """ERROR / WARNING lines the engine emitted, deduplicated in order."""
    seen: dict[str, None] = {}
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("ERROR") or s.startswith("WARNING"):
            seen.setdefault(s[:200], None)
    return list(seen)


if __name__ == "__main__":
    from . import use_utf8_stdio
    use_utf8_stdio()
    import json
    import sys
    print(json.dumps(parse(sys.argv[1]), indent=2))
