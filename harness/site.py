#!/usr/bin/env python3
"""Static dashboard generation for GitHub Pages.

Self-contained HTML — no external stylesheets, scripts, or fonts, because the
published site must render from a plain artifact deploy and keep working when
a CDN does not. Structure:

    /                        scoreboard: badges, per-suite results, census
    /runs/<stamp>/           immutable per-run report
    /tags/<tag>/             every case carrying a tag, and how it scored
    /badges/*.json           shields.io endpoints

The scoreboard reports **verification and regression separately** and labels
every figure with the reference class it came from. A number that mixes the
two would read as an accuracy claim the corpus cannot support, which is the
one thing this page must not do.
"""
from __future__ import annotations

import datetime
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from . import scoring

CSS = """
:root{--bg:#fff;--fg:#1a1d21;--muted:#5a6472;--line:#e3e7ec;--card:#f7f9fb;
--pass:#1a7f37;--fail:#c1121f;--warn:#b45309;--skip:#5a6472;--accent:#0b5fff}
@media (prefers-color-scheme:dark){:root{--bg:#0f1216;--fg:#e6e9ee;
--muted:#9aa5b4;--line:#242a33;--card:#161b22;--pass:#3fb950;--fail:#f85149;
--warn:#d29922;--skip:#8b949e;--accent:#58a6ff}}
*{box-sizing:border-box}
body{margin:0;padding:2rem 1.25rem 4rem;background:var(--bg);color:var(--fg);
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto}
h1{font-size:1.7rem;margin:0 0 .25rem}
h2{font-size:1.15rem;margin:2.5rem 0 .75rem;padding-bottom:.35rem;
border-bottom:1px solid var(--line)}
h3{font-size:1rem;margin:1.5rem 0 .5rem}
a{color:var(--accent)}
.sub{color:var(--muted);margin:0 0 1.5rem}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
gap:.75rem;margin:1.25rem 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:.9rem 1rem}
.card .k{font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;
color:var(--muted)}
.card .v{font-size:1.5rem;font-weight:600;margin-top:.15rem}
.card .n{font-size:.75rem;color:var(--muted);margin-top:.2rem}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{text-align:left;padding:.45rem .6rem;border-bottom:1px solid var(--line);
vertical-align:top}
th{font-weight:600;color:var(--muted);font-size:.78rem;text-transform:uppercase;
letter-spacing:.03em}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}
.v-PASS,.v-BASELINE-PASS{color:var(--pass);font-weight:600}
.v-FAIL,.v-BASELINE-FAIL,.v-ERROR,.v-XPASS{color:var(--fail);font-weight:600}
.v-SKIP,.v-UNAVAILABLE,.v-XFAIL{color:var(--skip)}
code{background:var(--card);padding:.1rem .3rem;border-radius:4px;font-size:.85em}
.tags a{display:inline-block;background:var(--card);border:1px solid var(--line);
border-radius:999px;padding:.15rem .6rem;margin:.15rem .2rem .15rem 0;
font-size:.82rem;text-decoration:none}
.note{background:var(--card);border-left:3px solid var(--accent);
padding:.75rem 1rem;border-radius:0 6px 6px 0;color:var(--muted);
font-size:.88rem;margin:1rem 0}
footer{margin-top:3rem;color:var(--muted);font-size:.82rem}
"""


def _page(title: str, body: str, depth: int = 0) -> str:
    # depth 0 is the scoreboard itself: a breadcrumb back to the page you are
    # already on is noise.
    crumb = (f"<p class=sub><a href='{'../' * depth}index.html'>"
             "&larr; OpenSWMM Benchmarks</a></p>") if depth else ""
    return (f"<!doctype html><html lang=en><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{CSS}</style>"
            f"<body><div class=wrap>{crumb}{body}"
            f"<footer>Generated {datetime.datetime.now():%Y-%m-%d %H:%M}. "
            f"Verification counts only cases with an exact solution; every "
            f"other figure is a regression or agreement result, not an "
            f"accuracy claim.</footer></div></body></html>")


