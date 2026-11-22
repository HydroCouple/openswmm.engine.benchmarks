"""Scientific failure modes of the independent-reference UK suite."""
import csv
import io
import json
from pathlib import Path
import zipfile
import numpy as np
import pytest
from harness import corpus, scoring
from suites.uk_2d import sources, sampling, observations, checks, suite, baseline
from tools.smoke_cases import partition


def test_raster_row_order_interpolation_and_nodata():
    raw=b'ncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 2\nNODATA_value -9999\n10 14\n2 6\n'
    r=sources.Raster(raw)
    assert r.sample(1,1)==2 and r.sample(3,3)==14
    assert r.sample(2,2)==8
    with pytest.raises(ValueError):r.sample(0,0)
    with pytest.raises(ValueError):sources.Raster(raw.replace(b'14',b'-9999')).sample(2,2)


def test_altered_archive_rejected(tmp_path):
    path=tmp_path/'altered.zip';path.write_bytes(b'not the locked source')
    with pytest.raises(ValueError,match='altered source'):sources.Sources(path)


def test_corpus_byte_identities_survive_checkout():
    from suites.uk_2d.build import COLLECTION
    for path in sorted(COLLECTION.glob('uk-ea-*')):
        case=suite.validate_case(path)
        review=path/'baselines/cpu-full-swe-rk2/baseline.json'
        record=json.loads(review.read_text(encoding='utf-8'))
        assert record['model_sha256']==case['model_sha256']
        assert record['probes_sha256']==case['probes_sha256']
        assert record['analysis_sha256']==suite.analysis_hash()
        assert record['data_sha256']==sources.digest(review.with_name('baseline.npz').read_bytes())
        reference=path/'reference/observations.json'
        if reference.exists():
            expected=json.loads(reference.read_text(encoding='utf-8'))['csv_sha256']
            assert sources.digest(reference.with_name('observations.csv').read_bytes())==expected


def test_total_discharge_integration_respects_seconds():
    assert sources.integral(np.array([[0,0],[10,65.5],[20,65.5],[30,0]]))==1310


def test_probe_does_not_cross_a_wall():
    vertices=np.array([[0,0],[1,0],[1,1],[0,1],[2,0],[3,0],[3,1],[2,1]])
    cells=np.array([[0,1,2,3],[4,5,6,7]])
    assert sampling.locate_probes(vertices,cells,[dict(id='a',x=.5,y=.5)])[0]['face']==0
    with pytest.raises(ValueError,match='outside'):sampling.locate_probes(vertices,cells,[dict(id='wall',x=1.5,y=.5)])


def test_mass_gate_independently_catches_lost_inflow():
    c=dict(initial_volume_m3=0,forcing=[[0,1],[10,1]],boundary_kind='flow',numerical_limits=dict(min_depth_m=-1e-10,continuity_pct=.5))
    data=dict(ledger={'continuity_error':0},minimum_depth_m=0,final_volume_m3=9)
    result=checks.numerical(c,data)
    assert result['checks']['continuity'] and not result['checks']['independent_volume']


def _output(path, times, nan=False):
    import h5py
    with h5py.File(path,'w') as f:
        f['time']=times;f['time'].attrs['units']='seconds since 2026-01-01 00:00:00'
        for key,value in dict(Mesh2_node_x=[0,1,1,0],Mesh2_node_y=[0,0,1,1],Mesh2_face_nodes=[[0,1,2,3]],Mesh2_face_z=[0.],Mesh2_face_area=[1.],Mesh2_face_x=[.5],Mesh2_face_y=[.5]).items():f[key]=value
        for key in ['depth','vx','vy']:
            f['Mesh2_face_'+key]=np.full((len(times),1),np.nan if nan else 1.)
        f.create_group('mass_balance_2d').attrs['continuity_error']=0.


@pytest.mark.parametrize('times,nan,error',[([1],False,'Invalid output time axis'),([.5,2],False,'misaligned'),([1,2],True,'NaN')])
def test_truncated_misaligned_and_nonfinite_output_rejected(tmp_path,times,nan,error):
    p=tmp_path/'surface.h5';_output(p,times,nan)
    c=dict(end=2,step=1,cell_count=1,area_m2=1,uk_test='3')
    with pytest.raises(ValueError,match=error):sampling.extract(p,c,[dict(id='a',x=.5,y=.5)],tmp_path)


def test_observations_absent_do_not_validate(tmp_path):
    result=observations.compare(tmp_path,{},np.arange(3),np.ones((3,3)),[dict(id='a')])
    assert result['status']=='unavailable' and not result['metrics']


