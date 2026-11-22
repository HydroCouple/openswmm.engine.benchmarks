#!/usr/bin/env python3
"""Inline SVG charts for the dashboard: no library, no script needed to draw.

Every chart is styled by CSS classes the dashboard stylesheet maps to the
HydroCouple tokens (``.s1`` .. ``.s3`` series, ``.g-pass`` .. ``.g-not_run``
verdict groups), so a chart follows the page's light or dark mode. Marks carry
``data-tip`` text for the page's tooltip script; every chart also comes with a
table view, so no value is reachable only by hovering.

Conventions (see the dataviz method the page follows): bars at most 24 px
wide with a 4 px rounded data end and a square base, a 2 px gap between
neighbors, 2 px lines, markers of radius 4 with a surface ring, hairline solid
gridlines, a legend whenever two or more series are drawn, and one y axis.
"""
from __future__ import annotations

import html
import math

E = html.escape


def _nice_step(span: float, target: int = 4) -> float:
    if span <= 0:
        return 1.0
    raw = span / target
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def _ticks(vmax: float) -> list[float]:
    step = _nice_step(vmax)
    top = math.ceil(vmax / step) * step if vmax > 0 else step
    n = int(round(top / step))
    return [i * step for i in range(n + 1)]


def fmt_tick(v: float) -> str:
    if v >= 10000:
        return f"{v / 1000:g}K"
    return f"{v:,.0f}" if v == int(v) else f"{v:g}"


def _bar_path(x: float, y: float, w: float, base: float) -> str:
    h = base - y
    if h <= 0:
        return ""
    r = min(4.0, w / 2, h)
    return (f"M{x:.1f},{base:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}"
            f"H{x + w - r:.1f}Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f}V{base:.1f}Z")


def legend(series: list[dict], kind: str = "rect") -> str:
    if len(series) < 2:
        return ""
    items = "".join(
        f"<li><span class='key key--{kind} {E(s['cls'])}'></span>{E(s['name'])}</li>"
        for s in series)
    return f"<ul class=legend>{items}</ul>"


def table_view(headers: list[str], rows: list[list], caption: str = "Table view") -> str:
    head = "".join(f"<th>{E(str(h))}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{E(str(v))}</td>" for v in r) + "</tr>"
                   for r in rows)
    return (f"<details class=tableview><summary>{E(caption)}</summary>"
            f"<div class=scroll><table class=data><thead><tr>{head}</tr></thead>"
            f"<tbody>{body}</tbody></table></div></details>")


def columns(categories: list[str], series: list[dict], *, unit: str,
            label: str, x_title: str = "") -> str:
    """Grouped columns. series = [{name, cls, values: [int per category]}]."""
    W, H, L, R, T, B = 640, 236, 46, 10, 18, 46
    pw, ph = W - L - R, H - T - B
    vmax = max([max(s["values"]) for s in series if s["values"]] + [0])
    ticks = _ticks(vmax or 1)
    top = ticks[-1]
    base = T + ph
    band = pw / max(len(categories), 1)
    n = max(len(series), 1)
    bw = min(24.0, (band * 0.72 - 2 * (n - 1)) / n)
    group_w = n * bw + 2 * (n - 1)

    parts = [f"<svg class=chart__svg viewBox='0 0 {W} {H}' role=img "
             f"aria-label='{E(label)}'>"]
    for t in ticks:
        y = base - (t / top) * ph
        parts.append(f"<line class=grid x1={L} x2={W - R} y1={y:.1f} y2={y:.1f} />"
                     f"<text class=tick x={L - 6} y={y + 3.5:.1f} text-anchor=end>"
                     f"{E(fmt_tick(t))}</text>")
    parts.append(f"<text class=axis-title x={L} y=11>{E(unit)}</text>")
    for si, s in enumerate(series):
        peak = max(range(len(s["values"])), key=lambda i: s["values"][i]) if s["values"] else -1
        for ci, v in enumerate(s["values"]):
            x = L + ci * band + (band - group_w) / 2 + si * (bw + 2)
            y = base - (v / top) * ph
            tip = f"{v:,} {unit}\n{s['name']} · {categories[ci]}"
            mark = (f"<path class='bar {E(s['cls'])}' d='{_bar_path(x, y, bw, base)}' />"
                    if v else "")
            if ci == peak and v:
                mark += (f"<text class=value x={x + bw / 2:.1f} y={y - 4:.1f} "
                         f"text-anchor=middle>{v:,}</text>")
            parts.append(f"<g class=mark tabindex=0 data-tip='{E(tip)}'>{mark}"
                         f"<rect class=hit x={x - 1:.1f} y={T} width={bw + 2:.1f} "
                         f"height={ph} /></g>")
    for ci, c in enumerate(categories):
        x = L + ci * band + band / 2
        parts.append(f"<text class=tick x={x:.1f} y={base + 15} text-anchor=middle>"
                     f"{E(c)}</text>")
    parts.append(f"<line class=baseline x1={L} x2={W - R} y1={base} y2={base} />")
    if x_title:
        parts.append(f"<text class=axis-title x={L + pw / 2:.1f} y={H - 6} "
                     f"text-anchor=middle>{E(x_title)}</text>")
    parts.append("</svg>")
    rows = [[c] + [s["values"][i] for s in series] for i, c in enumerate(categories)]
    return (f"<div class=chart>{legend(series)}<div class=chart__frame>"
            f"{''.join(parts)}</div>"
            + table_view([x_title or "bin"] + [s["name"] for s in series], rows)
            + "</div>")


