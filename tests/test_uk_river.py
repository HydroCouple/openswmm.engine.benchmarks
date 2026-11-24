"""Reference integrity, physical representation and independent-suite failures."""
import json
from pathlib import Path
import numpy as np
import pytest
from harness import corpus,scoring
from suites.uk_river import references,build,suite,report


def test_all_committed_cases_and_reference_identities():
    for path in references.CORPUS.glob('*/case.json'):
        case,meta=suite.validate(path.parent)
        assert case['end'] in [10,3600,14400,108000]
        assert meta['kind'] in ['analytic','observed','unavailable']
        if meta['kind']!='unavailable':assert meta['source_hashes']


def test_committed_step_clocks_are_explicit():
    """A bare step token is legacy decimal HOURS: uk-river-l's REPORT_STEP 0.04
    became 144 s (clamped to its 10 s run), so its 2D output held one frame and
    sampling raised 'Invalid output time axis' (Nightly 45045451271)."""
    import re
    for path in references.CORPUS.glob('*/model.inp'):
        text=path.read_text(encoding='utf-8')
        for key in ['REPORT_STEP','WET_STEP','DRY_STEP']:
            field=re.search(r'^'+key+r'\s+(\S+)',text,re.M)
            assert field is None or field.group(1).count(':')==2, (path.parent.name,key,field.group(1))


def test_original_laboratory_grid_and_gauge_arrivals():
    data=np.genfromtxt(build.reference('l')/'reference.csv',delimiter=',',names=True)
    assert data.shape==(251,)
    assert np.allclose(data['time_s'],np.arange(251)*.04,atol=1e-12,rtol=0)
    assert data['S1'][0]==.3 and data['S4'][0]==.003
    # These source arrivals are independent of solver predictions.
    assert data['time_s'][np.flatnonzero(data['S2']>.01)[0]]==3
    assert data['time_s'][np.flatnonzero(data['S3']>.01)[0]]==4.32


def test_lab_table_duplicate_or_missing_time_fails():
    class Page:
        def extract_text(self):return '0.00 0.300 0.003 0.003 0.003'
    class Reader:pages=[Page()]*92
    with pytest.raises(ValueError,match='Incomplete or duplicate'):references.laboratory_table(Reader())


def test_lab_tapers_preserve_physical_geometry_and_volume():
    for key in ['l','l-fine']:
        s=build.spec(key);v,c,centre,area=build.geometry(key,s)
        assert area.sum()==pytest.approx(19.3*.5-(.5-.1)*(1+.2))
        assert np.ptp(v[np.isclose(v[:,0],14.),1])==pytest.approx(.1)
        assert np.ptp(v[np.isclose(v[:,0],13.9),1])==pytest.approx(.3)
        assert np.sum(area[centre[:,0]<6.1])==pytest.approx(6.1*.5)


def test_source_a_axis_and_published_endpoint_preserved():
    a=np.genfromtxt(build.reference('a1')/'reference.csv',delimiter=',',names=True)
    assert np.array_equal(a['chainage_m'],np.arange(101))
    assert a['level_m'][0]==.87803 and a['level_m'][-1]==1.32769
    s=build.spec('a1');v,c,centre,area=build.geometry('a1',s)
    assert v[0,2]==a['bed_m'][-1] and v[s['nx'],2]==a['bed_m'][0]


def test_published_bridge_targets_are_measured_not_model_rows():
    a=np.genfromtxt(build.reference('j')/'reference.csv',delimiter=',',names=True,dtype=None,encoding='utf-8')
    assert np.allclose(a['afflux_m'],[.035,.070,.032,.062])
    assert np.allclose(a['flow_m3s'],[.02097,.03443,.02098,.03429])


def test_altered_or_unqualified_reference_cannot_silently_validate(tmp_path,monkeypatch):
    folder=tmp_path/'ref';folder.mkdir();(folder/'reference.csv').write_text('altered', encoding='utf-8')
    (folder/'reference.json').write_text(json.dumps(dict(kind='analytic',csv_sha256='wrong')), encoding='utf-8')
    monkeypatch.setattr(suite,'reference',lambda key:folder)
    path=references.CORPUS/'uk-river-a1'
    with pytest.raises(ValueError,match='Altered independent reference'):suite.validate(path)
    (folder/'reference.json').write_text(json.dumps(dict(kind='unavailable',reason='phase/linear friction unresolved')), encoding='utf-8')
    assert suite.compare('e',{},None,None,None)['status']=='unavailable'


def test_empty_nonfinite_fit_rejected():
    with pytest.raises(ValueError):suite.norms([],[])
    with pytest.raises(ValueError):suite.norms([float('nan')],[0])
    assert suite.norms([2,4],[1,3])['rmse_m']==1


def test_missing_bridge_execution_fails_required_coverage(tmp_path):
    env=suite.run(['--only','j','--require-complete','--output-dir',str(tmp_path)])
    assert not env['coverage']['complete'] and env['coverage']['unexecuted']==['j']
    assert scoring.exit_code(env)==1


