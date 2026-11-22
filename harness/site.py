#!/usr/bin/env python3
"""Static dashboard generation for GitHub Pages.

The site loads nothing from another host: the HydroCouple theme's tokens,
fonts and logo are copied from the manual's vendored theme
(``docs/manual/_hydrocouple/static/hc``) into ``assets/hc/``, beside the
dashboard's own stylesheet and script (``harness/site_assets``). Charts are
inline SVG drawn here (harness.charts). Layout:

    /                          overview: the latest run, every job with its
                               manifest and artifact links, failures by
                               mechanism, runtime, mass balance, stability,
                               parity, platform agreement, corpus by tag
    /runs/<stamp>_<suite>[_<platform>][_<K>-of-<N>]@<sha>/
                               one envelope: its run, the same sections, and
                               every cell in a sortable, filterable table
    /cases/<id>/               one case on every engine and platform
    /tags/<tag>/               every case carrying a tag, and how it scored
    /trends/                   history across runs (harness.history)
    /badges/*.json             shields.io endpoints
    /docs/                     the manual (built by the Publish workflow)

The scoreboard reports **verification and regression separately** and labels
every figure with the reference class it came from. A number that mixes the
two would read as an accuracy claim the corpus cannot support, which is the
one thing this page must not do.
"""
from __future__ import annotations

import datetime
import html
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from . import charts, metrics, scoring

E = html.escape
REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent / "site_assets"
THEME = REPO_ROOT / "docs" / "manual" / "_hydrocouple"
REPO_URL = "https://github.com/HydroCouple/openswmm.engine.benchmarks"
ENGINE_URL = "https://github.com/HydroCouple/openswmm.engine"
MANUAL_ID = "openswmm.engine.benchmarks"

#: Engine series colors follow the engine on every chart (CSS .s1/.s2/.s3).
SERIES_CLASS = {metrics.V6: "s1", metrics.LEGACY: "s2"}

WALL_EDGES = [0.1, 0.3, 1, 3, 10, 30, 100, 300]
CONT_EDGES = [0.01, 0.1, 0.5, 1, 5, 10]
NC_EDGES = [1e-9, 1, 5, 20, 50]
REL_EDGES = [1e-15, 1e-12, 1e-9, 1e-6, 1e-3]
RSS_EDGES = [16, 64, 256, 1024, 4096]


# ── assets and page shell ──────────────────────────────────────────────────

def _copy_assets(dest: Path) -> list[Path]:
    """Theme tokens, fonts, logo, and the dashboard's stylesheet and script."""
    out = dest / "assets"
    hc = out / "hc"
    (hc / "fonts").mkdir(parents=True, exist_ok=True)
    written = []
    src = THEME / "static" / "hc"
    for name in ("hc-tokens.css", "hc-fonts.css", "hydrocouple_logo.png"):
        if (src / name).exists():
            shutil.copyfile(src / name, hc / name)
            written.append(hc / name)
    for f in sorted((src / "fonts").glob("*")) if (src / "fonts").is_dir() else []:
        shutil.copyfile(f, hc / "fonts" / f.name)
        written.append(hc / "fonts" / f.name)
    for name in ("dashboard.css", "dashboard.js"):
        shutil.copyfile(ASSETS / name, out / name)
        written.append(out / name)
    return written


def _manuals() -> dict:
    try:
        reg = json.loads((THEME / "manuals.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    groups = []
    for g in reg.get("groups", []):
        ms = [dict(m, current=m["id"] == MANUAL_ID) for m in g.get("manuals", [])
              if m.get("published") or m["id"] == MANUAL_ID]
        if ms:
            groups.append({"title": g["title"], "manuals": ms})
    reg["groups"] = groups
    return reg


_PREPAINT = ("try{var m=localStorage.getItem('mode')||'auto';var d=document.documentElement;"
             "d.dataset.mode=m;d.dataset.theme=m==='auto'?(matchMedia('(prefers-color-scheme: dark)')"
             ".matches?'dark':'light'):m}catch(e){}")

_ICON_GITHUB = ("<svg viewBox='0 0 16 16' width=18 height=18 aria-hidden=true><path fill=currentColor "
                "d='M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82"
                "-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63"
                "-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64"
                "-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2"
                "-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82"
                " 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46"
                ".55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z'/></svg>")
_ICON_MODE = ("<svg viewBox='0 0 24 24' width=18 height=18 aria-hidden=true fill=none stroke=currentColor "
              "stroke-width=2 stroke-linecap=round stroke-linejoin=round>"
              "<g class=i-light><circle cx=12 cy=12 r=4 /><path d='M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 "
              "17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4'/></g>"
              "<g class=i-dark><path d='M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z'/></g>"
              "<g class=i-auto><circle cx=12 cy=12 r=9 /><path d='M12 3v18' /><path d='M12 3a9 9 0 010 "
              "18z' fill=currentColor /></g></svg>")


def _topbar(r: str, active: str) -> str:
    reg = _manuals()
    nav = [("overview", "index.html", "Overview"), ("runs", "index.html#runs", "Runs"),
           ("performance", "index.html#performance", "Performance"),
           ("trends", "trends/index.html", "Trends"), ("docs", "docs/index.html", "Manual")]
    links = "".join(
        f"<a href='{r}{href}'{' aria-current=page' if key == active else ''}>{E(label)}</a>"
        for key, href, label in nav)
    menu = ""
    if reg.get("groups"):
        groups = "".join(
            f"<div class=manuals__group><p class=manuals__heading>{E(g['title'])}</p><ul>"
            + "".join(f"<li><a class='manuals__item{' is-current' if m['current'] else ''}' "
                      f"href='{E(m['url'])}'><span class=manuals__title>{E(m['title'])}</span>"
                      f"<span class=manuals__kind>{E(m['kind'])}</span></a></li>"
                      for m in g["manuals"]) + "</ul></div>"
            for g in reg["groups"])
        foot = "".join(f"<a href='{E(x['url'])}'>{E(x['title'])}</a>" for x in reg.get("links", []))
        menu = (f"<details class=manuals><summary>Documentation</summary>"
                f"<div class=manuals__menu><div class=manuals__groups>{groups}</div>"
                f"<div class=manuals__footer>{foot}</div></div></details>")
    home = E(reg.get("home", "https://www.hydrocouple.org/"))
    return (
        "<header class=topbar><div class='wrap topbar__inner'>"
        f"<div class=hc-brand><a class=hc-brand__home href='{home}' title='HydroCouple home'>"
        f"<img class=hc-brand__mark src='{r}assets/hc/hydrocouple_logo.png' alt='' width=30 height=30>"
        "<span class=hc-brand__name>HydroCouple</span></a><span class=hc-brand__sep aria-hidden=true></span>"
        f"<a class=hc-brand__project href='{r}index.html'>OpenSWMM Benchmarks</a></div>"
        f"<nav class=topnav aria-label=Dashboard>{links}</nav>"
        f"<div class=topbar__end>{menu}"
        "<button class=mode-toggle type=button aria-label='Color mode'>" + _ICON_MODE + "</button>"
        f"<a class=icon-btn href='{REPO_URL}' aria-label='GitHub repository'>{_ICON_GITHUB}</a>"
        "</div></div></header>")


def _footer(r: str, generated: str) -> str:
    reg = _manuals()
    links = "".join(f"<a href='{E(x['url'])}'>{E(x['title'])}</a>" for x in reg.get("links", []))
    return (
        "<footer class=footer><div class=wrap>"
        f"<div class=footer__brand><img src='{r}assets/hc/hydrocouple_logo.png' alt='' width=24 height=24>"
        "<span>OpenSWMM Benchmarks</span></div>"
        f"<nav class=footer__links aria-label=HydroCouple><a href='{E(reg.get('home', 'https://www.hydrocouple.org/'))}'>"
        f"hydrocouple.org</a>{links}<a href='{REPO_URL}'>Source</a><a href='{r}docs/index.html'>Manual</a></nav>"
        f"<p class=footer__note>Generated {E(generated)}. Verification counts only cases with an "
        "exact solution; every other figure is a regression or agreement result, not an accuracy "
        "claim. Runtimes are from shared CI runners: compare them within a run, and across runs only "
        "on the same CPU model.</p></div></footer>")


def _page(title: str, body: str, depth: int = 0, *, active: str = "",
          description: str = "") -> str:
    r = "../" * depth
    generated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    desc = (f"<meta name=description content='{E(description)}'>" if description else "")
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{E(title)}</title>{desc}<script>{_PREPAINT}</script>"
        f"<link rel=stylesheet href='{r}assets/hc/hc-fonts.css'>"
        f"<link rel=stylesheet href='{r}assets/hc/hc-tokens.css'>"
        f"<link rel=stylesheet href='{r}assets/dashboard.css'>"
        f"<link rel=icon href='{r}assets/hc/hydrocouple_logo.png'>"
        f"<script src='{r}assets/dashboard.js' defer></script></head>"
        f"<body>{_topbar(r, active)}<main>{body}</main>{_footer(r, generated)}</body></html>")


# ── small pieces ───────────────────────────────────────────────────────────

def _verdict(v: str) -> str:
    return f"<span class='v v-{E(v)}'>{E(v)}</span>"


def _chip(text: str, cls: str = "") -> str:
    return f"<span class='chip {cls}'>{E(text)}</span>"


def _status(ok: bool | None, text: str) -> str:
    cls, icon = (("none", "–") if ok is None else ("ok", "✓") if ok else ("bad", "✕"))
    return f"<span class='status status--{cls}'><span aria-hidden=true>{icon}</span>{E(text)}</span>"


def _tile(k: str, v, note: str = "", status: str = "") -> str:
    return (f"<div class=tile><div class=tile__k>{E(k)}</div>"
            f"<div class=tile__v>{E(str(v))}</div>"
            + (f"<div class=tile__s>{status}</div>" if status else "")
            + (f"<div class=tile__n>{E(note)}</div>" if note else "") + "</div>")


def _num(v, fmt: str = "{:,.3g}", cls: str = "num") -> str:
    if v is None or v == "":
        return f"<td class={cls} data-v=''>—</td>"
    try:
        text = fmt.format(v)
    except (ValueError, TypeError):
        text = str(v)
    return f"<td class={cls} data-v='{E(str(v))}'>{E(text)}</td>"


def _pct(v) -> str:
    return _num(v, "{:.2f}")


def _secs(v) -> str:
    return f"<td class=num data-v='{'' if v is None else v}'>{E(charts.fmt_seconds(v))}</td>"


def _group_legend() -> str:
    items = "".join(f"<li><span class='key key--rect g-{k}'></span>{E(metrics.GROUP_LABEL[k])}</li>"
                    for k in metrics.GROUPS)
    return f"<ul class=legend>{items}</ul>"


def _segbar(cells: list[dict]) -> str:
    return charts.segbar(metrics.group_counts(cells), metrics.GROUP_LABEL)


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(text)).strip("_") or "_"