def test_observation_gaps_and_hashes(tmp_path):
    data='time_s,probe,quantity,value\n0,a,level_m,1\n1,a,level_m,1\n10,a,level_m,1\n11,a,level_m,1\n'
    (tmp_path/'observations.csv').write_text(data, encoding='utf-8')
    meta=dict(source='laboratory',citation='test fixture',quantity_definitions='level',datum='zero',time_origin='gate release',max_gap_s=2,kind='observed',csv_sha256=sources.digest(data.encode()))
    (tmp_path/'observations.json').write_text(json.dumps(meta), encoding='utf-8')
    result=observations.compare(tmp_path,{},np.arange(12),np.ones((12,3)),[dict(id='a')])
    assert result['metrics'][0]['covered_duration_s']==2
    (tmp_path/'observations.csv').write_text(data.replace(',1',',2'), encoding='utf-8')
    with pytest.raises(ValueError,match='hash'):observations.compare(tmp_path,{},np.arange(12),np.ones((12,3)),[dict(id='a')])


def test_dedicated_dispatch_handles_explicit_selection(monkeypatch,tmp_path):
    uk=corpus.Case(tmp_path/'uk',meta={'id':'uk','tags':['uk_ea_2d'],'tiers':['nightly']})
    other=corpus.Case(tmp_path/'normal',meta={'id':'normal','tags':['hydraulics'],'tiers':['nightly']})
    monkeypatch.setattr(corpus,'load',lambda:[uk,other])
    assert partition(['uk','normal'])==(['normal'],['uk'])
    from suites.parity import suite as parity
    class Registry:
        def resolved(self):return {}
    monkeypatch.setattr(parity.engines,'resolve_all',lambda *a,**k:Registry())
    monkeypatch.setattr(parity,'RESULTS',tmp_path)
    env=parity.run(['--tier','nightly','--only','uk'])
    assert all(c['case']!='uk' for c in env['cells'])
    assert scoring.exit_code(env)==1


def test_required_coverage_fails_when_engine_missing(tmp_path):
    env=suite.run(['--only','1','--exe',str(tmp_path/'absent'),'--output-dir',str(tmp_path)])
    assert scoring.exit_code(env)==1
    assert env['coverage']['executed']==0 and env['coverage']['required_missing']==['1']


def test_baseline_changes_and_tampering_are_detected(tmp_path):
    data=tmp_path/'baseline.npz';np.savez(data,times=[1,2],values=[[1,2,3],[1,2,3]])
    case=dict(model_sha256='model',probes_sha256='probes')
    meta=dict(reviewer='fixture',reason='unit check',engine_sha='abc',binary_sha256={'exe':'hash'},date='2026-10-22',
              analysis_sha256='analysis',data_sha256=sources.digest(data.read_bytes()),atol=1e-6,rtol=1e-5,**case)
    (tmp_path/'baseline.json').write_text(json.dumps(meta), encoding='utf-8')
    assert checks.regression(tmp_path,case,np.array([1,2]),np.ones((2,3)),'analysis')['verdict']=='BASELINE-FAIL'
    data.write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='hash'):checks.regression(tmp_path,case,np.array([1,2]),np.ones((2,3)),'analysis')


