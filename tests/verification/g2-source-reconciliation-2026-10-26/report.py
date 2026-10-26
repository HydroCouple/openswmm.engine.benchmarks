"""Package the source audit without redistributing original chart artwork."""
from pathlib import Path
import hashlib
import html
import json
import shutil

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'results/uk_2d/g2-source-reconciliation-2026-10-26'
HERE = Path(__file__).parent


def table(headers, rows):
    def cells(tag, values):
        return ''.join(f'<{tag}>{html.escape(str(v))}</{tag}>' for v in values)
    return '<table><thead><tr>' + cells('th', headers) + '</tr></thead><tbody>' + ''.join(
        '<tr>' + cells('td', row) + '</tr>' for row in rows) + '</tbody></table>'


def main():
    audit = json.loads((OUT / 'audit.json').read_text())
    assert audit['state'] == 'COMPLETE'
    assert audit['geometry']['status'] == audit['markers']['status'] == 'PASS'
    assert 'Ran 4 tests' in (OUT / 'marker-tests.log').read_text() and 'OK' in (OUT / 'marker-tests.log').read_text()
    source = OUT / 'source'; source.mkdir(exist_ok=True)
    for p in HERE.glob('*.py'):
        shutil.copy2(p, source / p.name)
    source_review = dict(
        date='2026-10-26', state='COMPLETE_WITH_SOURCE_LIMITATIONS',
        controlling_spec='EA2DTest6 - May2010.pdf, pages 1–3; 2013 SC120002/R Appendix A.6, PDF pages 153–155',
        drawing_review='Full specification page and four embedded drawing pieces inspected visually. Long building side is 64 degrees from x. Bank slopes and rectangular throat are explicit.',
        report_review='SC120002/R section 4.7.1, PDF pages 78–84; original G2 embedded level and speed panels inspected visually. Source pixels match historical extraction hashes.',
        gate='UK specification gives an initial-value release at x=0 and no finite gate-opening schedule. Current internal gate interface and bed z=0 match. No evidence establishes a missing sill or opening duration.',
        initial_conditions='UK test specification and 2013 Appendix A.6 say depth 0.4/0.02 m; the main report introduction says water level. Previous uniform-level sensitivity did not resolve G2. This audit keeps the explicit test specification.',
        legacy_lead=dict(url='https://www.yumpu.com/en/document/view/52377181/dam-break-flow-experiment-the-isolated-building-test-case-impact',
                         access='Search-indexed transcription of the authors’ earlier IMPACT specification. Direct page required robot verification; original IMPACT host was unavailable. No original PDF acquired or authenticated.',
                         b1_x_m=3.40, downstream_depth_m=.01,
                         qualification='Provisional version discrepancy only. Do not substitute these values into the UK case or infer actual experimental initial conditions without an authoritative original.'),
        primary_publication=dict(url='https://doi.org/10.1080/00221686.2007.9521830',
                                 institutional_record='https://research.dial.uclouvain.be/entities/publication/1be139aa-afe4-44b5-9a87-710c1a15076c',
                                 access='Institutional abstract and metadata found. Publisher full text unavailable to this audit; original instrument/time-series and gate-motion records not acquired.'),
        disposition='No geometry, initial-condition or release change is established as a correction. No new hydraulic run is justified by this source audit alone.',
        next_evidence=['Authoritative original building corner coordinates and applicable experiment/version',
                       'Original G2/G6 water-level series and G2 velocity components with measurement elevation/averaging and time origin',
                       'Gate opening history and actual downstream initial water level for the recorded run'],
        observation_review='Independent algorithm, same assistant visual review; no second-person or original-instrument validation claimed.')
    (OUT / 'source-review.json').write_text(json.dumps(source_review, indent=2, ensure_ascii=False) + '\n')
    reconciliation = [
        ['Gauge coordinates', 'UK Test6Aoutput.csv and drawing', 'All six match exactly; G2 (2.65, −0.60) m', 'Retain'],
        ['Throat / gate bed', 'Drawing section BB and explicit release x=0', '1.0 m rectangular width; bed 0; open internal interface', 'No missing sill shown'],
        ['Channel / reservoir', 'Drawing sections AA and CC', '3.6 m total width; 0.155 m rise over each 0.34 m bank', 'Sloping banks are specified'],
        ['Building', 'UK drawing inset and b1 dimensions', '0.8 × 0.4 m, 64° from x; b1 (3.44, −0.05) m', 'Retain UK geometry'],
        ['Initial condition', 'Test specification §3 and report Appendix A.6', 'Depth 0.4 m upstream / 0.02 m downstream', 'Main report wording differs; retain explicit specification'],
        ['Output', 'Test specification §5', '0.1 s reporting; 30 s diagnostic retained separately from 120 s qualification', 'No output rescaling or clock fitting'],
        ['Gate opening', 'UK initial-value problem', 'Instantaneous release; no measured motion schedule supplied', 'Do not invent a finite opening time'],
        ['Earlier IMPACT version', 'Search-indexed transcription only', 'b1 x=3.40 m; downstream depth 0.01 m', 'Provisional conflict, original needed'],
    ]
    counts = table(['Gauge / quantity', 'Historical markers', 'Strict markers', 'Historical bins', 'Strict bins'],
                   [[r['probe'] + ' / ' + r['quantity'], r['original_pixels'], r['strict_pixels'],
                     r['original_bins'], r['strict_bins']] for r in audit['markers']['series']])
    metrics = table(['Gauge / quantity', 'Samples', 'Covered intervals (s)', 'RMSE', 'Bias'],
                    [[r['probe'] + ' / ' + r['quantity'], r['n'], f"{r['covered_duration_s']:.3f}",
                      f"{r['rmse']:.6f}", f"{r['bias']:.6f}"] for r in audit['markers']['strict_comparison']['metrics']])
    body = '''<h1>Test 6A: source geometry and observation audit</h1>
<p>26 October 2026 · Source reconciliation; no new hydraulic simulation</p>
<p class="finding">The executed drawing geometry, gauge locations and output cadence agree with the UK specification. A stricter independent marker extraction still shows the missing G2 depth rise and slowdown. No verified source error establishes a geometry, gate or initial-condition correction.</p>
<h2>What the supplied sources actually specify</h2>''' + table(['Item', 'Controlling source', 'Finding', 'Disposition'], reconciliation) + '''
<p>The drawing is rectangular in plan. Its reservoir and downstream cross-sections include shallow sloping banks; the narrow throat has vertical sides and a flat bed. The 64° angle is between the long building side and the x direction, as drawn in the inset. The source audit checks these segments against the executed input independently of the mesh-generator function.</p>
<img src="source-geometry.png" alt="Authored reconstruction of the UK geometry and gauge coordinates">
<p>DEM threshold areas are not survey dimensions: the blocked-pixel area near the building varies from 0.415 m² at elevation 0.02 m to 0.405 m² at 0.4 m and 0.255 m² near its 10 m artificial top. The dimensioned building area is 0.32 m². This threshold dependence prevents treating one raster mask as a uniquely defined physical footprint. The existing source-drawing geometry is retained.</p>
<h2>Conflicting versions and unresolved metadata</h2>
<p>The UK test specification and report appendix explicitly prescribe initial <em>depths</em> of 0.4 and 0.02 m. The main report introduction uses the term water level. The prior uniform-level diagnostic did not resolve G2; this source audit does not repeat or silently substitute it.</p>
<p>A search-indexed transcription of the earlier author-written IMPACT specification lists b1 at x=3.40 m and downstream depth 0.01 m. The UK drawing and specification give 3.44 m and 0.02 m. This is a provisional source-version discrepancy: direct access to the mirror required robot verification, the original IMPACT site was unavailable, and no authenticated original was obtained. It is insufficient evidence to change the UK benchmark or assert which initialization produced the published measurements. See the <a href="https://www.yumpu.com/en/document/view/52377181/dam-break-flow-experiment-the-isolated-building-test-case-impact">indexed IMPACT document</a> and <a href="source-review.json">retrieval limitations</a>.</p>
<p>The UK files provide no finite gate-opening history. The implemented release at x=0, internal hydraulic connection and zero gate-bed elevation match the specified initial-value problem. No missing sill or elevation offset was found. The 2007 <a href="https://research.dial.uclouvain.be/entities/publication/1be139aa-afe4-44b5-9a87-710c1a15076c">UCL institutional publication record</a> identifies both ADV and image-based velocity measurements, but its abstract does not establish the measurement operator for each UK curve. Full original records remain necessary.</p>
<h2>Correction to the extraction description</h2>
<p>The historical extractor searches a 5×5 diamond-shaped magenta pixel pattern and excludes the legend. It does <strong>not</strong> ensure that the detected shape is disconnected from neighboring magenta graphics. Earlier wording that all retained markers were isolated and all overlapping or ambiguous cases were excluded was too strong. Attached patterns can be real touching measurement markers or connections to the same-colour continuous curve; connectivity alone cannot decide which.</p>
<p>The new implementation flood-fills eight-connected magenta components and accepts only an entire 13-pixel diamond with 5×5 bounds, an integer centre and Manhattan radius two. It does not call the original sliding-template detector. Four synthetic tests check isolated acceptance, attached-line rejection, diagonal-contact rejection and wrong-shape rejection. Plot bounds and legend exclusion are unchanged. Every historical CSV time and value also reproduces independently from its recorded pixel coordinates within 10⁻¹², ruling out a conversion inconsistency in those records.</p>''' + counts + '''
<p>At G2 the stricter rule retains 15 level markers, binned into 11 times, and 138 speed markers, binned into 117 times. These remain far from the unchanged control after the secondary transition. At about 27.13 s a disconnected level marker is 0.1072 m; at about 29.84 s another is 0.1003 m, while the control remains near 0.03 m. Disconnected speed markers likewise retain the late low-velocity cluster. This supports the existence of the discrepancy, not complete accuracy of the recovered experiment.</p>
<img src="g2-marker-audit.png" alt="G2 historical and strict recovered observations against the same simulation">
<h2>Strict-subset errors and their limits</h2>''' + metrics + '''
<p>Units are metres for levels and metres per second for speeds. These errors use the same interpolation and one-second gap policy as previous assessments. The stricter G2 level series covers only 2.51 s of connected observation intervals; its isolated late points have zero interval weight but remain visible in the plot and maximum residual. G2 speed covers 15.21 s. Changing subsets changes coverage and weights: lower or higher RMSE here is not solver improvement or deterioration.</p>
<p>The independent algorithm and visual checks were performed by the same assistant. They are not a second-person review, do not recover hidden or overlapping measurements, and do not resolve instrument uncertainty. The historical reference files and metrics remain byte-identical; the strict subset is an audit artifact, not a promoted validation reference. No competing model curves are reproduced.</p>
<h2>Practical next step</h2>
<p>Keep the UK drawing geometry and FLAT/MEAN control. Before another source-based variant, obtain the authoritative building-corner table and applicable experiment version, original G2/G6 level and G2 velocity records with instrument metadata, and the gate-opening/initial-water-level record. This audit does not justify narrowing the throat, rotating or enlarging the building, adding a gate sill, changing downstream depth to 0.01 m, or tuning wall friction. Further solver work should be driven by an independent diagnostic that isolates a specific numerical deficiency.</p>
<h2>Evidence</h2>
<p>Controlling sources: <a href="https://assets.publishing.service.gov.uk/media/6033a9bbd3bf7f72182e99ca/Benchmarking_Model_Data.zip">official UK model archive</a> (Test 6 specification pp. 1–3 and gauge CSV); <a href="https://assets.publishing.service.gov.uk/media/6033a943d3bf7f721f4b0d49/_SC120002_Benchmarking_2D_hydraulic_models_Report.pdf">SC120002/R</a> §4.7.1 and Appendix A.6. All local source hashes are retained; original artwork stays local.</p>
<p><a href="audit.json">Complete audit</a> · <a href="source-review.json">Source decisions and limitations</a> · <a href="marker-connectivity.csv">Every historical marker’s connectivity</a> · <a href="strict-marker-pixels.json">Strict marker coordinates</a> · <a href="strict-reference/observations.csv">Strict recovered observations</a> · <a href="strict-reference/observations.json">Observation provenance</a> · <a href="strict-comparison.json">Strict-subset metrics</a> · <a href="marker-tests.log">Four detector tests</a> · <a href="source/audit.py">Audit reproducer</a> · <a href="source/test_markers.py">Detector tests</a> · <a href="source/report.py">Report builder</a></p>
<p>Run the scripts in their original benchmark repository directory, tests/verification/g2-source-reconciliation-2026-10-26, with the existing Python environment, local PDFs and completed reconstruction control. No engine binary is executed. The report copies are source archives and depend on those documented local inputs.</p>'''
    page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Test 6A source and observation audit</title><style>body{max-width:1120px;margin:48px auto;padding:0 24px;font:17px/1.6 system-ui;color:#193042;background:#fafcfd}h1{line-height:1.15}h2{margin-top:2em;color:#075969}.finding{padding:20px;background:#e5f1f4;border-left:5px solid #007c91}table{width:100%;border-collapse:collapse;font-size:14px}th,td{border-bottom:1px solid #cbd8df;padding:9px;text-align:left}img{width:100%;height:auto;margin:14px 0}a{color:#006b86}</style><main>' + body + '</main></html>'
    (OUT / 'report.html').write_text(page)
    files = ['report.html', 'audit.json', 'source-review.json', 'marker-connectivity.csv',
             'strict-marker-pixels.json', 'strict-reference/observations.csv', 'strict-reference/observations.json',
             'strict-comparison.json', 'marker-tests.log', 'source-geometry.png', 'g2-marker-audit.png']
    files += [str(p.relative_to(OUT)) for p in source.glob('*.py')]
    manifest = dict(state='COMPLETE', scope='Source reconciliation with unresolved original records; no new hydraulic run.',
                    files={name: hashlib.sha256((OUT / name).read_bytes()).hexdigest() for name in files})
    (OUT / 'publication-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Sealed', len(files), 'artifacts')


if __name__ == '__main__':
    main()