def _run_slug(env: dict) -> str:
    suite = str(env.get("suite", "run")).replace("/", "_")
    stamp = str(env.get("timestamp", ""))[:19].replace(":", "").replace("-", "")
    sha = env.get("engine_sha") or "nosha"
    # Sharded jobs on several OSes publish one envelope each for the same
    # suite and SHA, often within the same second; keyed on stamp alone
    # they overwrite each other's page.
    where = [str(x) for x in (env.get("platform"), env.get("shard")) if x]
    tag = "".join(f"_{x}" for x in where).replace("/", "-of-")
    return f"{stamp}_{suite}{tag}@{sha}"


def _engine_class(eid: str, order: list[str]) -> str:
    """Slots 1 and 2 belong to the two parity engines everywhere; any other
    engine takes the next slot in the order it appears (the stylesheet
    defines all eight)."""
    if eid in SERIES_CLASS:
        return SERIES_CLASS[eid]
    others = [e for e in order if e not in SERIES_CLASS]
    return f"s{min(3 + others.index(eid), 8)}" if eid in others else "s3"


def _ago(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        t = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    if t.tzinfo is None:
        return t.strftime("%Y-%m-%d %H:%M")
    return t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _coverage_note(env: dict) -> str:
    coverage = env.get("coverage")
    if not coverage:
        return ""
    return ("<div class=note><strong>" + E(str(env.get("suite", ""))) +
            " coverage:</strong> " + E(str(coverage.get("executed", 0))) +
            "/" + E(str(coverage.get("requested", 0))) +
            " requested scenarios executed; " + E(str(coverage.get("observed_compared", 0))) +
            " compared with observations; " + E(str(coverage.get("regression_checked", 0))) +
            " checked against own baselines. Numerical PASS does not establish observed validation.</div>")


def _census() -> tuple[Counter, int, dict]:
    try:
        from . import corpus
        cases = corpus.load()
        return (Counter(t for c in cases for t in c.tags), len(cases),
                {c.id: c for c in cases})
    except Exception:
        return Counter(), 0, {}


# ── the run manifest ───────────────────────────────────────────────────────

def _artifact_links(env: dict, r: str, *, run_page: bool = True) -> str:
    m = env.get("_run") or {}
    arts = m.get("artifacts") or {}
    links = []
    if run_page:
        links.append((f"{r}runs/{env['_slug']}/index.html", "Run page", True))
    links += [
        (m.get("url"), "Workflow run", bool(m.get("url"))),
        (m.get("job_url"), "Job log", bool(m.get("job_url"))),
        (arts.get("evidence"), "Evidence artifact", bool(arts.get("evidence"))),
        ((m.get("url") or "") + "#artifacts", "All artifacts", bool(m.get("url"))),
        (f"{r}runs/{env['_slug']}/scores.json", "scores.json", True),
    ]
    return "<div class=links>" + "".join(
        f"<a class=linkbtn href='{E(href)}'>{E(label)}</a>" if ok else
        f"<span class=linkbtn aria-disabled=true title='not recorded for this run'>{E(label)}</span>"
        for href, label, ok in links) + "</div>"


def _manifest_grid(env: dict) -> str:
    m = env.get("_run") or {}
    if not m:
        return ("<p class=muted>This envelope came without a run manifest "
                "(written by run_regression.py since 2026-11-22), so only the "
                "envelope's own fields are known.</p>")
    eng, h = m.get("engine") or {}, m.get("host") or {}
    commit = (f"<a href='{ENGINE_URL}/commit/{E(eng['sha_full'])}'><code>{E(eng.get('sha') or '')}</code></a>"
              if eng.get("sha_full") else f"<code>{E(eng.get('sha') or env.get('engine_sha') or '—')}</code>")
    versions = "; ".join(f"{k}: {v}" for k, v in (eng.get("versions") or {}).items() if v)
    rows = [
        ("Workflow", " · ".join(str(x) for x in (m.get("workflow"), m.get("event"),
                                                 f"attempt {m['attempt']}" if m.get("attempt") else None) if x)),
        ("Job", m.get("job")), ("Started", _ago(m.get("started"))),
        ("Finished", _ago(m.get("finished")) if m.get("finished") else "did not finish"),
        ("Duration", charts.fmt_seconds(m.get("duration_s")) if m.get("duration_s") is not None else "—"),
        ("Exit code", m.get("exit_code")),
        ("Engine", None), ("Commit", eng.get("subject")), ("Committed", _ago(eng.get("commit_date"))),
        ("Engine versions", versions or None),
        ("Host", " · ".join(str(x) for x in (h.get("os"), h.get("release"), h.get("machine")) if x)),
        ("CPU", f"{h.get('cpu') or 'unknown'} · {h.get('cpu_count') or '?'} logical"),
        ("Memory", f"{h['memory_gb']} GiB" if h.get("memory_gb") else None),
        ("Python", f"{h.get('python') or '?'} · numpy {h.get('numpy') or '?'}"),
        ("Runner", h.get("runner")),
        ("Benchmarks", m.get("benchmarks_sha")),
        ("Tier · budget", " · ".join(str(x) for x in (m.get("tier"), f"--max-wall {m['max_wall']:g} s"
                                                     if m.get("max_wall") else None) if x)),
        ("Arguments", " ".join(m.get("args") or []) or None),
    ]
    items = []
    for k, v in rows:
        if k == "Engine":
            ref = E(eng.get("ref") or "")
            items.append(f"<div><dt>Engine</dt><dd>{ref + ' @ ' if ref else ''}{commit}"
                         f"{' (modified tree)' if eng.get('dirty') else ''}</dd></div>")
            continue
        if v in (None, ""):
            continue
        val = f"<code>{E(str(v))}</code>" if k in ("Benchmarks", "Arguments") else E(str(v))
        wide = " class=wide" if k in ("Arguments", "Engine versions") else ""
        items.append(f"<div{wide}><dt>{E(k)}</dt><dd>{val}</dd></div>")
    crashed = m.get("crashed") or []
    if crashed:
        items.append("<div><dt>Crashed</dt><dd>" + "<br>".join(E(c) for c in crashed) + "</dd></div>")
    return f"<dl class=facts-grid>{''.join(items)}</dl>"


def _run_stats(cells: list[dict]) -> str:
    runs = [c for c in cells if metrics.is_engine_run(c)]
    w = metrics.summary_stats([metrics.wall(c) for c in runs if metrics.wall(c) is not None])
    cont = metrics.continuity(cells)
    stab = metrics.stability(cells)
    parts = [f"{len(runs):,} engine run(s)"]
    if w["n"]:
        parts.append(f"engine time {charts.fmt_seconds(w['total'])} "
                     f"(median {charts.fmt_seconds(w['median'])}, max {charts.fmt_seconds(w['max'])})")
    if cont["worst"]:
        parts.append(f"worst |continuity| {abs(cont['worst'][0]['continuity_err']):.2f} %")
    if stab["runs"]:
        parts.append(f"{100 * stab['stable'] / len(stab['runs']):.1f} % stable")
    return "<p class=muted>" + " · ".join(E(p) for p in parts) + "</p>"


def _verdict_chips(cells: list[dict]) -> str:
    c = metrics.counts(cells)
    return "<p class=chips>" + " ".join(
        f"{_verdict(v)} <b>{c[v]:,}</b>" for v in scoring.VERDICTS if c.get(v)) + "</p>"


def _run_details(env: dict, r: str, open_: bool = False) -> str:
    cells = metrics.cells_of([env])
    m = env.get("_run") or {}
    plat, shard = metrics.platform_of(env), env.get("shard")
    gating = sum(1 for c in cells if c.get("verdict") in scoring.GATING)
    dur = charts.fmt_seconds(m["duration_s"]) if m.get("duration_s") is not None else (
        "unfinished" if m and not m.get("finished") else "—")
    return (
        f"<details class=run id='run-{E(env['_slug'])}'{' open' if open_ else ''}><summary>"
        "<span class=chev aria-hidden=true>›</span>"
        f"<span class=run__name><b>{E(str(env.get('suite', '?')))}</b>"
        f"{_chip(plat)}{_chip('shard ' + shard) if shard else ''}</span>"
        f"<span class=run__bar>{_segbar(cells)}</span>"
        f"<span class=run__meta><code>{E(env.get('engine_sha') or '—')}</code>"
        f"<span>{len(cells):,} cells</span><span>{E(dur)}</span>"
        + (_status(False, f"{gating:,} gating") if gating else _status(True, "no gating cells"))
        + "</span></summary><div class=run__body>"
        + (f"<p class=run__desc>{E(m['description'])}</p>" if m.get("description") else "")
        + _artifact_links(env, r) + _verdict_chips(cells) + _run_stats(cells)
        + _manifest_grid(env) + _coverage_note(env) + "</div></details>")


# ── sections ───────────────────────────────────────────────────────────────

def _section(id_: str, title: str, lede: str, body: str) -> str:
    return (f"<section class=block id='{E(id_)}'><h2>{E(title)}</h2>"
            + (f"<p class=block__lede>{lede}</p>" if lede else "") + body + "</section>")


def _suite_table(envelopes: list[dict], r: str) -> str:
    groups = defaultdict(list)
    for env in envelopes:
        groups[(env.get("suite", "?"), metrics.platform_of(env))].append(env)
    rows = []
    for (suite, plat), envs in sorted(groups.items()):
        cells = metrics.cells_of(envs)
        g = metrics.group_counts(cells)
        t = sum(metrics.wall(c) or 0 for c in cells if metrics.is_engine_run(c))
        pages = " ".join(
            f"<a href='{r}runs/{E(e['_slug'])}/index.html'>{E(e.get('shard') or 'run')}</a>"
            for e in sorted(envs, key=lambda e: e.get("shard") or ""))
        rows.append(
            f"<tr><td><code>{E(suite)}</code></td><td>{E(plat)}</td>"
            f"<td class=num data-v={len(cells)}>{len(cells):,}</td><td class=barcell>{_segbar(cells)}</td>"
            + "".join(f"<td class=num data-v={g[k]}>{g[k]:,}</td>" for k in metrics.GROUPS)
            + f"<td class=num data-v={t:.3f}>{E(charts.fmt_seconds(t) if t else '—')}</td>"
              f"<td>{pages}</td></tr>")
    head = ("<tr><th data-sort>suite</th><th data-sort>platform</th><th class=num data-sort=num>cells</th>"
            "<th>verdicts</th>" + "".join(f"<th class=num data-sort=num>{E(metrics.GROUP_LABEL[k])}</th>"
                                          for k in metrics.GROUPS)
            + "<th class=num data-sort=num>engine time</th><th>run pages</th></tr>")
    return (_group_legend() + "<div class='card scroll'><table class='data'>"
            f"<thead>{head}</thead><tbody>{''.join(rows)}</tbody></table></div>")


def _mechanisms(cells: list[dict], r: str, case_pages: set[str], limit: int = 25) -> str:
    fams = metrics.mechanisms(cells)
    if not fams:
        return "<p class=note>No gating cells.</p>"
    out = []
    for fam, cs in fams[:limit]:
        where = Counter((c["_suite"], c["_platform"]) for c in cs)
        chips = " ".join(_chip(f"{s} · {p} · {n}") for (s, p), n in sorted(where.items()))
        verdicts = " ".join(_verdict(v) for v in sorted({c.get("verdict") for c in cs}))
        rows = "".join(
            f"<tr><td>{_case_link(c['case'], r, case_pages)}</td>"
            f"<td>{E(str(c.get('solver') or c.get('pair') or ''))}</td><td class=nw>{E(c['_platform'])}</td>"
            f"<td>{_verdict(c.get('verdict', '?'))}</td><td class=note-cell>{E(str(c.get('note') or ''))}</td></tr>"
            for c in sorted(cs, key=lambda c: (c["case"], c["_platform"]))[:150])
        more = f"<p class=muted>… {len(cs) - 150:,} more on the run pages.</p>" if len(cs) > 150 else ""
        out.append(
            f"<details class=mech><summary><span class=chev aria-hidden=true>›</span>"
            f"<span class=mech__n>{len(cs):,}</span><span class=mech__text>{E(fam)}</span>"
            f"<span class=mech__where>{verdicts}</span></summary><div class=mech__body>"
            f"<p class=chips>{chips}</p><div class=scroll><table class=data><thead><tr>"
            "<th data-sort>case</th><th data-sort>engine / pair</th><th data-sort>platform</th>"
            "<th data-sort>verdict</th><th>note</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div>{more}</div></details>")
    rest = sum(len(cs) for _, cs in fams[limit:])
    if rest:
        out.append(f"<p class=muted>{len(fams) - limit:,} smaller groups ({rest:,} cells) are "
                   "on the run pages.</p>")
    return "".join(out)


def _case_link(case: str, r: str, case_pages: set[str]) -> str:
    if case in case_pages:
        return f"<a href='{r}cases/{E(_slug(case))}/index.html'><code>{E(case)}</code></a>"
    return f"<code>{E(case)}</code>"


def _performance(cells: list[dict], r: str, case_pages: set[str]) -> str:
    runs = metrics.parity_runs(cells)
    if not runs:
        return "<p class=note>No parity engine runs in this set.</p>"
    plats = sorted({c["_platform"] for c in runs})
    order = sorted({c["solver"] for c in runs}, key=lambda e: (e not in SERIES_CLASS, e))
    tiles, hists, scatters = [], [], []
    for p in plats:
        pr = [c for c in runs if c["_platform"] == p]
        series = []
        for eid in order:
            ws = [metrics.wall(c) for c in pr if c["solver"] == eid]
            if not ws:
                continue
            st = metrics.summary_stats(ws)
            tiles.append(_tile(f"{eid} · {p}", charts.fmt_seconds(st["total"]),
                               f"{st['n']:,} runs · median {charts.fmt_seconds(st['median'])} · "
                               f"p90 {charts.fmt_seconds(st['p90'])}"))
            series.append({"name": eid, "cls": _engine_class(eid, order),
                           "values": metrics.bin_counts(ws, WALL_EDGES)})
        hists.append(f"<div class=card><h3>{E(p)}</h3><p class=sub>Completed parity runs per "
                     "wall-time bin, one series per engine.</p>"
                     + charts.columns(metrics.bin_labels(WALL_EDGES), series, unit="runs",
                                      label=f"Run time distribution on {p}",
                                      x_title="engine wall time (s)") + "</div>")
        pts = metrics.speed_points(cells).get(p, [])
        if pts:
            rs = metrics.ratio_summary(pts)
            note = (f"{len(pts):,} cases. Of the {rs['n']:,} where either engine took ≥ "
                    f"{metrics.RATIO_FLOOR_S:g} s, the median {metrics.V6} ÷ {metrics.LEGACY} time is "
                    f"{rs['median']:.2f} (geometric mean {rs['geomean']:.2f}); {metrics.V6} was faster "
                    f"on {rs['faster']:,}." if rs["n"] else f"{len(pts):,} cases, all under "
                    f"{metrics.RATIO_FLOOR_S:g} s on both engines, where start-up dominates.")
            scatters.append(f"<div class=card><h3>{E(p)}: {E(metrics.V6)} against {E(metrics.LEGACY)}</h3>"
                            f"<p class=sub>{E(note)} Points below the diagonal ran faster on "
                            f"{E(metrics.V6)}.</p>"
                            + charts.scatter_loglog(pts, x_name=metrics.LEGACY, y_name=metrics.V6,
                                                    unit="s", label=f"Per-case wall time on {p}")
                            + "</div>")
    slow = sorted(runs, key=lambda c: -(metrics.wall(c) or 0))[:15]
    slow_rows = "".join(
        f"<tr><td>{_case_link(c['case'], r, case_pages)}</td><td class=nw>{E(c['solver'])}</td>"
        f"<td class=nw>{E(c['_platform'])}</td>{_secs(metrics.wall(c))}"
        f"{_num(c.get('peak_rss_mb'), '{:,.0f}')}<td>{'trimmed' if c.get('trimmed') else ''}</td></tr>"
        for c in slow)
    rss = [c for c in runs if isinstance(c.get("peak_rss_mb"), (int, float))]
    mem = ""
    if rss:
        mplats = sorted({c["_platform"] for c in rss})
        mcharts = []
        for p in mplats:
            series = [{"name": eid, "cls": _engine_class(eid, order),
                       "values": metrics.bin_counts([c["peak_rss_mb"] for c in rss
                                                     if c["_platform"] == p and c["solver"] == eid],
                                                    RSS_EDGES)}
                      for eid in order if any(c["solver"] == eid and c["_platform"] == p for c in rss)]
            mcharts.append(f"<div class=card><h3>Peak memory · {E(p)}</h3><p class=sub>Each engine "
                           "process's own peak resident memory.</p>"
                           + charts.columns(metrics.bin_labels(RSS_EDGES), series, unit="runs",
                                            label=f"Peak memory on {p}", x_title="peak RSS (MiB)")
                           + "</div>")
        missing = sorted(set(plats) - set(mplats))
        mem = ("<h3 class=subhead>Memory</h3>"
               + (f"<p class=muted>Not recorded for {E(', '.join(missing))}. Windows has no "
                  "per-process peak from the Python standard library, and envelopes written "
                  "before 2026-11-22 predate the measurement.</p>" if missing else "")
               + f"<div class=multiples>{''.join(mcharts)}</div>")
    return (f"<div class=tiles>{''.join(tiles)}</div>"
            f"<h3 class=subhead>Distribution</h3><div class=multiples>{''.join(hists)}</div>"
            + (f"<h3 class=subhead>Engine against engine</h3><div class=multiples>{''.join(scatters)}</div>"
               if scatters else "")
            + "<h3 class=subhead>Slowest runs</h3><div class='card scroll'><table class=data><thead><tr>"
              "<th data-sort>case</th><th data-sort>engine</th><th data-sort>platform</th>"
              "<th class=num data-sort=num>wall</th><th class=num data-sort=num>peak MiB</th><th></th>"
              f"</tr></thead><tbody>{slow_rows}</tbody></table></div>" + mem)


def _engine_hists(cells: list[dict], value, edges, *, unit_label: str, what: str) -> str:
    """Distributions over the parity suite's engines only: the other suites'
    solvers (2D schemes, analytic generators) answer different questions, and
    their figures stay in the tables."""
    runs = [c for c in cells if c["_suite"] == "parity" and metrics.is_engine_run(c)
            and value(c) is not None]
    if not runs:
        return ""
    plats = sorted({c["_platform"] for c in runs})
    order = sorted({c["solver"] for c in runs}, key=lambda e: (e not in SERIES_CLASS, e))[:3]
    out = []
    for p in plats:
        series = [{"name": eid, "cls": _engine_class(eid, order),
                   "values": metrics.bin_counts([value(c) for c in runs
                                                 if c["_platform"] == p and c["solver"] == eid], edges)}
                  for eid in order if any(c["solver"] == eid and c["_platform"] == p for c in runs)]
        out.append(f"<div class=card><h3>{E(p)}</h3><p class=sub>{E(what)}</p>"
                   + charts.columns(metrics.bin_labels(edges), series, unit="runs",
                                    label=f"{what} on {p}", x_title=unit_label) + "</div>")
    return f"<div class=multiples>{''.join(out)}</div>"


def _mass_balance(cells: list[dict], r: str, case_pages: set[str]) -> str:
    cont = metrics.continuity(cells)
    if not cont["graded"]:
        return "<p class=note>No continuity errors reported in this set.</p>"
    hist = _engine_hists(
        [c for c in cells if not c.get("expected_high_continuity")],
        lambda c: abs(c["continuity_err"]) if isinstance(c.get("continuity_err"), (int, float)) else None,
        CONT_EDGES, unit_label="|flow routing continuity error| (%)",
        what="Engine runs per |flow routing continuity error| bin.")
    rows = "".join(
        f"<tr><td>{_case_link(c['case'], r, case_pages)}</td><td class=nw>{E(c['solver'])}</td>"
        f"<td class=nw>{E(c['_platform'])}</td><td>{E(c['_suite'])}</td>{_pct(c.get('continuity_err'))}"
        f"{_pct(c.get('runoff_err'))}{_pct(c.get('groundwater_err'))}{_pct(c.get('quality_err'))}</tr>"
        for c in cont["worst"][:15])
    note = (f"<p class=muted>{cont['by_design']:,} run(s) of models tagged "
            "<code>expected_high_continuity</code> are left out: their committed legacy reports "
            "already show more than 10 % error, so the figure belongs to the model, not the engine.</p>"
            if cont["by_design"] else "")
    return (hist + note + "<h3 class=subhead>Largest errors</h3><div class='card scroll'><table class=data>"
            "<thead><tr><th data-sort>case</th><th data-sort>engine</th><th data-sort>platform</th>"
            "<th data-sort>suite</th><th class=num data-sort=num>routing %</th>"
            "<th class=num data-sort=num>runoff %</th><th class=num data-sort=num>groundwater %</th>"
            "<th class=num data-sort=num>worst quality %</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div>")


def _stability(cells: list[dict], r: str, case_pages: set[str]) -> str:
    st = metrics.stability(cells)
    if not st["runs"]:
        return "<p class=note>No routing statistics reported in this set.</p>"
    hist = _engine_hists(
        cells, lambda c: c["pct_not_converging"] if isinstance(c.get("pct_not_converging"), (int, float))
        else None, NC_EDGES, unit_label="steps not converging (%)",
        what="Engine runs per share of routing steps that did not converge.")
    rows = "".join(
        f"<tr><td>{_case_link(c['case'], r, case_pages)}</td><td class=nw>{E(c['solver'])}</td>"
        f"<td class=nw>{E(c['_platform'])}</td>{_pct(c.get('pct_not_converging'))}{_num(c.get('avg_iter'), '{:.2f}')}"
        f"{_num(c.get('min_dt'), '{:.3g}')}{_num(c.get('avg_dt'), '{:.3g}')}"
        f"{_num(c.get('links_instability'), '{:,}')}{_num(c.get('nodes_flooded'), '{:,}')}"
        f"{_num(c.get('nodes_surcharged'), '{:,}')}</tr>"
        for c in st["worst"][:15])
    return (hist + "<h3 class=subhead>Least converged</h3><div class='card scroll'><table class=data>"
            "<thead><tr><th data-sort>case</th><th data-sort>engine</th><th data-sort>platform</th>"
            "<th class=num data-sort=num>not conv. %</th><th class=num data-sort=num>avg iter</th>"
            "<th class=num data-sort=num>min dt (s)</th><th class=num data-sort=num>avg dt (s)</th>"
            "<th class=num data-sort=num>unstable links</th><th class=num data-sort=num>flooded nodes</th>"
            "<th class=num data-sort=num>surcharged nodes</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div>")


def _parity(cells: list[dict], r: str, case_pages: set[str]) -> str:
    ps = metrics.pairs(cells)
    if not ps:
        return "<p class=note>No engine pairs compared in this set.</p>"
    plats = sorted({c["_platform"] for c in ps})
    out = []
    labels = ["identical"] + metrics.bin_labels(REL_EDGES[1:], fmt=lambda x: f"{x:.0e}")
    for p in plats:
        vals = [c["max_rel"] for c in ps if c["_platform"] == p]
        counts = metrics.bin_counts(vals, REL_EDGES)        # < 1e-15 reads as identical
        out.append(f"<div class=card><h3>{E(p)}</h3><p class=sub>Compared pairs per largest "
                   "relative difference over every element, variable and period.</p>"
                   + charts.columns(labels, [{"name": "pairs", "cls": "s3", "values": counts}],
                                    unit="pairs", label=f"Parity on {p}",
                                    x_title="max relative difference") + "</div>")
    worst = sorted((c for c in ps if c["max_rel"] > 0), key=lambda c: -c["max_rel"])[:15]
    rows = "".join(
        f"<tr><td>{_case_link(c['case'], r, case_pages)}</td><td class=nw>{E(c['_platform'])}</td>"
        f"<td>{_verdict(c.get('verdict', '?'))}</td>{_num(c.get('max_rel'), '{:.2e}')}"
        f"{_num(c.get('total_over_tol'), '{:,}')}{_num(c.get('total_cells'), '{:,}')}"
        f"<td><code>{E(str(c.get('worst_var') or ''))}</code></td>"
        f"<td><code>{E(str(c.get('worst_element') or ''))}</code></td>{_num(c.get('first_div_period'), '{}')}</tr>"
        for c in worst)
    return (f"<div class=multiples>{''.join(out)}</div><h3 class=subhead>Largest differences</h3>"
            "<div class='card scroll'><table class=data><thead><tr><th data-sort>case</th>"
            "<th data-sort>platform</th><th data-sort>verdict</th><th class=num data-sort=num>max rel</th>"
            "<th class=num data-sort=num>over tol</th><th class=num data-sort=num>compared</th>"
            "<th>worst variable</th><th>element</th><th class=num data-sort=num>first period</th></tr>"
            f"</thead><tbody>{rows or '<tr><td colspan=9>Every compared pair is identical.</td></tr>'}"
            "</tbody></table></div>")


def _platforms(cells: list[dict], r: str, case_pages: set[str]) -> str:
    ag = metrics.agreement(cells)
    if not ag:
        plats = sorted({c["_platform"] for c in cells})
        return (f"<p class=note>Only {E(', '.join(plats) or 'no platform')} in this set; agreement "
                "needs the same cases on two.</p>")
    p, q = ag["platforms"]
    rows = "".join(
        f"<tr><td class=nw>{E(eid)}</td>{_num(e['both'], '{:,}')}"
        f"<td class=num data-v={e['verdict_agree']}>{e['verdict_agree']:,} "
        f"({100 * e['verdict_agree'] / e['both']:.1f} %)</td>"
        f"<td class=num data-v={e['identical']}>{e['identical']:,} of {e['hashed']:,}</td>"
        f"{_num(e['wall_ratio_median'], '{:.2f}')}{_num(e['wall_ratio_n'], '{:,}')}</tr>"
        for eid, e in sorted(ag["engines"].items()))
    differ = "".join(
        f"<tr><td>{_case_link(case, r, case_pages)}</td><td class=nw>{E(eid)}</td><td>{_verdict(a.get('verdict', '?'))}"
        f"</td><td>{_verdict(b.get('verdict', '?'))}</td><td class=note-cell>"
        f"{E(str(a.get('note') or b.get('note') or ''))}</td></tr>"
        for eid, case, a, b in ag["differ"][:200])
    return (
        "<div class='card scroll'><table class=data><thead><tr><th>engine</th>"
        f"<th class=num>cases on both</th><th class=num>same verdict</th>"
        f"<th class=num>identical .out</th><th class=num>median {E(q)} ÷ {E(p)} time</th>"
        "<th class=num>timed cases</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
        "<p class=muted>Identical .out compares the first 16 hex digits of each output's SHA-256 "
        "(outputs over 256 MiB are not hashed). The time ratio uses cases where either platform "
        f"took at least {metrics.RATIO_FLOOR_S:g} s; the runners' CPUs may differ (see each run's manifest).</p>"
        + (f"<details class=mech><summary><span class=chev aria-hidden=true>›</span>"
           f"<span class=mech__n>{len(ag['differ']):,}</span><span class=mech__text>runs whose verdict "
           f"differs between {E(p)} and {E(q)}</span></summary><div class=mech__body><div class=scroll>"
           f"<table class=data><thead><tr><th>case</th><th>engine</th><th>{E(p)}</th><th>{E(q)}</th>"
           f"<th>note</th></tr></thead><tbody>{differ}</tbody></table></div></div></details>"
           if ag["differ"] else ""))


def _tags_block(tag_counts: Counter, r: str) -> str:
    if not tag_counts:
        return ""
    links = "".join(f"<a href='{r}tags/{E(t)}/index.html'>{E(t)} <b>{n}</b></a>"
                    for t, n in tag_counts.most_common())
    return f"<div class=tags>{links}</div>"


# ── pages ──────────────────────────────────────────────────────────────────

def _latest_run(envelopes: list[dict]) -> tuple[dict, list[dict]]:
    """The newest workflow run among the envelopes, and its envelopes."""
    by = defaultdict(list)
    for env in envelopes:
        by[(env.get("_run") or {}).get("id")].append(env)
    def started(item):
        _, envs = item
        return max(((e.get("_run") or {}).get("started") or e.get("timestamp") or "") for e in envs)
    run_id, envs = max(by.items(), key=started)
    return (envs[0].get("_run") or {}), envs


def _hero(envelopes: list[dict]) -> str:
    from .history import _run_description
    m, envs = _latest_run(envelopes)
    manifests = [e.get("_run") or {} for e in envs]
    desc = _run_description(manifests) if any(manifests) else ""
    eng = m.get("engine") or {}
    shas = sorted({e.get("engine_sha") or "" for e in envelopes} - {""})
    plats = sorted({metrics.platform_of(e) for e in envs})
    started = min((x.get("started") for x in manifests if x.get("started")), default=None)
    finished = [x.get("finished") for x in manifests]
    commit = (f"<a href='{ENGINE_URL}/commit/{E(eng['sha_full'])}'>{E((eng.get('ref') + ' @ ') if eng.get('ref') else '')}"
              f"{E(eng.get('sha') or '')}</a>" if eng.get("sha_full")
              else E(", ".join(shas) or "—"))
    facts = [("Engine", commit), ("Commit", E(eng.get("subject") or "—")),
             ("Started", E(_ago(started) if started else _ago(max(e.get("timestamp", "") for e in envs)))),
             ("Platforms", E(" · ".join(plats))),
             ("Jobs", E(f"{len(envs):,} envelope(s)" + ("" if all(finished) else " · some unfinished")))]
    buttons = []
    if m.get("url"):
        buttons.append(f"<a class='hc-btn hc-btn--solid' href='{E(m['url'])}'>Workflow run</a>")
    buttons += ["<a class='hc-btn hc-btn--ghost' href='#runs'>Runs and artifacts</a>",
                "<a class='hc-btn hc-btn--ghost' href='trends/index.html'>Trends</a>",
                "<a class='hc-btn hc-btn--ghost' href='docs/index.html'>Manual</a>"]
    kicker = " · ".join(x for x in (m.get("workflow"), {"schedule": "scheduled",
                                                       "workflow_dispatch": "started by hand",
                                                       "repository_dispatch": "engine push"}.get(
        m.get("event") or "", m.get("event"))) if x) or "Benchmark results"
    return (
        "<section class=hero><div class='wrap hero__inner'>"
        f"<p class=hero__kicker>{E(kicker)}</p><h1 class=hero__title>OpenSWMM Benchmarks</h1>"
        "<p class=hero__lede>Engine-agnostic regression and verification for SWMM-compatible "
        "engines." + (f" <span class=hero__desc>{E(desc)}</span>" if desc else "") + "</p>"
        "<ul class=facts>" + "".join(f"<li><span class=k>{k}</span><span class=v>{v}</span></li>"
                                     for k, v in facts) + "</ul>"
        f"<div class=hero__actions>{''.join(buttons)}</div></div>"
        "<svg class=hero__wave viewBox='0 0 1440 70' preserveAspectRatio=none aria-hidden=true "
        "focusable=false><path d='M0,40 C240,70 480,8 720,30 C960,52 1200,20 1440,44 L1440,70 L0,70 Z'/>"
        "</svg></section>")


def _tiles(cells: list[dict], badge_map: dict, n_cases: int) -> str:
    def msg(k):
        return badge_map.get(k, {}).get("message", "—")
    truth = [c for c in cells if scoring.is_truth(c.get("reference_class", ""))]
    gating = [c for c in cells if c.get("verdict") in scoring.GATING]
    ps = metrics.pairs(cells)
    identical = sum(1 for c in ps if c["max_rel"] == 0)
    cont = metrics.continuity(cells)
    st = metrics.stability(cells)
    runs = [c for c in cells if metrics.is_engine_run(c)]
    total = sum(metrics.wall(c) or 0 for c in runs)
    ratio_note = ""
    for p, pts in sorted(metrics.speed_points(cells).items()):
        rs = metrics.ratio_summary(pts)
        if rs["n"]:
            ratio_note = f"median {metrics.V6} ÷ legacy {rs['median']:.2f} on {p}"
            break
    rss = [c["peak_rss_mb"] for c in runs if isinstance(c.get("peak_rss_mb"), (int, float))]
    ver_ok = None if not truth else not any(c.get("verdict") in scoring.GATING for c in truth)
    tiles = [
        _tile("Verification", msg("verification"), "exact-solution cases only",
              _status(ver_ok, "exact solutions")),
        _tile("Regression", msg("regression"), "parity and baseline drift",
              _status(not gating, f"{len(gating):,} gating cell(s)")),
        _tile("Cells graded", f"{len(cells):,}", f"{len(runs):,} engine runs · {len(ps):,} pairs"),
        _tile("Parity", f"{identical:,} of {len(ps):,}" if ps else "—",
              "pairs bit-identical at every element and period"),
        _tile("Mass balance", f"{abs(cont['worst'][0]['continuity_err']):.2f} %" if cont["worst"] else "—",
              "worst |flow routing continuity|"
              + (f" · {cont['by_design']:,} by design left out" if cont["by_design"] else "")),
        _tile("Stability", f"{100 * st['stable'] / len(st['runs']):.1f} %" if st["runs"] else "—",
              f"runs with ≤ {metrics.STABLE_PCT:g} % of steps not converging"),
        _tile("Engine time", charts.fmt_seconds(total) if total else "—", ratio_note or "all engine runs"),
        _tile("Peak memory", f"{max(rss):,.0f} MiB" if rss else "—",
              "largest single engine process" if rss else "not measured in this set"),
        _tile("Corpus", f"{n_cases:,}", "models, tagged and validated"),
    ]
    return f"<div class=wrap><div class='tiles tiles--lift'>{''.join(tiles)}</div></div>"


def build_site(envelopes: list[dict], dest: Path,
               history: list[dict] | None = None) -> list[Path]:
    """Render the dashboard. Returns every file written."""
    dest = Path(dest)
    (dest / "badges").mkdir(parents=True, exist_ok=True)
    written: list[Path] = _copy_assets(dest)

    tag_counts, n_cases, corpus_cases = _census()
    badge_map = scoring.badges(envelopes, corpus_count=n_cases or None)
    written += scoring.write_badges(dest / "badges", badge_map)

    # A run that produced nothing must never render as a clean run. With no
    # cells the ordinary layout reads "Failing cells 0 / No failing cells in
    # this run" — a clean bill of health for work that never happened, which
    # is the most dangerous page this project could publish. Say so instead.
    if not any(env.get("cells") for env in envelopes):
        written += _write_empty_state(dest, n_cases)
        written += _write_trends(history or [], dest)
        return written

    for env in envelopes:
        env["_slug"] = _run_slug(env)
    cells = metrics.cells_of(envelopes)
    case_pages = {c["case"] for c in cells if c.get("case") and c["case"] != "-"}

    written += _write_index(envelopes, cells, badge_map, n_cases, tag_counts, case_pages, dest)
    written += _write_run_pages(envelopes, dest, case_pages)
    written += _write_case_pages(cells, corpus_cases, dest)
    written += _write_tag_pages(tag_counts, cells, dest, corpus_cases, case_pages)
    written += _write_trends(history or [], dest)
    return written


def _write_index(envelopes, cells, badge_map, n_cases, tag_counts, case_pages, dest) -> list[Path]:
    r = ""
    truth = [c for c in cells if scoring.is_truth(c.get("reference_class", ""))]
    regression = [c for c in cells if not scoring.is_truth(c.get("reference_class", ""))]
    envs_sorted = sorted(envelopes, key=lambda e: (str(e.get("suite")), metrics.platform_of(e),
                                                   e.get("shard") or ""))
    body = [
        _hero(envelopes), _tiles(cells, badge_map, n_cases), "<div class=wrap>",
        "<div class=note><strong>Verification is not regression.</strong> "
        f"{len(truth):,} cell(s) here are graded against an exact solution and can show an engine "
        f"is <em>wrong</em> (verification: exact-solution cases only). The other {len(regression):,} "
        "cover baseline changes, observations or numerical consistency. Their verdicts must be "
        "interpreted according to their reference and check scope.</div>",
        "".join(_coverage_note(env) for env in envelopes),
        _section("suites", "Results by suite",
                 "Verdicts for each suite on each platform. Gating verdicts (FAIL, BASELINE-FAIL, "
                 "ERROR, XPASS) fail the Nightly; an expected failure is a documented divergence.",
                 _suite_table(envelopes, r)),
        _section("runs", "Runs",
                 "One row per sweep job and suite. Open a row for its description, the run "
                 "manifest (engine commit, host, CPU, arguments) and links to the workflow run, the "
                 "job log and the job's artifacts (kept 30 days).",
                 "".join(_run_details(env, r) for env in envs_sorted)),
        _section("failures", "Failures by mechanism",
                 "Gating cells grouped by what the note says, with names, numbers and line numbers "
                 "taken out, so one cause shows up as one row however many cases it affects.",
                 _mechanisms(cells, r, case_pages)),
        _section("performance", "Performance",
                 "Wall time of every completed parity run, one engine process each, on one thread "
                 "(OMP_NUM_THREADS=1). Cases trimmed for the CI budget are left out of the "
                 "engine-against-engine comparison.",
                 _performance(cells, r, case_pages)),
        _section("mass-balance", "Mass balance",
                 "Continuity errors from each engine's own report.", _mass_balance(cells, r, case_pages)),
        _section("stability", "Stability",
                 "Routing convergence and time steps from each engine's own report.",
                 _stability(cells, r, case_pages)),
        _section("parity", "Parity",
                 "How far the engine under test is from the legacy reference, per compared pair.",
                 _parity(cells, r, case_pages)),
        _section("platforms", "Platforms",
                 "The same case and engine on two operating systems.", _platforms(cells, r, case_pages)),
    ]
    if tag_counts:
        body.append(_section("tags", "Corpus by tag", "", _tags_block(tag_counts, r)))
    body.append("</div>")
    p = dest / "index.html"
    p.write_text(_page("OpenSWMM Benchmarks", "".join(body), 0, active="overview",
                       description="Regression and verification results for SWMM-compatible engines."),
                 encoding="utf-8")
    return [p]


def _write_empty_state(dest: Path, n_cases: int) -> list[Path]:
    """Publish the fact that the run produced nothing.

    The alternative outcomes are both worse: a failed publish leaves the last
    good dashboard up, so a broken nightly looks like a healthy one; and the
    ordinary layout with zero cells reads as an all-clear.
    """
    body = [
        "<section class='hero hero--alert'><div class='wrap hero__inner'>"
        "<p class=hero__kicker>Benchmark results</p><h1 class=hero__title>OpenSWMM Benchmarks</h1>"
        "<p class=hero__lede>Engine-agnostic regression and verification for SWMM-compatible "
        "engines.</p></div></section><div class=wrap>",
        "<div class='note note--alert'><strong>This run produced no results.</strong>"
        "<br>No scores envelope reached the publish step, so there is nothing "
        "to report — this is <em>not</em> a passing run. The usual causes are a "
        "sweep that failed before writing any cell, an engine build that never "
        "completed, or a publish triggered outside the run that holds the "
        "artifacts. Check the most recent <code>Nightly</code> workflow run.</div>",
        f"<section class=block><h2>Corpus</h2><p>{n_cases:,} models are present and schema-valid; "
        "none of them were graded in this run.</p></section></div>",
    ]
    index = dest / "index.html"
    index.write_text(_page("OpenSWMM Benchmarks — no results", "".join(body), 0, active="overview"),
                     encoding="utf-8")
    return [index]


def _pagehead(r: str, crumbs: list[tuple[str, str]], title: str, sub: str = "") -> str:
    trail = " / ".join([f"<a href='{r}index.html'>Overview</a>"]
                       + [f"<a href='{E(h)}'>{E(t)}</a>" if h else E(t) for t, h in crumbs])
    return (f"<section class=pagehead><div class=wrap><p class=crumbs>{trail}</p>"
            f"<h1>{title}</h1>" + (f"<p class=pagehead__sub>{sub}</p>" if sub else "")
            + "</div></section>")


_SKIP_KEYS = {"case", "solver", "pair", "verdict", "note", "reference_class"}


def _cell_details(c: dict) -> str:
    """The cell's remaining fields, compact, for suites with their own metrics."""
    bits = []
    for k, v in c.items():
        if k in _SKIP_KEYS or k.startswith("_") or v in (None, "", [], {}):
            continue
        if isinstance(v, bool):
            v = "yes" if v else "no"
        elif isinstance(v, float):
            v = f"{v:.4g}"
        elif isinstance(v, dict):
            bad = [kk for kk, vv in v.items() if vv is False]
            v = ("all pass" if v and all(vv is True for vv in v.values())
                 else ("failed: " + ", ".join(bad)) if bad else json.dumps(v, default=str)[:120])
        bits.append(f"<span class=kv><span>{E(k)}</span> {E(str(v))[:160]}</span>")
    return "".join(bits)


def _cells_table(cells: list[dict], r: str, case_pages: set[str], table_id: str) -> str:
    rows = "".join(
        f"<tr><td>{_case_link(str(c.get('case', '')), r, case_pages)}</td>"
        f"<td>{E(str(c.get('solver') or c.get('pair') or ''))}</td>"
        f"<td data-v='{E(c.get('verdict', ''))}'>{_verdict(c.get('verdict', '?'))}</td>"
        f"{_secs(metrics.wall(c))}{_pct(c.get('continuity_err'))}"
        f"<td class=note-cell>{E(str(c.get('note') or ''))}</td>"
        f"<td class=details-cell>{_cell_details(c)}</td></tr>"
        for c in cells)
    return (f"<div class=filterbar><input type=search data-filter='{table_id}' "
            "placeholder='Filter: case, engine, verdict, note…' aria-label='Filter cells'>"
            f"<span class=muted><span data-count-for='{table_id}'>{len(cells):,}</span> of {len(cells):,} cells</span></div>"
            f"<div class='card scroll'><table class=data id='{table_id}'><thead><tr>"
            "<th data-sort>case</th><th data-sort>engine / pair</th><th data-sort>verdict</th>"
            "<th class=num data-sort=num>wall</th><th class=num data-sort=num>continuity %</th>"
            "<th>note</th><th>details</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div>")


def _write_run_pages(envelopes: list[dict], dest: Path, case_pages: set[str]) -> list[Path]:
    written = []
    r = "../../"
    for env in envelopes:
        d = dest / "runs" / env["_slug"]
        d.mkdir(parents=True, exist_ok=True)
        cells = metrics.cells_of([env])
        m = env.get("_run") or {}
        where = " ".join(_chip(x) for x in [metrics.platform_of(env)]
                         + ([f"shard {env['shard']}"] if env.get("shard") else []))
        sub = (f"engine <code>{E(env.get('engine_sha') or 'nosha')}</code> · "
               f"{E(str(env.get('timestamp', '')))} · {where} · {len(cells):,} cell(s)")
        body = [
            _pagehead(r, [("Runs", f"{r}index.html#runs"), (env.get("suite", "run"), "")],
                      E(str(env.get("suite", "?"))), sub),
            "<div class=wrap>",
            (f"<p class=lead>{E(m['description'])}</p>" if m.get("description") else ""),
            _artifact_links(env, r, run_page=False),
            _coverage_note(env),
            _section("verdicts", "Verdicts", "", _group_legend() + _segbar(cells) + _verdict_chips(cells)
                     + _run_stats(cells)),
            _section("run", "Run", "The manifest the sweep wrote beside this envelope.",
                     _manifest_grid(env)),
            _section("failures", "Failures by mechanism", "", _mechanisms(cells, r, case_pages, 40)),
        ]
        if metrics.parity_runs(cells):
            body.append(_section("performance", "Performance", "", _performance(cells, r, case_pages)))
        if metrics.continuity(cells)["graded"]:
            body.append(_section("mass-balance", "Mass balance", "", _mass_balance(cells, r, case_pages)))
        if metrics.stability(cells)["runs"]:
            body.append(_section("stability", "Stability", "", _stability(cells, r, case_pages)))
        if metrics.pairs(cells):
            body.append(_section("parity", "Parity", "", _parity(cells, r, case_pages)))
        body += [_section("cells", "Every cell", "Click a column to sort; type to filter.",
                          _cells_table(cells, r, case_pages, "cells")), "</div>"]
        p = d / "index.html"
        p.write_text(_page(f"{env.get('suite', 'run')} — {env['_slug']}", "".join(body), 2,
                           active="runs"), encoding="utf-8")
        written.append(p)
        raw = d / "scores.json"
        raw.write_text(json.dumps({k: v for k, v in env.items() if not k.startswith("_")},
                                  indent=2, default=str), encoding="utf-8")
        written.append(raw)
    return written


def _write_case_pages(cells: list[dict], corpus_cases: dict, dest: Path) -> list[Path]:
    by = defaultdict(list)
    for c in cells:
        if c.get("case") and c["case"] != "-":
            by[c["case"]].append(c)
    written = []
    r = "../../"
    for case, cs in sorted(by.items()):
        meta = corpus_cases.get(case)
        tags = sorted(meta.tags) if meta else []
        info = []
        if meta:
            md = meta.meta or {}
            for k, label in (("title", "Title"), ("description", "Description"),
                             ("source", "Source"), ("collection", "Collection")):
                v = md.get(k)
                if isinstance(v, dict):
                    v = ", ".join(f"{a}: {b}" for a, b in v.items() if isinstance(b, (str, int, float)))
                if v:
                    info.append(f"<div><dt>{label}</dt><dd>{E(str(v))[:600]}</dd></div>")
            info.append(f"<div><dt>Reference</dt><dd>{E(meta.reference_class)}</dd></div>")
            xf = md.get("expected_failures") or []
            for x in xf:
                info.append(f"<div><dt>Expected failure</dt><dd>{E(str(x.get('engine', '*')))}: "
                            f"{E(str(x.get('reason') or x.get('report_error') or ''))}</dd></div>")
        tag_links = "".join(f"<a href='{r}tags/{E(t)}/index.html'>{E(t)}</a>" for t in tags)
        rows = "".join(
            f"<tr><td class=nw>{E(c['_platform'])}</td><td>{E(c['_suite'])}</td>"
            f"<td>{E(str(c.get('solver') or c.get('pair') or ''))}</td>"
            f"<td>{_verdict(c.get('verdict', '?'))}</td>{_secs(metrics.wall(c))}"
            f"{_num(c.get('peak_rss_mb'), '{:,.0f}')}{_pct(c.get('continuity_err'))}"
            f"{_pct(c.get('runoff_err'))}{_pct(c.get('pct_not_converging'))}"
            f"{_num(c.get('avg_iter'), '{:.2f}')}{_num(c.get('max_rel'), '{:.2e}')}"
            f"<td><a href='{r}runs/{E(c['_env']['_slug'])}/index.html'>run</a></td>"
            f"<td class=note-cell>{E(str(c.get('note') or ''))}</td></tr>"
            for c in sorted(cs, key=lambda c: (c["_platform"], c["_suite"], "pair" in c,
                                               str(c.get("solver") or c.get("pair")))))
        body = [
            _pagehead(r, [("Cases", "")], f"<code>{E(case)}</code>",
                      " ".join(_verdict(v) for v in sorted({c.get('verdict', '?') for c in cs}))),
            "<div class=wrap>",
            (f"<dl class=facts-grid>{''.join(info)}</dl>" if info else ""),
            (f"<div class=tags>{tag_links}</div>" if tag_links else ""),
            _section("results", "Results", "Every engine run and compared pair of this case in the "
                     "published set.",
                     "<div class='card scroll'><table class=data><thead><tr><th data-sort>platform</th>"
                     "<th data-sort>suite</th><th data-sort>engine / pair</th><th data-sort>verdict</th>"
                     "<th class=num data-sort=num>wall</th><th class=num data-sort=num>peak MiB</th>"
                     "<th class=num data-sort=num>routing %</th><th class=num data-sort=num>runoff %</th>"
                     "<th class=num data-sort=num>not conv. %</th><th class=num data-sort=num>avg iter</th>"
                     "<th class=num data-sort=num>max rel</th><th></th><th>note</th></tr></thead>"
                     f"<tbody>{rows}</tbody></table></div>"),
            "</div>"]
        d = dest / "cases" / _slug(case)
        d.mkdir(parents=True, exist_ok=True)
        p = d / "index.html"
        p.write_text(_page(f"{case} — OpenSWMM Benchmarks", "".join(body), 2, active="runs"),
                     encoding="utf-8")
        written.append(p)
    return written


def _write_tag_pages(tag_counts: Counter, cells: list[dict], dest: Path,
                     corpus_cases: dict, case_pages: set[str]) -> list[Path]:
    if not tag_counts or not corpus_cases:
        return []
    by_case: dict[str, list[dict]] = defaultdict(list)
    for c in cells:
        by_case[str(c.get("case", ""))].append(c)
    plats = sorted({c["_platform"] for c in cells})
    written = []
    r = "../../"
    for tag in tag_counts:
        rows = ""
        for case in sorted((c for c in corpus_cases.values() if tag in c.tags), key=lambda c: c.id):
            cs = by_case.get(case.id, [])
            per = []
            for p in plats:
                vs = {x.get("verdict") for x in cs if x["_platform"] == p}
                per.append(f"<td>{' '.join(_verdict(v) for v in sorted(vs)) if vs else '—'}</td>")
            rows += (f"<tr><td>{_case_link(case.id, r, case_pages)}</td>"
                     f"<td>{E(case.reference_class)}</td>{''.join(per)}"
                     f"<td class=muted>{E(', '.join(sorted(case.tags)))}</td></tr>")
        head = "".join(f"<th data-sort>{E(p)}</th>" for p in plats)
        body = [_pagehead(r, [("Tags", f"{r}index.html#tags"), (tag, "")], E(tag),
                          f"{tag_counts[tag]} case(s) carry this tag"),
                "<div class=wrap><div class='card scroll'><table class=data><thead><tr>"
                f"<th data-sort>case</th><th data-sort>reference</th>{head}<th>tags</th></tr></thead>"
                f"<tbody>{rows}</tbody></table></div></div>"]
        d = dest / "tags" / tag
        d.mkdir(parents=True, exist_ok=True)
        p = d / "index.html"
        p.write_text(_page(f"tag: {tag}", "".join(body), 2), encoding="utf-8")
        written.append(p)
    return written


def _write_trends(history: list[dict], dest: Path) -> list[Path]:
    r = "../"
    d = dest / "trends"
    d.mkdir(parents=True, exist_ok=True)
    body = [_pagehead(r, [("Trends", "")], "Trends",
                      f"{len(history):,} recorded run(s) from the <code>benchmark-data</code> branch"),
            "<div class=wrap>"]
    if len(history) < 2:
        body.append("<div class=note>Trends need at least two recorded workflow runs; "
                    f"{len(history):,} so far. The Publish workflow records one per run.</div>")
    else:
        xl = [f"{(h.get('started') or '')[5:10]} {((h.get('engine') or {}).get('sha') or '')[:8]}"
              for h in history]
        # Parity leads, one section per platform; the smaller suites follow
        # behind a disclosure with their gating count and engine time only.
        keys = sorted({(g["suite"], g["platform"]) for h in history for g in h.get("groups", [])},
                      key=lambda k: (k[0] != "parity", k))
        others = []
        for suite, plat in keys:
            groups = [next((g for g in h.get("groups", [])
                            if g["suite"] == suite and g["platform"] == plat), None) for h in history]
            eids = sorted({e for g in groups if g for e in g.get("engines", {})},
                          key=lambda e: (e not in SERIES_CLASS, e))
            if suite != "parity" and len(eids) > 3:
                eids = []
            def value(g, e, field, scale):
                v = ((g or {}).get("engines", {}).get(e) or {}).get(field)
                return v * scale if isinstance(v, (int, float)) else None

            def series(field, scale=1.0):
                return [{"name": e, "cls": _engine_class(e, eids),
                         "values": [value(g, e, field, scale) for g in groups]}
                        for e in eids]
            cards = [f"<div class=card><h3>Gating cells</h3><p class=sub>Per run, all engines.</p>"
                     + charts.lines(xl, [{"name": "gating", "cls": "g-gating",
                                          "values": [g["gating"] if g else None for g in groups]}],
                                    unit="cells", label=f"Gating cells, {suite} on {plat}",
                                    fmt=lambda v: f"{v:,.0f}") + "</div>"]
            if eids:
                cards.append(
                    f"<div class=card><h3>Engine time</h3><p class=sub>Sum of passing runs' wall "
                    "time.</p>" + charts.lines(xl, series("wall_total", 1 / 3600), unit="hours",
                                               label=f"Engine time, {suite} on {plat}",
                                               fmt=lambda v: f"{v:.2f} h") + "</div>")
            if suite != "parity":
                others.append(f"<h3 class=subhead>{E(suite)} · {E(plat)}</h3>"
                              f"<div class=multiples>{''.join(cards)}</div>")
                continue
            if eids:
                cards += [
                    f"<div class=card><h3>Median run</h3><p class=sub>Median wall time of passing "
                    "runs.</p>" + charts.lines(xl, series("wall_median"), unit="seconds",
                                               label=f"Median run, {suite} on {plat}",
                                               fmt=lambda v: charts.fmt_seconds(v)) + "</div>",
                    f"<div class=card><h3>Worst continuity</h3><p class=sub>Largest graded |flow "
                    "routing continuity error|.</p>" + charts.lines(
                        xl, series("continuity_worst"), unit="%",
                        label=f"Worst continuity, {suite} on {plat}", fmt=lambda v: f"{v:.2f} %")
                    + "</div>",
                    f"<div class=card><h3>Stable runs</h3><p class=sub>Runs with ≤ "
                    f"{metrics.STABLE_PCT:g} % of steps not converging.</p>" + charts.lines(
                        xl, series("stable_pct"), unit="%", label=f"Stable runs, {suite} on {plat}",
                        fmt=lambda v: f"{v:.1f} %") + "</div>",
                ]
            body.append(_section(f"{_slug(suite)}-{_slug(plat)}", f"{suite} · {plat}", "",
                                 f"<div class=multiples>{''.join(cards)}</div>"))
        if others:
            body.append(_section("other-suites", "Other suites", "",
                                 f"<details class=mech><summary><span class=chev aria-hidden=true>›"
                                 f"</span><span class=mech__n>{len(others)}</span><span "
                                 "class=mech__text>suite and platform combinations: gating cells "
                                 "and engine time</span></summary><div class=mech__body>"
                                 f"{''.join(others)}</div></details>"))
        rows = "".join(
            f"<tr><td>{E(_ago(h.get('started')))}</td><td>{E(h.get('description') or '')}</td>"
            f"<td><code>{E((h.get('engine') or {}).get('sha') or '')}</code></td>"
            f"<td>{('<a href=' + chr(39) + E(h['url']) + chr(39) + '>run</a>') if h.get('url') else ''}</td></tr>"
            for h in reversed(history))
        body.append(_section("history", "Recorded runs", "",
                             "<div class='card scroll'><table class=data><thead><tr><th>started</th>"
                             "<th>description</th><th>engine</th><th></th></tr></thead>"
                             f"<tbody>{rows}</tbody></table></div>"))
    body.append("</div>")
    p = d / "index.html"
    p.write_text(_page("Trends — OpenSWMM Benchmarks", "".join(body), 1, active="trends"),
                 encoding="utf-8")
    return [p]
