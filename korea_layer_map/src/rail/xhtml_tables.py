import sys, re
from lxml import etree
doc = etree.parse(sys.argv[1], etree.HTMLParser())
for ti, t in enumerate(doc.iter('table')):
    print(f'### table {ti}')
    for tr in t.iter('tr'):
        cells = []
        for td in tr:
            if td.tag not in ('td','th'): continue
            txt = ' '.join(''.join(td.itertext()).split())
            rs, cs = td.get('rowspan'), td.get('colspan')
            tag = ''
            if rs and rs!='1': tag += f'[r{rs}]'
            if cs and cs!='1': tag += f'[c{cs}]'
            cells.append(tag+txt)
        print(' | '.join(cells))