def _card(k: str, v, note: str = "") -> str:
    n = f"<div class=n>{html.escape(note)}</div>" if note else ""
    return (f"<div class=card><div class=k>{html.escape(k)}</div>"
            f"<div class=v>{html.escape(str(v))}</div>{n}</div>")


def _verdict(v: str) -> str:
    return f"<span class='v-{html.escape(v)}'>{html.escape(v)}</span>"


def _counts_table(cells: list[dict]) -> str:
    by_suite: dict[str, Counter] = defaultdict(Counter)
    for c in cells:
        by_suite[c.get("_suite", "?")][c.get("verdict", "?")] += 1
    verdicts = [v for v in scoring.VERDICTS
                if any(v in c for c in by_suite.values())]
    head = "".join(f"<th class=num>{v}</th>" for v in verdicts)
    rows = ""
    for suite, counter in sorted(by_suite.items()):
        cells_html = "".join(
            f"<td class=num>{counter.get(v, 0) or ''}</td>" for v in verdicts)
        rows += (f"<tr><td><code>{html.escape(suite)}</code></td>"
                 f"<td class=num>{sum(counter.values())}</td>{cells_html}</tr>")
    return (f"<div class=scroll><table><tr><th>suite</th><th class=num>cells</th>"
            f"{head}</tr>{rows}</table></div>")


def _failures_table(cells: list[dict], limit: int = 40) -> str:
    bad = [c for c in cells if c.get("verdict") in scoring.GATING]
    if not bad:
        return "<p class=note>No failing cells in this run.</p>"
    rows = ""
    for c in bad[:limit]:
        worst = c.get("max_rel", c.get("continuity_err", ""))
        worst = f"{worst:.3e}" if isinstance(worst, float) else html.escape(str(worst))
        rows += (f"<tr><td><code>{html.escape(str(c.get('case','')))}</code></td>"
                 f"<td>{html.escape(str(c.get('solver', c.get('pair',''))))}</td>"
                 f"<td>{_verdict(c.get('verdict','?'))}</td>"
                 f"<td class=num>{worst}</td>"
                 f"<td>{html.escape(str(c.get('note',''))[:110])}</td></tr>")
    more = (f"<tr><td colspan=5>… {len(bad) - limit} more</td></tr>"
            if len(bad) > limit else "")
    return (f"<div class=scroll><table><tr><th>case</th><th>engine / pair</th>"
            f"<th>verdict</th><th class=num>worst</th><th>note</th></tr>"
            f"{rows}{more}</table></div>")


def _all_cells(envelopes: list[dict]) -> list[dict]:
    out = []
    for env in envelopes:
        for cell in env.get("cells", []):
            out.append({**cell, "_suite": env.get("suite", "?")})
    return out


def _census() -> tuple[Counter, int]:
    try:
        from . import corpus
        cases = corpus.load()
        return Counter(t for c in cases for t in c.tags), len(cases)
    except Exception:
        return Counter(), 0


def build_site(envelopes: list[dict], dest: Path) -> list[Path]:
    """Render the dashboard. Returns every file written."""
    dest = Path(dest)
    (dest / "badges").mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    cells = _all_cells(envelopes)
    tag_counts, n_cases = _census()

    badge_map = scoring.badges(envelopes, corpus_count=n_cases or None)
    written += scoring.write_badges(dest / "badges", badge_map)

    truth = [c for c in cells if scoring.is_truth(c.get("reference_class", ""))]
    regression = [c for c in cells
                  if not scoring.is_truth(c.get("reference_class", ""))]
    failing = [c for c in cells if c.get("verdict") in scoring.GATING]

    cards = "".join([
        _card("Corpus", f"{n_cases:,}", "models, tagged and validated"),
        _card("Verification", badge_map.get("verification", {}).get("message", "—"),
              "exact-solution cases only"),
        _card("Regression", badge_map.get("regression", {}).get("message", "—"),
              "parity and baseline drift"),
        _card("Failing cells", f"{len(failing):,}", "across all suites"),
    ])

    engines_seen = sorted({env.get("engine_sha", "") for env in envelopes} - {""})
    body = [
        "<h1>OpenSWMM Benchmarks</h1>",
        "<p class=sub>Engine-agnostic regression and verification for "
        "SWMM-compatible engines.</p>",
        f"<div class=cards>{cards}</div>",
        "<div class=note><strong>Verification is not regression.</strong> "
        f"{len(truth):,} cell(s) here are graded against an exact solution and "
        f"can show an engine is <em>wrong</em>. The other {len(regression):,} "
        "compare engines to each other or to a pinned baseline: they show that "
        "results <em>differ</em>, not which is right.</div>",
        "<h2>Results by suite</h2>", _counts_table(cells),
        "<h2>Failures</h2>", _failures_table(cells),
    ]

    if tag_counts:
        links = "".join(
            f"<a href='tags/{html.escape(t)}/index.html'>{html.escape(t)} "
            f"<b>{n}</b></a>" for t, n in tag_counts.most_common())
        body += ["<h2>Corpus by tag</h2>", f"<div class=tags>{links}</div>"]

    if engines_seen:
        body.append("<h2>Engines in this run</h2><p>" + ", ".join(
            f"<code>{html.escape(s)}</code>" for s in engines_seen) + "</p>")

    index = dest / "index.html"
    index.write_text(_page("OpenSWMM Benchmarks", "".join(body)),
                     encoding="utf-8")
    written.append(index)

    written += _write_run_pages(envelopes, dest)
    written += _write_tag_pages(tag_counts, cells, dest)
    return written


