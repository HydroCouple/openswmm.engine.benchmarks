"""Check the sealed website bundle and links without reading live solver files."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import hashlib,importlib.util,json
R=Path(__file__).resolve().parents[3];O=R/'results/uk_2d/g2-reconstruction-2026-10-25';S=R.parent/'hydrocouple.github.io';A=S/'articles/uk-2d-benchmark-assessment';D=A/'evidence/g2-reconstruction'
assert (D/'publication-manifest.json').read_bytes()==(O/'publication-manifest.json').read_bytes(), 'Published bundle is not the latest sealed source'
spec=importlib.util.spec_from_file_location('reconstruction_publication',A/'reconstruction.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);p=m.validate(D)
class Links(HTMLParser):
 def __init__(self):super().__init__();self.paths=[]
 def handle_starttag(self,tag,attrs):
  for k,v in attrs:
   if k in ['href','src'] and v:self.paths.append(v)
def check(page,only_audit=False):
 parser=Links();parser.feed(page.read_text(encoding='utf-8'));checked=0
 for value in parser.paths:
  u=urlsplit(value)
  if u.scheme or not u.path:continue
  if only_audit and 'g2-reconstruction' not in u.path:continue
  target=S/u.path.lstrip('/') if u.path.startswith('/') else page.parent/unquote(u.path)
  assert target.is_file(),(page,value,target);checked+=1
 return checked
report_links=check(D/'report.html');preview_links=check(A/'preview.html',True);index_links=check(S/'articles.html',True)
protected=R/'corpus/uk-ea-2d/uk-ea-2013-t6a/model.inp';assert hashlib.sha256(protected.read_bytes()).hexdigest()=='d40e3cb0b2c3123764bf6b54a4f10c53b2e388fff702890fe32eed07b948bd10'
provenance=json.loads((D/'report-provenance.json').read_text(encoding='utf-8'));assert hashlib.sha256((D/'report.html').read_bytes()).hexdigest()==provenance['report_sha256']
result=dict(status='PASS',sealed_artifacts=len(p['files']),technical_report_local_links=report_links,preview_new_report_links=preview_links,article_new_report_links=index_links,reviewed_scientific_figures=len(provenance['figures']),protected_working_input_unchanged=True,cases=p['cases'],qualification='Six figures visually inspected; sealed identities and local links verified. Corrected coarse run completes120s, gradient-only/refined controls30s. G2 remains unresolved; no canonical promotion.')
(O/'publication-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
