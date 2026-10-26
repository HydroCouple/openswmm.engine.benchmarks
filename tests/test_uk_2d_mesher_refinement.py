"""Optional native checks for the GUI-backed benchmark mesh adapter."""
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import pytest


@pytest.fixture
def mesher():
    path=os.environ.get('UK_GUI_MESHER')
    if not path:pytest.skip('Set UK_GUI_MESHER to the built GUI adapter')
    assert Path(path).is_file()
    return path


def request():
    return dict(domain=[[-2,-1],[2,-1],[2,1],[-2,1]],constraints=[],holes=[],
                max_area=.1,min_cell_size=.025)


def run(mesher,tmp_path,name,value):
    source=tmp_path/(name+'.json');target=tmp_path/(name+'-mesh.json')
    source.write_text(json.dumps(value))
    result=subprocess.run([mesher,str(source),str(target)],capture_output=True,text=True,timeout=120)
    return result,target


def test_no_local_size_callback_retains_identical_mesh(mesher,tmp_path):
    original=request();empty=dict(original,refinement_boxes=[])
    first,a=run(mesher,tmp_path,'original',original);second,b=run(mesher,tmp_path,'empty',empty)
    assert first.returncode==second.returncode==0
    assert json.loads(a.read_text())==json.loads(b.read_text())


def test_graded_refinement_reduces_local_cells_and_preserves_domain(mesher,tmp_path):
    value=request();value['refinement_boxes']=[dict(xmin=-.5,xmax=.5,ymin=-.5,ymax=.5,max_area=.01,transition_width=.3)]
    result,path=run(mesher,tmp_path,'graded',value);assert result.returncode==0,result.stderr
    mesh=json.loads(path.read_text());vertices=np.array(mesh['vertices']);cells=np.array(mesh['triangles'])
    p=vertices[cells];area=.5*np.sum(p[:,:,0]*np.roll(p[:,:,1],-1,axis=1)-p[:,:,1]*np.roll(p[:,:,0],-1,axis=1),axis=1)
    centre=p.mean(1);inner=(abs(centre[:,0])<.4)&(abs(centre[:,1])<.4);outer=abs(centre[:,0])>1.2
    assert (area>0).all() and area.sum()==pytest.approx(8,abs=1e-10)
    assert np.median(area[inner])<.4*np.median(area[outer])
    assert not mesh['stats']['refine_capped']


@pytest.mark.parametrize('changed',[{'transition_width':0},{'max_area':-.1},{'max_area':.2},
                                    {'xmin':.8,'xmax':.5},{'ymin':.8,'ymax':.5},{'xmin':'invalid'}])
def test_invalid_refinement_is_rejected_before_meshing(mesher,tmp_path,changed):
    value=request();box=dict(xmin=-.5,xmax=.5,ymin=-.5,ymax=.5,max_area=.01,transition_width=.3)
    box.update(changed);value['refinement_boxes']=[box]
    result,target=run(mesher,tmp_path,'invalid',value)
    assert result.returncode==2 and not target.exists()
