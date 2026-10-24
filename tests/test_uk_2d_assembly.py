"""A mesh correction must retain dated identities and discard stale case plots."""
import json
import pytest
from suites.uk_2d.assemble import merged


def cohort(root,identities,complete=True):
    root.mkdir()
    cells=[]
    for ident,label in identities.items():
        case=root/ident;(case/'figures').mkdir(parents=True)
        (case/'figures'/('plot-'+label+'.png')).write_bytes(b'fixture')
        (case/'run-manifest.json').write_text(json.dumps(dict(created=label,model_sha256=label)), encoding='utf-8')
        cells.append(dict(case=ident,solver='swmm2d-cpu-full-swe-rk2',verdict='PASS',checks={'volume':True},observed_status='not_applicable',regression_status='unavailable'))
    (root/'scores.json').write_text(json.dumps(dict(engine_sha='same-engine',cells=cells,
        coverage=dict(complete=complete,requested=len(cells),executed=len(cells)))), encoding='utf-8')


def test_replacement_keeps_unchanged_identity_and_archives_old_mesh(tmp_path):
    old,new,out=[tmp_path/n for n in ['old','new','assembled']]
    cohort(old,{'a':'old-a','b':'old-b'});cohort(new,{'b':'new-b'})
    merged(old,new,out,['b'])
    history=json.loads((out/'assessment-history.json').read_text(encoding='utf-8'))
    assert history['case_sources']['a']['executed']=='old-a'
    assert history['case_sources']['b']['executed']=='new-b'
    assert (out/'history/cartesian-b/figures/plot-old-b.png').exists()
    assert not (out/'b/figures/plot-old-b.png').exists()
    assert (out/'b/figures/plot-new-b.png').exists()
    assert (out/'history/original-scores.json').read_bytes()==(old/'scores.json').read_bytes()


def test_incomplete_replacement_cannot_publish_or_copy_partial_evidence(tmp_path):
    old,new,out=[tmp_path/n for n in ['old','new','assembled']]
    cohort(old,{'a':'old-a'});cohort(new,{'a':'new-a'},False)
    with pytest.raises(ValueError,match='expected completed'):merged(old,new,out,['a'])
    assert not out.exists()
