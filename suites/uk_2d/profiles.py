"""Read the source profile geometry, and sample only within containing cells."""
from __future__ import annotations
import csv
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
import numpy as np
from .sources import digest


def read_profile(data):
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        rows=ET.fromstring(book.read('xl/worksheets/sheet1.xml')).findall('.//s:row',ns)
        result=[]
        for row in rows[1:]:
            vals={c.attrib['r'].rstrip('0123456789'):c.find('s:v',ns) for c in row}
            if not all(k in vals and vals[k] is not None for k in ['B','C','D']):continue
            result.append([float(vals[k].text) for k in ['B','C','D']])
    result=np.asarray(result)
    if not np.isfinite(result).all() or np.any(np.diff(result[:,0])<=0):raise ValueError('Invalid profile chainage')
    return result


def import_profiles(archive,inventory,destination):
    records={r['path']:r for r in json.loads(Path(inventory).read_text(encoding='utf-8'))['files']}
    with zipfile.ZipFile(archive) as outer:
        nested='XS info Tests_5&6.zip';data=outer.read(nested)
        key='Benchmarking_Model_Data.zip!/'+nested
        if digest(data)!=records[key]['sha256']:raise ValueError('Altered profile archive')
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                raw=z.read(name);key2=key+'!/'+name
                if digest(raw)!=records[key2]['sha256']:raise ValueError('Altered profile workbook')
                values=read_profile(raw)
                case='uk-ea-2013-t05' if 'Test5' in name else 'uk-ea-2013-t6b'
                if not (Path(destination)/case/'model.inp').exists():continue
                target=Path(destination)/case/'profiles';target.mkdir(parents=True,exist_ok=True)
                base=Path(name).stem
                with (target/(base+'.csv')).open('w',newline='', encoding='utf-8') as stream:
                    w=csv.writer(stream);w.writerow(['chainage_m','x','y']);w.writerows(values)
                (target/(base+'.json')).write_text(json.dumps(dict(source=key2,sha256=digest(raw),role='profile geometry only; no model results'),indent=2)+'\n', encoding='utf-8')


def sample(values,fields):
    verts=fields['vertices'];cells=fields['cells'];polys=[verts[c[c>=0]] for c in cells]
    lo=np.array([p.min(axis=0) for p in polys]);hi=np.array([p.max(axis=0) for p in polys])
    result=[]
    for s,x,y in values:
        candidates=np.flatnonzero((lo[:,0]-1e-8<=x)&(hi[:,0]+1e-8>=x)&(lo[:,1]-1e-8<=y)&(hi[:,1]+1e-8>=y))
        found=None
        for c in candidates:
            p=polys[c];b=np.roll(p,-1,axis=0);cross=(b[:,0]-p[:,0])*(y-p[:,1])-(b[:,1]-p[:,1])*(x-p[:,0])
            if np.all(cross>=-1e-8) or np.all(cross<=1e-8):found=c;break
        result.append([s,x,y,np.nan if found is None else fields['z'][found]+fields['max_depth'][found],
                       np.nan if found is None else fields['max_speed'][found],np.nan if found is None else fields['z'][found]])
    return np.asarray(result)
