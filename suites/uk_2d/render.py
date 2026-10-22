"""Small escaped Markdown renderer for portable generated evidence reports."""
import html
import re


def inline(text):
    text=html.escape(text)
    text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',text)
    text=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',text)
    text=re.sub(r'`([^`]+)`',r'<code>\1</code>',text)
    return text


def render(markdown):
    lines=markdown.splitlines();result=[];i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        heading=re.match(r'^(#{1,6}) (.*)',line)
        if heading:
            n=len(heading[1]);result.append(f'<h{n}>{inline(heading[2])}</h{n}>');i+=1;continue
        image=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',line)
        if image:
            alt=html.escape(image[1],quote=True);url=html.escape(image[2],quote=True)
            result.append(f'<figure><img src="{url}" alt="{alt}" loading="lazy"><figcaption>{alt}</figcaption></figure>');i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                rows.append([x.strip() for x in lines[i].strip().strip('|').split('|')]);i+=1
            result.append('<div class="table"><table><thead><tr>'+''.join('<th>'+inline(x)+'</th>' for x in rows[0])+'</tr></thead><tbody>')
            for row in rows[2:]:result.append('<tr>'+''.join('<td>'+inline(x)+'</td>' for x in row)+'</tr>')
            result.append('</tbody></table></div>');continue
        paragraph=[]
        while i<len(lines) and lines[i].strip() and not lines[i].lstrip().startswith(('#','|','![')):
            paragraph.append(lines[i].strip());i+=1
        result.append('<p>'+inline(' '.join(paragraph))+'</p>')
    css='''body{font:17px/1.65 system-ui,sans-serif;color:#183b4b;background:#fff;max-width:1100px;margin:3rem auto;padding:0 1.4rem}h1,h2,h3{line-height:1.2;color:#103c48}h1{font-size:2.3rem;border-bottom:5px solid #16867b;padding-bottom:1rem}h2{margin-top:3rem}a{color:#007b82}figure{margin:2rem 0}img{max-width:100%;height:auto}figcaption{font-size:.9rem;color:#5c6f76}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{padding:.65rem;border-bottom:1px solid #d9e5e9;text-align:left;vertical-align:top}th{background:#edf5f5}code{background:#edf3f5;padding:.1rem .3rem}strong{color:#7b4019}@media print{body{font-size:11pt}figure,table{break-inside:avoid}}'''
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>UK 2D benchmark evidence</title><style>'+css+'</style></head><body><main>'+''.join(result)+'</main></body></html>'
