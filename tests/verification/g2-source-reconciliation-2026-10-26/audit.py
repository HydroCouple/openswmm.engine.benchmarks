"""Source reconciliation and independent connected-component observation audit.

No solver runs, canonical input edits, competitor-curve extraction or reference
promotion. Extracted source artwork remains local and is not published.
"""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import os
import sys

import numpy as np
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'results/uk_2d/g2-source-reconciliation-2026-10-26'
OUT.mkdir(exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(OUT / 'mpl-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from suites.uk_2d import observations
from suites.uk_2d.sources import Raster

SOURCE = Path('/Users/calebbuahin/Downloads/UKBenchmarking')
DATA = SOURCE / 'Benchmarking_Model_Data/Test6 dataset 2010'
CONTROL = ROOT / 'results/uk_2d/g2-reconstruction-2026-10-25/clean-combined'
REPORT = SOURCE / '_SC120002_Benchmarking_2D_hydraulic_models_Report.pdf'
SPEC = DATA / 'EA2DTest6 - May2010.pdf'
PANELS = [(79, 0, 'G2', 'level_m', .18), (79, 1, 'G4', 'level_m', .16),
          (80, 0, 'G5', 'level_m', .14), (80, 1, 'G6', 'level_m', .42),
          (81, 0, 'G2', 'speed_mps', 2.5), (81, 1, 'G4', 'speed_mps', 2.)]
GAUGES = [('G1', 2.65, 1.15), ('G2', 2.65, -.60), ('G3', 4., 1.15),
          ('G4', 4., -.80), ('G5', 5.20, .30), ('G6', -1.87, 1.10)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def components(mask):
    """Eight-neighbor flood fill, independent of the existing sliding template."""
    labels = np.full(mask.shape, -1, int)
    groups = []
    height, width = mask.shape
    for y, x in np.argwhere(mask):
        if labels[y, x] >= 0:
            continue
        label = len(groups)
        stack = [(int(y), int(x))]
        labels[y, x] = label
        pixels = []
        while stack:
            yy, xx = stack.pop()
            pixels.append((yy, xx))
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    ny, nx = yy + dy, xx + dx
                    if (0 <= ny < height and 0 <= nx < width
                            and mask[ny, nx] and labels[ny, nx] < 0):
                        labels[ny, nx] = label
                        stack.append((ny, nx))
        groups.append(np.array(pixels))
    return labels, groups


def diamond_center(pixels):
    if len(pixels) != 13 or not np.array_equal(np.ptp(pixels, axis=0), [4, 4]):
        return None
    center = pixels.mean(axis=0)
    if not np.array_equal(center, np.round(center)):
        return None
    if not np.all(abs(pixels - center).sum(axis=1) <= 2):
        return None
    return int(center[1]), int(center[0])


def in_chart(x, y):
    return 158 < x < 1085 and 70 < y < 800 and not (712 <= x <= 1078 and 76 <= y <= 550)


def source_geometry():
    text = (CONTROL / 'model.inp').read_text()
    sections = {}
    for line in text.splitlines():
        line = line.split(';')[0].strip()
        if not line:
            continue
        if line.startswith('['):
            current = line.strip('[]')
            sections[current] = []
        else:
            sections[current].append(line.split())
    vertices = np.array(sections['2D_VERTICES'], float)
    raw_triangles = np.array(sections['2D_TRIANGLES'], float)
    triangles = raw_triangles[:, :3].astype(int)
    depth = raw_triangles[:, 4]
    p = vertices[triangles]
    centers = p.mean(axis=1)
    area = .5 * np.sum(p[:, :, 0] * np.roll(p[:, :, 1], -1, axis=1)
                      - p[:, :, 1] * np.roll(p[:, :, 0], -1, axis=1), axis=1)
    assert np.allclose(depth, np.where(centers[:, 0] < 0, .4, .02), rtol=0, atol=1e-14)
    assert np.all(raw_triangles[:, 3] == .01)
    assert np.allclose(vertices[:, 2], .155 / .34 * np.maximum(abs(vertices[:, 1]) - 1.46, 0), atol=1e-12)
    options = {row[0]: row[1:] for row in sections['OPTIONS']}
    assert options['REPORT_STEP'] == ['0:00:00.1']
    input_gauges = [(r['Point ID'], float(r['X']), float(r['Y']))
                    for r in csv.DictReader((DATA / 'Test6Aoutput.csv').open())]
    executed = [(r['id'], float(r['x']), float(r['y']))
                for r in csv.DictReader((CONTROL / 'probe-locations.csv').open())]
    assert input_gauges == executed == GAUGES
    edges = {}
    for c in triangles:
        for j in range(3):
            key = tuple(sorted([int(c[j]), int(c[(j + 1) % 3])]))
            edges[key] = edges.get(key, 0) + 1
    gate = [(a, b) for (a, b), count in edges.items()
            if abs(vertices[a, 0]) < 1e-9 and abs(vertices[b, 0]) < 1e-9
            and max(abs(vertices[a, 1]), abs(vertices[b, 1])) <= .5 + 1e-9]
    assert all(edges[key] == 2 for key in gate)
    assert abs(sum(np.linalg.norm(vertices[b, :2] - vertices[a, :2]) for a, b in gate) - 1.) < 1e-9
    angle = np.deg2rad(64)
    along = np.array([np.cos(angle), np.sin(angle)])
    across = np.array([along[1], -along[0]])
    corner = np.array([3.44, -.05])
    building = np.array([corner, corner + .4 * across,
                         corner + .4 * across + .8 * along, corner + .8 * along])
    for a, b in zip(building, np.roll(building, -1, axis=0)):
        length = np.linalg.norm(b - a)
        covered = 0.
        for (i, j), count in edges.items():
            if count != 1:
                continue
            ep = vertices[[i, j], :2]
            cross = (b[0] - a[0]) * (ep[:, 1] - a[1]) - (b[1] - a[1]) * (ep[:, 0] - a[0])
            t = (ep - a) @ (b - a) / length ** 2
            if np.all(abs(cross) < 1e-9) and np.all(t >= -1e-9) and np.all(t <= 1 + 1e-9):
                covered += np.linalg.norm(ep[1] - ep[0])
        assert abs(covered - length) < 1e-9
    # DEM cell centers are data samples, not surveyed polygon corners.
    dem = Raster((DATA / 'Test6ADEM.asc').read_bytes())
    xx, yy = np.meshgrid(dem.x0 + np.arange(dem.nx) * dem.dx,
                         dem.y0 + np.arange(dem.ny) * dem.dx)
    window = (xx > 3) & (xx < 4.6) & (abs(yy) < 1.1)
    threshold_areas = {str(v): float(np.sum(dem.z[window] >= v) * dem.dx ** 2)
                       for v in [.02, .4, 9.99]}
    # Authored reconstruction only; no copied source drawing or competitor traces.
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), layout='constrained')
    ax = axes[0]
    for y in [-1.8, 1.8]:
        ax.plot([-2.5, 5.6], [y, y], color='black')
        ax.plot([-2.5, -.8], [np.sign(y) * 1.46] * 2, '--', color='#9aa8ad')
        ax.plot([0, 5.6], [np.sign(y) * 1.46] * 2, '--', color='#9aa8ad')
    for lo, hi in [(-1.8, -.5), (.5, 1.8)]:
        ax.fill([-.8, 0, 0, -.8], [lo, lo, hi, hi], color='#657781')
    ax.plot([0, 0], [-.5, .5], '--', color='#007c91', label='Released gate / initial interface')
    ring = np.vstack([building, building[0]])
    ax.fill(ring[:, 0], ring[:, 1], color='#c75146', label='UK drawing: 0.8 × 0.4 m, 64°')
    for name, x, y in GAUGES:
        ax.plot(x, y, 'ko', ms=4)
        ax.annotate(name, (x, y), xytext=(5, 5), textcoords='offset points')
    ax.set(xlabel='x (m)', ylabel='y (m)', aspect='equal', title='UK coordinates and physical constraints')
    ax.legend(loc='lower left', fontsize=7)
    y = np.linspace(-1.8, 1.8, 401)
    axes[1].plot(y, .155 / .34 * np.maximum(abs(y) - 1.46, 0), label='Reservoir / channel bed')
    axes[1].plot([-.5, -.5, .5, .5], [.22, 0, 0, .22], '--', label='Rectangular throat (overlaid)')
    axes[1].set(xlabel='y (m)', ylabel='Bed elevation (m)', title='Bank slopes are specified; the throat is rectangular')
    axes[1].legend(fontsize=8)
    fig.savefig(OUT / 'source-geometry.png', dpi=160)
    plt.close(fig)
    return dict(status='PASS', input_sha256=sha(CONTROL / 'model.inp'), gauges=GAUGES,
                gate_width_m=1., gate_internal=True, gate_bed_m=0., report_step_s=.1,
                building_corners_m=building.tolist(), building_area_m2=.32,
                long_side_angle_from_x_deg=64., bank_rise_m=.155, bank_run_m=.34,
                area_m2=float(area.sum()), initial_volume_m3=float(area @ depth),
                dem_blocked_pixel_area_m2=threshold_areas,
                note='Pass means consistency with UK specification, not independent confirmation of laboratory construction.')


def marker_audit():
    pdf = PdfReader(REPORT)
    reference = CONTROL / 'reference'
    original = json.loads((reference / 'digitization-audit.json').read_text())
    oldrows = list(csv.DictReader((reference / 'observations.csv').open()))
    series = []
    strict_rows = []
    all_original = []
    strict_pixels = []
    for page, index, gauge, quantity, top in PANELS:
        rgb = np.asarray(pdf.pages[page - 1].images[index].image.convert('RGB'))
        assert rgb.shape == (900, 1201, 3)
        old = next(v for v in original['charts'] if v['probe'] == gauge and v['quantity'] == quantity)
        assert hashlib.sha256(rgb.tobytes()).hexdigest() == old['embedded_pixels_sha256']
        mask = (rgb[:, :, 0] > 220) & (rgb[:, :, 1] < 80) & (rgb[:, :, 2] > 220)
        labels, groups = components(mask)
        centers = [c for pixels in groups if (c := diamond_center(pixels)) is not None and in_chart(*c)]
        oldset = {tuple(v) for v in old['marker_pixels']}
        assert set(centers).issubset(oldset)
        grouped = {}
        for x, y in centers:
            grouped.setdefault(x, []).append(y)
            strict_pixels.append(dict(probe=gauge, quantity=quantity, x=x, y=y))
        for x, ys in sorted(grouped.items()):
            vals = [(802 - y) / 734 * top for y in ys]
            strict_rows.append(dict(time_s=(x - 156) / 931 * 60, probe=gauge, quantity=quantity,
                                    value=float(np.mean(vals)), value_min=min(vals), value_max=max(vals),
                                    isolated_marker_count=len(vals)))
        for x, y in old['marker_pixels']:
            all_original.append(dict(probe=gauge, quantity=quantity, x=x, y=y,
                                     connected_pixels=len(groups[labels[y, x]]), strict=(x, y) in centers))
        # Verify every historical CSV value by a second direct pixel-to-axis calculation.
        oldgroup = {}
        for x, y in old['marker_pixels']:
            oldgroup.setdefault(x, []).append(y)
        saved = [v for v in oldrows if v['probe'] == gauge and v['quantity'] == quantity]
        assert len(saved) == len(oldgroup)
        for value, (x, ys) in zip(saved, sorted(oldgroup.items())):
            assert abs(float(value['time_s']) - (x - 156) / 931 * 60) < 1e-12
            assert abs(float(value['value']) - (802 - np.mean(ys)) / 734 * top) < 1e-12
        series.append(dict(probe=gauge, quantity=quantity, original_pixels=len(oldset),
                           strict_pixels=len(centers), original_bins=len(saved), strict_bins=len(grouped),
                           attached_candidates=len(oldset) - len(centers),
                           one_pixel_time_s=60 / 931, one_pixel_value=top / 734))
    strict = OUT / 'strict-reference'
    strict.mkdir(exist_ok=True)
    with (strict / 'observations.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(strict_rows[0]))
        writer.writeheader(); writer.writerows(strict_rows)
    provenance = json.loads((reference / 'observations.json').read_text())
    provenance.update(csv_sha256=sha(strict / 'observations.csv'),
                      extraction='Independent eight-neighbor connected components; exactly 13 pixels, 5×5 support, integer center and Manhattan radius two; same chart bounds and legend exclusion.',
                      coverage='Audit-only, more restrictive visibility-selected subset. Does not replace historical reference or represent the complete experiment.',
                      peer_review_status='Independent algorithm and visual review by the same assistant, not a second-person review.')
    (strict / 'observations.json').write_text(json.dumps(provenance, indent=2) + '\n')
    with (OUT / 'marker-connectivity.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(all_original[0]));writer.writeheader();writer.writerows(all_original)
    save('strict-marker-pixels.json', strict_pixels)
    probe_rows = list(csv.DictReader((CONTROL / 'probe-locations.csv').open()))
    output = list(csv.DictReader((CONTROL / 'probes.csv').open()))
    times = np.array(sorted({float(r['time_s']) for r in output}))
    values = np.array([[float(r[key]) for r in output if float(r['time_s']) == t
                       for key in ['depth_m', 'level_m', 'speed_mps']] for t in times])
    comparison = observations.compare(strict, {}, times, values, probe_rows)
    save('strict-comparison.json', comparison)
    # Plot only measurements and our unchanged control, never competing curves.
    fig, axs = plt.subplots(2, 1, figsize=(10, 7), layout='constrained')
    for ax, quantity, label in zip(axs, ['level_m', 'speed_mps'], ['Level (m)', 'Speed (m/s)']):
        own = [r for r in output if r['probe'] == 'G2']
        original_rows = [r for r in oldrows if r['probe'] == 'G2' and r['quantity'] == quantity]
        new = [r for r in strict_rows if r['probe'] == 'G2' and r['quantity'] == quantity]
        ax.plot([float(r['time_s']) for r in own], [float(r[quantity]) for r in own], color='#007c91', label='Corrected original-mesh control')
        ax.scatter([float(r['time_s']) for r in original_rows], [float(r['value']) for r in original_rows],
                   marker='D', facecolors='none', edgecolors='#aaaaaa', s=28, label='Historical recovered subset')
        ax.scatter([r['time_s'] for r in new], [r['value'] for r in new], color='#bd493b', s=18,
                   label='Strict disconnected-diamond subset', zorder=5)
        ax.set(xlim=(0, 30), xlabel='Time (s)', ylabel=label)
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('G2 source-marker audit: unchanged simulation, two visibility-selected subsets')
    fig.savefig(OUT / 'g2-marker-audit.png', dpi=160);plt.close(fig)
    return dict(status='PASS', axis_conversion='All historical binned times and values reproduce independently within 1e-12.',
                series=series, strict_comparison=comparison,
                limitation='Connectivity rejects touching valid measurements as well as possible same-colour curve connections. Rejected does not mean false. Sparse subsets have different time coverage and their RMSEs cannot be ranked as solver changes.')


def main():
    assert sha(ROOT / 'corpus/uk-ea-2d/uk-ea-2013-t6a/model.inp') == 'd40e3cb0b2c3123764bf6b54a4f10c53b2e388fff702890fe32eed07b948bd10'
    geometry = source_geometry()
    markers = marker_audit()
    sources = {str(p): sha(p) for p in [SPEC, REPORT, DATA / 'Test6Aoutput.csv', DATA / 'Test6ADEM.asc',
                                       CONTROL / 'model.inp', CONTROL / 'reference/observations.csv']}
    save('audit.json', dict(state='COMPLETE', sources=sources, geometry=geometry, markers=markers,
                           qualification='Source and observation audit only; no new simulation, source-backed solver correction or baseline promotion.'))
    print(json.dumps(dict(geometry=geometry, marker_series=markers['series'], metrics=markers['strict_comparison']['metrics']), indent=2))


if __name__ == '__main__':
    main()
