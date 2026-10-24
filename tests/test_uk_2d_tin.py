"""Constrained Test 6 geometry, physical scaling and wall adjacency contracts."""
import json
import numpy as np
import pytest
from types import SimpleNamespace
from suites.uk_2d.build import COLLECTION
from suites.uk_2d.tin import audit,areas,geometry


def deck(key):
    vertices=[];cells=[];walls=set();depths=[];section=''
    for line in (COLLECTION/('uk-ea-2013-t'+key)/'model.inp').read_text(encoding='utf-8').splitlines():
        if line.startswith('['):section=line;continue
        if not line.strip() or line.startswith(';'):continue
        values=line.split()
        if section=='[2D_VERTICES]':vertices.append(list(map(float,values)))
        if section=='[2D_TRIANGLES]':cells.append(list(map(int,values[:3])));depths.append(float(values[4]))
        if section=='[2D_QUADS]':raise AssertionError('Test 6 must not use Cartesian quads')
        if section=='[2D_BOUNDARY_CONDITIONS]':
            assert values[2]=='WALL'
            walls.add((int(values[0]),int(values[1])))
    return np.array(vertices),np.array(cells),np.array(depths),walls


@pytest.mark.parametrize('key,scale',[('6a',1),('6b',20)])
def test_test6_exact_geometry_open_gate_and_explicit_walls(key,scale):
    vertices,cells,depths,walls=deck(key)
    provenance=json.loads((COLLECTION/('uk-ea-2013-t'+key)/'mesh-provenance.json').read_text(encoding='utf-8'))
    zscale=1 if provenance.get('vertical_interpretation')=='dem' else scale
    normalised=vertices/scale;normalised[:,2]=vertices[:,2]/zscale
    review,expected_walls=audit(normalised,cells,geometry())
    assert walls=={(ci,edge) for ci,edge,_ in expected_walls}
    assert review['area_m2']==pytest.approx(354.,abs=1e-7)
    assert review['min_angle_deg']>=28
    assert review['triangle_count']==61642
    assert vertices[:,2].max()==pytest.approx(.155*zscale)
    assert set(depths)=={.4*scale,.02*scale}
    assert np.dot(areas(vertices,cells),depths)==pytest.approx(16.618*scale**3,rel=1e-9)
    assert not provenance['stats']['refine_capped']


def test_test6_scale_does_not_change_connectivity_or_depth_assignment():
    a,ca,ha,wa=deck('6a');b,cb,hb,wb=deck('6b')
    assert np.array_equal(ca,cb) and wa==wb
    p=json.loads((COLLECTION/'uk-ea-2013-t6b/mesh-provenance.json').read_text(encoding='utf-8'))
    expected=a.copy();expected[:,:2]*=20
    if p.get('vertical_interpretation')!='dem':expected[:,2]*=20
    np.testing.assert_allclose(b,expected,atol=1e-8,rtol=1e-10)
    np.testing.assert_allclose(hb,20*ha,atol=1e-12,rtol=0)


def test_test6_audit_rejects_flattened_banks_and_inverted_cells():
    v,c,_,_=deck('6a');v[:,2]=0
    with pytest.raises(ValueError,match='Bed differs'):audit(v,c,geometry())
    v,c,_,_=deck('6a');c[0]=c[0,::-1]
    with pytest.raises(ValueError,match='Nonpositive'):audit(v,c,geometry())


def test_superseded_cartesian_anchors_cannot_be_confused_with_current_models():
    for key in ['6a','6b']:
        case=COLLECTION/('uk-ea-2013-t'+key)
        old=json.loads((case/'baselines/cartesian-2026-10-22/baseline.json').read_text(encoding='utf-8'))
        current=json.loads((case/'case.json').read_text(encoding='utf-8'))
        assert old['model_sha256']!=current['model_sha256']
        assert (case/'baselines/cartesian-2026-10-22/superseded.json').exists()


def test_test6b_source_conflict_cannot_be_resolved_silently(monkeypatch,tmp_path):
    from suites.uk_2d import build
    monkeypatch.setattr(build,'Raster',lambda data:None)
    sources=SimpleNamespace(read=lambda *args:b'')
    with pytest.raises(ValueError,match='select --test6b-elevations explicitly'):
        build.build_case('6b',sources,tmp_path)
