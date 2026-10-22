"""Conservative recovery of isolated UCL diamond markers; no curve digitization."""
from __future__ import annotations
import argparse
import csv
import io
import json
from pathlib import Path
import numpy as np
from PIL import Image
from .sources import INVENTORY,digest
from .build import COLLECTION

# Verified directly against the six original embedded chart images (1201x900).
# Bounds are original image pixels; x=0/60 s and y=0/top tick.
CHARTS=[(79,0,'G2','level_m',.18),(79,1,'G4','level_m',.16),
        (80,0,'G5','level_m',.14),(80,1,'G6','level_m',.42),
        (81,0,'G2','speed_mps',2.5),(81,1,'G4','speed_mps',2.)]
AXES=dict(x0=156.,x60=1087.,y0=802.,ytop=68.)


def markers(rgb):
    """Exact 5x5 diamond support; overlapped/ambiguous markers are omitted."""
    if rgb.shape!=(900,1201,3):raise ValueError('Unexpected source image dimensions')
    mask=(rgb[:,:,0]>220)&(rgb[:,:,1]<80)&(rgb[:,:,2]>220)
    template=np.fromfunction(lambda y,x:abs(y-2)+abs(x-2)<=2,(5,5)).astype(bool)
    exact=np.ones((896,1197),bool)
    for y in range(5):
        for x in range(5):exact &= mask[y:y+896,x:x+1197]==template[y,x]
    yy,xx=np.where(exact);xx+=2;yy+=2
    keep=(xx>158)&(xx<1085)&(yy>70)&(yy<800)
    keep &= ~((xx>=712)&(xx<=1078)&(yy>=76)&(yy<=550))
    return np.column_stack([xx[keep],yy[keep]])


def recover(pdf,destination):
    from pypdf import PdfReader
    raw=Path(pdf).read_bytes();locked=json.loads(INVENTORY.read_text(encoding='utf-8'))
    record=next(x for x in locked['files'] if x['path']=='_SC120002_Benchmarking_2D_hydraulic_models_Report.pdf')
    if digest(raw)!=record['sha256']:raise ValueError('Unrecognized source report')
    reader=PdfReader(io.BytesIO(raw));dest=Path(destination);dest.mkdir(parents=True,exist_ok=True)
    output=[];audit=[]
    for page,index,probe,quantity,top in CHARTS:
        image=reader.pages[page-1].images[index].image.convert('RGB');rgb=np.asarray(image)
        points=markers(rgb);grouped={}
        for x,y in points:grouped.setdefault(int(x),[]).append(float(y))
        for x,ys in sorted(grouped.items()):
            values=[(AXES['y0']-y)/(AXES['y0']-AXES['ytop'])*top for y in ys]
            output.append(dict(time_s=(x-AXES['x0'])/(AXES['x60']-AXES['x0'])*60,probe=probe,quantity=quantity,
                               value=float(np.mean(values)),value_min=min(values),value_max=max(values),isolated_marker_count=len(ys)))
        audit.append(dict(pdf_page_1based=page,image_index=index,probe=probe,quantity=quantity,top=top,
                          embedded_pixels_sha256=digest(rgb.tobytes()),isolated_markers=len(points),binned_samples=len(grouped),
                          one_pixel_value=top/734,one_pixel_time_s=60/931,
                          marker_pixels=points.tolist()))
    csvpath=dest/'observations.csv'
    with csvpath.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=['time_s','probe','quantity','value','value_min','value_max','isolated_marker_count'])
        writer.writeheader();writer.writerows(output)
    manifest=dict(kind='digitized_observed',source='UCL measurement diamonds only, EA SC120002/R Figures 4.25 and 4.26',
                  citation='Neelz and Pender (2013), SC120002/R, Figures 4.25-4.26; underlying IMPACT/UCL experiment cited therein',
                  source_pdf_sha256=record['sha256'],quantity_definitions={'level_m':'Water surface elevation in metres above the flat flume bed','speed_mps':'Scalar velocity magnitude in metres per second as labelled in Figure 4.26'},
                  datum='Flat flume bed = 0 m, per UK specification',time_origin='Gate release, chart elapsed-time origin',
                  csv_sha256=digest(csvpath.read_bytes()),max_gap_s=1.0,license='unverified',
                  uncertainty={'instrument':'unknown; not inferred from digitization','digitization':'Conservative +/-1 pixel per axis; per-series physical conversion in digitization-audit.json',
                               'time_binning':'Markers in the same x-pixel column are averaged; min/max and counts retained'},
                  coverage='Visible isolated markers only; primarily first 30 s. G6 unrecoverable. Original raw observations remain unavailable.',
                  selection_limitations='Occluded/overlapping markers are omitted. This is a visibility-selected subset and does not estimate fit to the complete experiment.',
                  extraction='Exact magenta 5x5 radius-2 Manhattan diamond template, with non-diamond surroundings, inside plot axes; source legend excluded. No continuous model curve is sampled.',
                  peer_review_status='Algorithm and visual recovery audit only; independent second-person digitization pending')
    (dest/'observations.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (dest/'digitization-audit.json').write_text(json.dumps(dict(axes_pixels=AXES,legend_exclusion=[712,76,1078,550],charts=audit),indent=2)+'\n',encoding='utf-8')
    return manifest,audit

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pdf',type=Path,required=True);ap.add_argument('--destination',type=Path,default=COLLECTION/'uk-ea-2013-t6a/reference')
    args=ap.parse_args();manifest,audit=recover(args.pdf,args.destination)
    for row in audit:print(row['probe'],row['quantity'],row['isolated_markers'],'markers',row['binned_samples'],'samples')