def test_failing_numerical_run_cannot_be_promoted(tmp_path):
    (tmp_path/'metrics.json').write_text(json.dumps({'checks':{'mass':False}}), encoding='utf-8')
    (tmp_path/'run-manifest.json').write_text('{}', encoding='utf-8');(tmp_path/'case.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError,match='failing'):baseline.promote(tmp_path,'fixture','not acceptable')


def test_digitizer_recovers_only_isolated_diamonds_and_excludes_legend():
    from suites.uk_2d.digitize import markers
    rgb=np.full((900,1201,3),255,dtype=np.uint8)
    for cx,cy in [(200,400),(755,164)]:
        for y in range(-2,3):
            for x in range(-2,3):
                if abs(x)+abs(y)<=2:rgb[cy+y,cx+x]=[255,0,255]
    # Continuous model-like strokes must not be treated as measurement points.
    rgb[300:500,300:303]=[255,0,255]
    assert markers(rgb).tolist()==[[200,400]]


def test_subsecond_output_interval_is_seconds_not_timeseries_hours():
    from suites.uk_2d.build import clock
    assert clock(.1)=='0:00:00.1'
    assert clock(60)=='0:01:00'


def test_timeseries_fractional_seconds_have_a_distinct_hours_conversion():
    from suites.uk_2d.build import series_clock
    assert abs(float(series_clock(.1))*3600-.1)<1e-12


def test_preflight_rejects_wrong_report_unit_even_with_matching_input_hash(tmp_path):
    from suites.uk_2d.build import COLLECTION
    import shutil
    source=COLLECTION/'uk-ea-2013-t01'
    for name in ['case.json','model.inp','probes.csv']:shutil.copy2(source/name,tmp_path/name)
    inp=tmp_path/'model.inp';text=inp.read_text(encoding='utf-8').replace('REPORT_STEP 0:01:00','REPORT_STEP 0.0166666667')
    inp.write_text(text,encoding='utf-8')
    case=json.loads((tmp_path/'case.json').read_text(encoding='utf-8'));case['model_sha256']=sources.digest(inp.read_bytes())
    (tmp_path/'case.json').write_text(json.dumps(case),encoding='utf-8')
    with pytest.raises(ValueError,match='REPORT_STEP'):suite.validate_case(tmp_path)


@pytest.mark.parametrize('key',['REPORT_STEP','WET_STEP','DRY_STEP'])
def test_preflight_rejects_ambiguous_numeric_clock_matching_declared_seconds(tmp_path,key):
    from suites.uk_2d.build import COLLECTION
    import shutil,re
    source=COLLECTION/'uk-ea-2013-t01'
    for name in ['case.json','model.inp','probes.csv']:shutil.copy2(source/name,tmp_path/name)
    inp=tmp_path/'model.inp';text=inp.read_text(encoding='utf-8')
    for field in ['REPORT_STEP','WET_STEP','DRY_STEP']:
        text=re.sub(r'^'+field+r'\s+.*$',field+' 0:00:00.1',text,flags=re.M)
    text=text.replace(key+' 0:00:00.1',key+' 0.1');inp.write_text(text, encoding='utf-8')
    case=json.loads((tmp_path/'case.json').read_text(encoding='utf-8'));case['step']=.1;case['model_sha256']=sources.digest(inp.read_bytes())
    (tmp_path/'case.json').write_text(json.dumps(case), encoding='utf-8')
    with pytest.raises(ValueError,match=key):suite.validate_case(tmp_path)


def test_partial_coverage_stays_visible_in_dashboard_and_badge():
    from harness.site import _coverage_note
    env=dict(suite='uk_2d',coverage=dict(requested=10,executed=7,observed_compared=1,regression_checked=2),cells=[])
    assert '7/10' in _coverage_note(env)
    badge=scoring.badges([env])['uk-2d-coverage']
    assert '7/10' in badge['message'] and badge['color']!='brightgreen'


def test_report_uses_packaged_specifications_without_local_plans(tmp_path,monkeypatch):
    from suites.uk_2d import figures
    monkeypatch.setattr(figures,'ROOT',tmp_path,raising=False)
    (tmp_path/'scores.json').write_text(json.dumps(dict(coverage={},cells=[])),encoding='utf-8')
    figures.build_report(tmp_path)
    rows=list(csv.DictReader((tmp_path/'report-output-register.csv').open(encoding='utf-8')))
    assert len(rows)==61 and not (tmp_path/'plans').exists()


@pytest.mark.parametrize('write_fresh_output',[False,True])
def test_analytical_rejects_stale_files_and_wrong_time_axis(tmp_path,monkeypatch,write_fresh_output):
    import h5py
    from suites.uk_2d import analytical
    exe=tmp_path/'engine';exe.write_bytes(b'test fixture')
    def output(work,stage,shift=0):
        _,_,reference=analytical.deck(stage)
        with h5py.File(work/'surface.h5','w') as f:
            f['time']=np.arange(1,61)+shift;f['time'].attrs['units']='seconds since 2026-01-01 00:00:00'
            f['Mesh2_face_depth']=np.tile(reference,(60,1))
            for field in ['vx','vy']:f['Mesh2_face_'+field]=np.zeros((60,400))
            f.create_group('mass_balance_2d').attrs['continuity_error']=0.
    for name,stage in [('immersed',1.),('emerged',.3)]:
        work=tmp_path/('analytic-lake-at-rest-'+name);work.mkdir();output(work,stage)
    def run_engine(exe,inp,rpt,out,**kwargs):
        rpt.write_text('MOMENTUM_EQUATION FULL_SWE\n2D solver: cpu\n',encoding='utf-8')
        if write_fresh_output:output(inp.parent,1. if 'immersed' in inp.parent.name else .3,shift=100)
        return dict(ok=True,stdout='',stderr='',wall=.01)
    monkeypatch.setattr(analytical.runner,'run',run_engine)
    env=analytical.run(exe,tmp_path,120)
    assert scoring.exit_code(env)==1 and all(c['verdict']=='ERROR' for c in env['cells'])
    if write_fresh_output:assert all('Misaligned' in c['note'] for c in env['cells'])
    else:assert not any(tmp_path.glob('*/surface.h5'))
