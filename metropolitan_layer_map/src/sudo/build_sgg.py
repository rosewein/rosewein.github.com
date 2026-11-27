import os as _os, sys as _sys  # paths.py 찾기: 이 파일 폴더에서 위로 올라감(저장소 src/, 작업 공간 $MLM_SUDO·$MLM_SUDO2)
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and not _os.path.isfile(_os.path.join(_d, 'paths.py')):
    _d = _os.path.dirname(_d)
_sys.path.insert(1, _d)
from paths import EXT  # noqa: E402
import json, shapely
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
sel=open(f'{EXT}/sel.txt').read().split()
def grp(s): return '서울' if '서울' in s else '인천' if '인천' in s else '경기'
snaps=[]
for d in sel:
    fc=json.load(open(f'gj/y{d}.json'))
    snaps.append([(grp(f['properties']['s']),f['properties']['n'],f['properties']['s'],shape(f['geometry']).buffer(0)) for f in fc['features']])
vers=[]   # dict key,name,sido,geom,fr,to
last={}
diffs=[]
for i,feats in enumerate(snaps):
    for g,n,s,geom in feats:
        k=(g,n)
        v=last.get(k)
        if v is not None and v['to']==i-1:
            sd=v['geom'].symmetric_difference(geom).area/max(v['geom'].area,geom.area)
            diffs.append(sd)
            if sd<0.01 and v['sido']==s:
                v['to']=i; continue
        v={'k':k,'n':n,'sido':s,'geom':geom,'fr':i,'to':i,'sd':(sd if v is not None and v['to']==i-1 else None)}
        vers.append(v); last[k]=v
import statistics
print('versions',len(vers),'snap feats',sum(len(s) for s in snaps))
diffs.sort(); print('diff quantiles', [round(diffs[int(q*(len(diffs)-1))],4) for q in (0.5,0.9,0.95,0.98,0.99,1)])
for v in vers:
    if v['fr']>0: print(sel[v['fr']], v['k'], v['sido'], 'sd=',v['sd'] if v['sd'] is None else round(v['sd'],3))
json.dump(None,open('/dev/null','w'))
import pickle; pickle.dump((sel,vers,snaps),open('vers.pkl','wb'))