def _log_ticks(lo: float, hi: float) -> list[float]:
    a, b = math.floor(math.log10(lo)), math.ceil(math.log10(hi))
    return [10.0 ** k for k in range(a, b + 1)]


def scatter_loglog(points: list[tuple[str, float, float]], *, x_name: str,
                   y_name: str, unit: str, cls: str = "s1", label: str,
                   guides: tuple[tuple[float, str], ...] = (
                       (1.0, "same"), (2.0, "2× slower"), (0.5, "2× faster")),
                   ) -> str:
    """Each point one case: x = time on engine A, y = time on engine B."""
    W, H, L, R, T, B = 520, 446, 50, 78, 22, 44
    pw, ph = W - L - R, H - T - B
    vals = [v for _, x, y in points for v in (x, y) if v and v > 0]
    lo = max(min(vals), 1e-3) if vals else 0.01
    hi = max(vals) if vals else 1.0
    ticks = _log_ticks(lo, hi)
    a, b = math.log10(ticks[0]), math.log10(ticks[-1])
    if b <= a:
        b = a + 1

    def sx(v):
        return L + (math.log10(max(v, ticks[0])) - a) / (b - a) * pw

    def sy(v):
        return T + ph - (math.log10(max(v, ticks[0])) - a) / (b - a) * ph

    out = [f"<svg class='chart__svg chart__svg--square' viewBox='0 0 {W} {H}' "
           f"role=img aria-label='{E(label)}'>"]
    for t in ticks:
        x, y = sx(t), sy(t)
        tl = E(f"{t:g}")
        out.append(f"<line class=grid x1={x:.1f} x2={x:.1f} y1={T} y2={T + ph} />"
                   f"<line class=grid x1={L} x2={L + pw} y1={y:.1f} y2={y:.1f} />"
                   f"<text class=tick x={x:.1f} y={T + ph + 15} text-anchor=middle>{tl}</text>"
                   f"<text class=tick x={L - 6} y={y + 3.5:.1f} text-anchor=end>{tl}</text>")
    t0, t1 = ticks[0], ticks[-1]
    for k, name in guides:
        # y = k x, clipped to the plot square
        x0, x1 = t0, t1
        y0, y1 = k * x0, k * x1
        if y0 < t0:
            x0, y0 = t0 / k, t0
        if y1 > t1:
            x1, y1 = t1 / k, t1
        cls_g = "guide guide--main" if k == 1.0 else "guide"
        # The label sits where its line leaves the plot: above the top edge,
        # ending at the exit, or right of the right edge (the corner included).
        if x1 < t1 * 0.999:
            lab = (f"<text class=guide-label x={sx(x1) - 2:.1f} y={T - 6} "
                   f"text-anchor=end>{E(name)}</text>")
        else:
            lab = (f"<text class=guide-label x={L + pw + 5} "
                   f"y={max(sy(y1) + 3.5, T + 8):.1f}>{E(name)}</text>")
        out.append(f"<line class='{cls_g}' x1={sx(x0):.1f} y1={sy(y0):.1f} "
                   f"x2={sx(x1):.1f} y2={sy(y1):.1f} />{lab}")
    for case, x, y in points:
        tip = (f"{y_name} {fmt_seconds(y)} · {x_name} {fmt_seconds(x)}\n{case}"
               + (f"\nratio {y / x:.2f}" if x > 0 else ""))
        cx, cy = sx(x), sy(y)
        out.append(f"<g class=mark data-tip='{E(tip)}'>"
                   f"<circle class='dot {E(cls)}' cx={cx:.1f} cy={cy:.1f} r=4 />"
                   f"<circle class=hit cx={cx:.1f} cy={cy:.1f} r=11 /></g>")
    out.append(f"<text class=axis-title x={L + pw / 2:.1f} y={H - 6} text-anchor=middle>"
               f"{E(x_name)} ({E(unit)})</text>"
               f"<text class=axis-title x=12 y={T + ph / 2:.1f} text-anchor=middle "
               f"transform='rotate(-90 12 {T + ph / 2:.1f})'>{E(y_name)} ({E(unit)})</text>")
    out.append("</svg>")
    return f"<div class=chart><div class=chart__frame>{''.join(out)}</div></div>"