def test_report_ignores_old_excluded_case_files(tmp_path):
    old=tmp_path/'uk-river-a1';old.mkdir();(old/'metrics.json').write_text('not current data', encoding='utf-8')
    (tmp_path/'scores.json').write_text(json.dumps(dict(cells=[dict(case='uk-river-a1',solver='swmm2d-cpu-full-swe-rk2',verdict='SKIP')],coverage={})), encoding='utf-8')
    report.build(tmp_path)
    assert '![Test A' not in (tmp_path/'report.md').read_text(encoding='utf-8')


def test_river_explicit_selection_cannot_enter_parity(monkeypatch,tmp_path):
    river=corpus.Case(tmp_path/'river',meta=dict(id='uk-river-a1',tags=['hydraulics','uk_ea_river'],tiers=['nightly']))
    from suites.parity import suite as parity
    class Registry:
        def resolved(self):return {}
    monkeypatch.setattr(parity.corpus,'load',lambda:[river])
    monkeypatch.setattr(parity.engines,'resolve_all',lambda *a,**k:Registry())
    monkeypatch.setattr(parity,'RESULTS',tmp_path)
    monkeypatch.setattr(parity,'_manifest',lambda tier:dict(select='hydraulics'))
    env=parity.run(['--tier','nightly','--only','uk-river-a1'])
    assert all(c['case']!='uk-river-a1' for c in env['cells']) and scoring.exit_code(env)==1


def test_submission_smoke_dispatches_river_to_its_own_suite(monkeypatch,tmp_path):
    from tools import smoke_cases
    river=corpus.Case(tmp_path/'river',meta=dict(id='uk-river-a1',tags=['hydraulics','uk_ea_river']))
    monkeypatch.setattr(smoke_cases.corpus,'load',lambda:[river])
    captured=[]
    def run(args):
        captured.extend(args)
        return dict(cells=[dict(case='uk-river-a1',verdict='PASS')])
    monkeypatch.setattr(suite,'run',run)
    monkeypatch.setattr(suite,'report',lambda args:[])
    from suites.parity import suite as parity
    def reject(*args,**kwargs):raise AssertionError('River entered competitor parity')
    monkeypatch.setattr(parity,'run',reject)
    assert smoke_cases.main(['--only','uk-river-a1'])==0
    assert captured[captured.index('--only')+1]=='a1'


def test_changed_analysis_or_reference_invalidates_numerical_anchor(tmp_path):
    folder=tmp_path/'baselines/cpu-full-swe-rk2';folder.mkdir(parents=True)
    (folder/'baseline.json').write_text(json.dumps(dict(model_sha256='model',analysis_sha256='old',reference_sha256='ref')), encoding='utf-8')
    with pytest.raises(ValueError,match='Baseline identity mismatch'):
        suite.regression(tmp_path,dict(model_sha256='model',probes_sha256='probes'),{},None,'ref')


def test_numerical_pass_cannot_be_badged_as_analytical_validation():
    env=dict(suite='uk_river',cells=[dict(case='uk-river-a1',solver='swmm2d-cpu-full-swe-rk2',
        reference_class='self_consistency',independent_reference_class='analytic',verdict='PASS')],
        coverage=dict(requested=11,executed=10,complete=False))
    badges=scoring.badges([env])
    assert 'verification' not in badges
    assert badges['uk-river-coverage']['color']==scoring.BADGE_YELLOW


def test_reporting_rejects_a_reference_changed_after_execution(tmp_path):
    work=tmp_path/'uk-river-a1';(work/'reference').mkdir(parents=True)
    model=b'original executed model\n';(work/'model.inp').write_bytes(model)
    references.write_json(work/'case.json',dict(key='a1',model_sha256=references.digest(model)))
    references.write_json(work/'metrics.json',{})
    references.write_json(work/'reference/reference.json',dict(kind='analytic',csv_sha256='original'))
    (work/'reference/reference.csv').write_text('tampered',encoding='utf-8')
    references.write_json(work/'run-manifest.json',dict(reference_hashes={'reference.csv':'original'}))
    references.write_json(tmp_path/'scores.json',dict(cells=[dict(case='uk-river-a1',solver='swmm2d-cpu-full-swe-rk2',
        verdict='PASS',checks=dict(continuity=True))],coverage={}))
    with pytest.raises(ValueError,match='reference changed before reporting'):report.build(tmp_path)


def test_empty_repeat_cannot_cover_an_executed_assessment(tmp_path):
    from suites.uk_river.repeat import attach
    original=tmp_path/'original';repeated=tmp_path/'repeat'
    references.write_json(original/'scores.json',dict(cells=[dict(case='uk-river-l',solver='swmm2d-cpu-full-swe-rk2',checks=dict(continuity=True))]))
    references.write_json(repeated/'scores.json',dict(cells=[],coverage=dict(complete=True)))
    with pytest.raises(ValueError,match='every executed assessment'):attach(original,repeated)
