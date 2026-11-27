"""광역버스 경로용 방향 도로 그래프(OSM busrd.geojsonseq) → busgraph.npz"""
import os as _os, sys as _sys  # paths.py 찾기: 이 파일 폴더에서 위로 올라감(저장소 src/, 작업 공간 $MLM_SUDO·$MLM_SUDO2)
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and not _os.path.isfile(_os.path.join(_d, 'paths.py')):
    _d = _os.path.dirname(_d)
_sys.path.insert(1, _d)
from paths import RAW, SUDO2  # noqa: E402
import json, numpy as np, math
COST = {'motorway':0.6,'motorway_link':0.8,'trunk':0.75,'trunk_link':0.85,'primary':0.9,'primary_link':0.95,
        'secondary':1.0,'secondary_link':1.0,'tertiary':1.1,'tertiary_link':1.1,'unclassified':1.3,
        'residential':1.6,'living_street':2.0,'busway':0.8}
CLS = {k:i for i,k in enumerate(COST)}
idx = {}; xs=[]; ys=[]
U=[];V=[];D=[];C=[]
def nid(c):
    k=(round(c[0]*1e7),round(c[1]*1e7))
    i=idx.get(k)
    if i is None:
        i=len(xs); idx[k]=i; xs.append(c[0]); ys.append(c[1])
    return i
for ln in open(f'{RAW}/osm/busrd.geojsonseq'):
    ln=ln.strip().lstrip('\x1e')
    if not ln: continue
    f=json.loads(ln); p=f['properties']; hw=p.get('highway')
    if hw not in COST: continue
    if p.get('access') in ('no','private') and p.get('bus') not in ('yes','designated') and p.get('psv') not in ('yes','designated'): continue
    ow=p.get('oneway')
    if ow in ('yes','true','1'): dirn=1
    elif ow=='-1': dirn=-1
    elif ow=='no': dirn=0
    elif hw in ('motorway','motorway_link') or p.get('junction') in ('roundabout','circular'): dirn=1
    else: dirn=0
    cs=f['geometry']['coordinates']; ids=[nid(c) for c in cs]
    for a,b,ca,cb in zip(ids,ids[1:],cs,cs[1:]):
        if a==b: continue
        d=math.hypot((cb[0]-ca[0])*88.4,(cb[1]-ca[1])*111.0)
        if dirn>=0: U.append(a);V.append(b);D.append(d);C.append(CLS[hw])
        if dirn<=0: U.append(b);V.append(a);D.append(d);C.append(CLS[hw])
np.savez_compressed(f'{SUDO2}/bus/busgraph.npz',x=np.array(xs),y=np.array(ys),u=np.array(U,np.int32),v=np.array(V,np.int32),d=np.array(D,np.float32),c=np.array(C,np.int8),cost=np.array(list(COST.values()),np.float32),names=np.array(list(COST)))
print(len(xs),'nodes',len(U),'directed edges')