def _write_run_pages(envelopes: list[dict], dest: Path) -> list[Path]:
    written = []
    for env in envelopes:
        suite = str(env.get("suite", "run")).replace("/", "_")
        stamp = str(env.get("timestamp", ""))[:19].replace(":", "").replace("-", "")
        sha = env.get("engine_sha") or "nosha"
        d = dest / "runs" / f"{stamp}_{suite}@{sha}"
        d.mkdir(parents=True, exist_ok=True)
        cells = _all_cells([env])
        body = [
            f"<h1>{html.escape(str(env.get('suite','?')))}</h1>",
            f"<p class=sub>engine <code>{html.escape(sha)}</code> · "
            f"{html.escape(str(env.get('timestamp','')))} · "
            f"{len(cells)} cell(s)</p>",
            "<h2>Verdicts</h2>", _counts_table(cells),
            "<h2>Failures</h2>", _failures_table(cells, limit=200),
        ]
        p = d / "index.html"
        p.write_text(_page(f"{env.get('suite','run')} — {stamp}",
                           "".join(body), depth=2), encoding="utf-8")
        written.append(p)
        raw = d / "scores.json"
        raw.write_text(json.dumps(env, indent=2, default=str), encoding="utf-8")
        written.append(raw)
    return written


def _write_tag_pages(tag_counts: Counter, cells: list[dict],
                     dest: Path) -> list[Path]:
    if not tag_counts:
        return []
    try:
        from . import corpus
        cases = corpus.load()
    except Exception:
        return []

    by_case: dict[str, list[dict]] = defaultdict(list)
    for c in cells:
        by_case[str(c.get("case", ""))].append(c)

    written = []
    for tag in tag_counts:
        d = dest / "tags" / tag
        d.mkdir(parents=True, exist_ok=True)
        rows = ""
        for case in sorted((c for c in cases if tag in c.tags),
                           key=lambda c: c.id):
            verdicts = {x.get("verdict") for x in by_case.get(case.id, [])}
            state = ("—" if not verdicts else
                     " ".join(_verdict(v) for v in sorted(verdicts)))
            rows += (f"<tr><td><code>{html.escape(case.id)}</code></td>"
                     f"<td>{html.escape(case.reference_class)}</td>"
                     f"<td>{html.escape(', '.join(sorted(case.tags)))}</td>"
                     f"<td>{state}</td></tr>")
        body = [f"<h1>{html.escape(tag)}</h1>",
                f"<p class=sub>{tag_counts[tag]} case(s) carry this tag</p>",
                f"<div class=scroll><table><tr><th>case</th><th>reference</th>"
                f"<th>tags</th><th>latest verdicts</th></tr>{rows}</table></div>"]
        p = d / "index.html"
        p.write_text(_page(f"tag: {tag}", "".join(body), depth=2),
                     encoding="utf-8")
        written.append(p)
    return written
