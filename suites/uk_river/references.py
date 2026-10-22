"""Import published numbers, never competitor simulation curves."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
CORPUS=ROOT/'corpus/uk-ea-river'
SPEC='W5-105-TR1-Test-Specifications.pdf'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def write_csv(path,header,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    # Explicit LF: the recorded hash must survive cross-platform regeneration.
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream,lineterminator='\n');writer.writerow(header);writer.writerows(rows)


class Sources:
    def __init__(self,root):
        self.root=Path(root)
        self.records={r['path']:r for r in json.loads((HERE/'sources.json').read_text(encoding='utf-8'))['files']}
        self.used={}

    def read(self,name):
        data=(self.root/name).read_bytes();record=self.records[name]
        if len(data)!=record['bytes'] or digest(data)!=record['sha256']:
            raise ValueError('Altered or unrecognized source: '+name)
        self.used[name]=record['sha256']
        return data


def table_rows(reader,pages,widths):
    for page in pages:
        for line in reader.pages[page-1].extract_text().splitlines():
            if not re.match(r'^\d+\.\d+\s',line):continue
            fields=line.split()
            if len(fields) not in widths:raise ValueError(f'Unexpected table width on page {page}')
            yield [float(v) for v in fields]


def laboratory_table(reader):
    rows=[]
    for row in table_rows(reader,[89,90,91,92],{5,10}):
        rows.extend([row[i:i+5] for i in range(0,len(row),5)])
    rows=np.array(sorted(rows,key=lambda r:r[0]))
    if rows.shape!=(251,5) or not np.allclose(rows[:,0],np.arange(251)*.04,rtol=0,atol=1e-10):
        raise ValueError('Incomplete or duplicate laboratory time grid')
    if not np.isfinite(rows).all() or np.any(rows[:,1:]<0):raise ValueError('Invalid laboratory values')
    if not np.array_equal(rows[0],[0,.3,.003,.003,.003]):raise ValueError('Laboratory initial values disagree')
    return rows


def bed_profile(data):
    """Read only the authored rectangular geometry, not model predictions."""
    rows=[]
    for block in data.decode('cp1252').split('Type RM Length L Ch R =')[1:]:
        head=block.splitlines()[0].split(',');chainage=float(head[1])
        match=re.search(r'#Sta/Elev=\s*4\s*\n([^\n]+)',block)
        if match is None:raise ValueError('Expected four-point source cross section')
        points=[float(v) for v in match[1].split()]
        if len(points)!=8 or points[3]!=points[5] or points[4]-points[2]!=10:
            raise ValueError('Unexpected rectangular channel geometry')
        rows.append([chainage,points[3]])
    rows=np.array(sorted(rows))
    if rows.shape!=(101,2) or not np.array_equal(rows[:,0],np.arange(101)):
        raise ValueError('Incomplete source bed profile')
    return rows


def manifest(destination,kind,source,pages,description,**extra):
    path=destination/'reference.csv'
    write_json(destination/'reference.json',dict(kind=kind,source=source,pdf_pages_1based=pages,
        citation='Environment Agency W5-105/TR1 (2004) or the named W5-105/TR2 results report',
        csv_sha256=digest(path.read_bytes()),description=description,rights='Source rights not independently verified',
        instrument_uncertainty='Not reported' if kind=='observed' else 'Not applicable',**extra))


def import_all(source_root):
    import io
    from pypdf import PdfReader
    src=Sources(source_root);reader=PdfReader(io.BytesIO(src.read(SPEC)))
    profiles=np.array(list(table_rows(reader,[77,78],{6})))
    profiles=profiles[np.argsort(profiles[:,0])]
    if profiles.shape!=(101,6) or not np.array_equal(profiles[:,0],np.arange(101)):
        raise ValueError('Incomplete Test A analytical table')
    for part in range(1,6):
        dest=CORPUS/f'uk-river-a{part}'/'reference'
        name=f'Test A/hec-ras/Part {part}/Test A-P{part}.g01'
        bed=bed_profile(src.read(name))
        if np.any(profiles[:,part]<=bed[:,1]):raise ValueError('Analytical surface below bed')
        write_csv(dest/'reference.csv',['chainage_m','bed_m','level_m'],zip(bed[:,0],bed[:,1],profiles[:,part]))
        manifest(dest,'analytic',SPEC,[77,78],'Published analytical water elevations, not competitor output. Source chainage decreases in the flow direction.',
                 rounding_m=.00005,rounding_note='Conservative half unit of the coarsest displayed four-decimal entry; 503 of 505 elevations display five decimals.',
                 source_hashes=dict(src.used),geometry_source=name)
    lab=laboratory_table(reader);dest=CORPUS/'uk-river-l'/'reference'
    write_csv(dest/'reference.csv',['time_s','S1','S2','S3','S4'],lab)
    manifest(dest,'observed',SPEC,[89,90,91,92],'Tabulated CADAM laboratory water levels above the flat bed; 251 times at 0.04 s, including t=0 and t=10.',
             rounding_m=.0005,time_origin='Physical gate release; no fitted time shift',source_hashes={SPEC:src.used[SPEC]})
    jname='Test_J_SCHO0305BIXX-E-E_pdf.sflb.pdf';jr=PdfReader(io.BytesIO(src.read(jname)))
    # Verify the directly transcribed measured row and flow header against text.
    text=jr.pages[19].extract_text()
    for line in ['Measured 0.035 0.070 0.032 0.062','0.02097 0.03443 0.02098 0.03429']:
        if line not in text:raise ValueError('Test J source table changed')
    dest=CORPUS/'uk-river-j'/'reference'
    write_csv(dest/'reference.csv',['bridge','flow_m3s','afflux_m'],[
        ['arch',.02097,.035],['arch',.03443,.070],['flat_soffit',.02098,.032],['flat_soffit',.03429,.062]])
    manifest(dest,'observed',jname,[20],'Measured Table 4.1 row only. Afflux is the upstream bridge/no-bridge depth difference at the same flow.',
             rounding_m=.0005,source_hashes={jname:src.used[jname]})
    fname='Test F/isis/n=0.0241/Monoclinial5KHT.dat'
    text=src.read(fname).decode('cp1252').split('INITIAL CONDITIONS')[1]
    initial=[]
    for line in text.splitlines():
        if re.match(r'^S\d+\s+y',line):
            f=line.split();initial.append([(int(f[0][1:])-1)*5000,float(f[2]),float(f[3])-float(f[-1])])
    initial=np.array(initial)
    if initial.shape!=(201,3) or not np.allclose(initial[[0,-1],2],[8,3]):raise ValueError('Invalid monoclinal initial profile')
    dest=CORPUS/'uk-river-f'/'reference'
    write_csv(dest/'reference.csv',['distance_from_upstream_m','discharge_m3s','depth_m'],initial)
    manifest(dest,'analytic',fname,[],'Source-declared analytical initial state (TR2F section 2.3), translated at the independently specified wave celerity. Linear interpolation of tabulated values, not a new closed-form calculation.',
             wave_celerity_mps=(24693.395-5698.697)/5000,rounding_depth_m=.0005,
             source_hashes={fname:src.used[fname]},friction='Analytical wave uses constant Chezy C=55; model uses the report\'s constant Manning n approximations.')
    # E's source scenario is executable, but its exact published reference is not qualified.
    ename='Test_E_SCHO0305BIXT-E-E_pdf.sflb.pdf';src.read(ename)
    write_json(CORPUS/'uk-river-e'/'reference'/'reference.json',dict(kind='unavailable',source=ename,
        source_hashes={ename:src.used[ename]},reason='TR2E section 4.3 identifies a sine/cosine boundary phase conflict. Appendix A also leaves the representative velocity for linear friction unspecified. No parameter fitting or phase shift is applied to manufacture agreement.'))
    write_json(HERE/'coverage.json',dict(collection='Environment Agency W5-105 river benchmarks',solver='SWMM2D CPU FULL_SWE',
        cases={**{f'a{i}':'Executable source-derived quasi-steady reproduction' for i in range(1,6)},
        'e':'Executable full scenario; published analytical reference qualification pending',
        'f':'Executable report Manning variants; translated analytical initial-profile reference',
        'l':'Executable physical laboratory geometry; original measured table recovered',
        'j':'Measured targets imported; bridge and paired no-bridge geometry implementation pending'},
        not_in_scope='A6 transient has no independent analytical history; numbered SC120002 2D tests remain a separate suite.'))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source-root',type=Path,required=True)
    import_all(ap.parse_args().source_root)