def lines(xlabels: list[str], series: list[dict], *, unit: str, label: str,
          fmt=None) -> str:
    """Trend lines. series = [{name, cls, values: [float|None per x]}]."""
    f = fmt or (lambda v: f"{v:,.3g}")
    W, H, L, R, T, B = 640, 220, 48, 64, 18, 40
    pw, ph = W - L - R, H - T - B
    vals = [v for s in series for v in s["values"] if v is not None]
    ticks = _ticks(max(vals) if vals else 1)
    top = ticks[-1] or 1
    base = T + ph
    n = len(xlabels)
    step = pw / max(n - 1, 1)

    def sx(i):
        return L + (i * step if n > 1 else pw / 2)

    def sy(v):
        return base - v / top * ph

    out = [f"<svg class=chart__svg viewBox='0 0 {W} {H}' role=img aria-label='{E(label)}'>"]
    for t in ticks:
        y = sy(t)
        out.append(f"<line class=grid x1={L} x2={W - R} y1={y:.1f} y2={y:.1f} />"
                   f"<text class=tick x={L - 6} y={y + 3.5:.1f} text-anchor=end>"
                   f"{E(fmt_tick(t))}</text>")
    out.append(f"<text class=axis-title x={L} y=11>{E(unit)}</text>"
               f"<line class=baseline x1={L} x2={W - R} y1={base} y2={base} />")
    label_every = max(1, math.ceil(n / 8))
    for i, xl in enumerate(xlabels):
        if i % label_every == 0 or i == n - 1:
            out.append(f"<text class=tick x={sx(i):.1f} y={base + 15} "
                       f"text-anchor=middle>{E(xl)}</text>")
    for s in series:
        segs, cur = [], []
        for i, v in enumerate(s["values"]):
            if v is None:
                if cur:
                    segs.append(cur)
                cur = []
            else:
                cur.append(f"{sx(i):.1f},{sy(v):.1f}")
        if cur:
            segs.append(cur)
        for seg in segs:
            if len(seg) > 1:
                out.append(f"<polyline class='line {E(s['cls'])}' points='{' '.join(seg)}' />")
        last = max((i for i, v in enumerate(s["values"]) if v is not None), default=None)
        if last is not None:
            v = s["values"][last]
            out.append(f"<circle class='dot {E(s['cls'])}' cx={sx(last):.1f} "
                       f"cy={sy(v):.1f} r=4 />"
                       f"<text class=value x={sx(last) + 8:.1f} y={sy(v) + 3.5:.1f}>"
                       f"{E(f(v))}</text>")
    # Crosshair: one column per x, the readout lists every series there.
    for i, xl in enumerate(xlabels):
        rows = [f"{s['name']}: {f(s['values'][i]) if s['values'][i] is not None else '—'}"
                for s in series]
        x0 = sx(i) - step / 2 if n > 1 else L
        w = step if n > 1 else pw
        out.append(f"<g class='mark mark--x' tabindex=0 data-tip='{E(xl + chr(10) + chr(10).join(rows))}'>"
                   f"<line class=cross x1={sx(i):.1f} x2={sx(i):.1f} y1={T} y2={base} />"
                   f"<rect class=hit x={max(x0, L):.1f} y={T} width={w:.1f} height={ph} /></g>")
    out.append("</svg>")
    rows = [[xl] + [(f(s["values"][i]) if s["values"][i] is not None else "—")
                    for s in series] for i, xl in enumerate(xlabels)]
    return (f"<div class=chart>{legend(series, 'line')}<div class=chart__frame>"
            f"{''.join(out)}</div>"
            + table_view(["run"] + [s["name"] for s in series], rows) + "</div>")


def segbar(groups: dict[str, int], labels: dict[str, str], *, thin: bool = True) -> str:
    """One whole split by verdict group; no text (the row beside it has the
    figures)."""
    total = sum(groups.values())
    if not total:
        return "<div class='segbar segbar--empty' role=img aria-label='no cells'></div>"
    name = ", ".join(f"{labels.get(k, k)} {v:,}" for k, v in groups.items() if v)
    segs = "".join(
        f"<span class='seg g-{E(k)}' style='flex-grow:{v}' "
        f"data-tip='{E(f'{v:,} {labels.get(k, k)}' + chr(10) + f'{100 * v / total:.1f}% of {total:,}')}'></span>"
        for k, v in groups.items() if v)
    return (f"<div class='segbar{' segbar--thin' if thin else ''}' role=img "
            f"aria-label='{E(name)}'>{segs}</div>")


def fmt_seconds(s: float | None) -> str:
    if s is None:
        return "—"
    if s < 1:
        return f"{s:.2f} s"
    if s < 120:
        return f"{s:.1f} s"
    if s < 7200:
        return f"{s / 60:.1f} min"
    return f"{s / 3600:.1f} h"
