# 강: OSM(Geofabrik 2026-11-24 추출본)에서 water=river 면과 waterway=river 선만 뽑음. 호수·저수지는 생긴 해를 정리하기 전이라 뺌
import os as _os, sys as _sys  # paths.py 찾기: 이 파일 폴더에서 위로 올라감(저장소 src/, 작업 공간 $MLM_SUDO·$MLM_SUDO2)
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and not _os.path.isfile(_os.path.join(_d, 'paths.py')):
    _d = _os.path.dirname(_d)
_sys.path.insert(1, _d)
from paths import PAGE_DATA, RAW, SUDO2  # noqa: E402
import json, sys
from shapely.geometry import shape, box, mapping, MultiPolygon, LineString, MultiLineString
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, linemerge
sys.path.insert(0,SUDO2)
from build2_util import rnd
FR=box(124.7,36.1,129.3,39.1)
CORE=box(125.9,36.75,128.1,38.45)
polys=[]; lines={}
for ln in open(f'{RAW}/osm/w.geojsonseq'):
    ln=ln.strip('\x1e\n ')
    if not ln: continue
    f=json.loads(ln); p=f['properties']; g=f['geometry']
    if g['type'] in ('Polygon','MultiPolygon') and (p.get('water') in ('river','canal') or p.get('waterway')=='riverbank'):
        s=shape(g).buffer(0)
        if s.intersects(FR): polys.append(s.intersection(FR))
    elif g['type']=='LineString' and p.get('waterway')=='river':
        s=shape(g)
        if s.intersects(FR):
            nm=(p.get('name:ko') or p.get('name') or '').split('/')[-1]
            lines.setdefault(nm,[]).append(s.intersection(FR))
import shapely
W=unary_union(polys).buffer(0.00015).buffer(-0.00015).simplify(0.0003,preserve_topology=True)
W=shapely.set_precision(W,0.0001).buffer(0)
ps=[W] if W.geom_type=='Polygon' else list(W.geoms)
CORE=box(125.9,36.75,128.1,38.45)
ps=[orient(p,-1.0) for p in ps if p.area>(3e-7 if p.intersects(CORE) else 6e-6)]
W=MultiPolygon(ps)
# 반올림 뒤 고리 방향 검사(d3는 시계 방향 바깥 고리만 받음)
def sa(r):
    return sum(x0*y1-x1*y0 for (x0,y0),(x1,y1) in zip(r,r[1:]))
bad=0
for p in W.geoms:
    ext=rnd(list(p.exterior.coords))
    if sa(ext)>=0: bad+=1
print('ccw after round',bad)
L=[]
for nm,gs in lines.items():
    parts=[]
    for g in gs:
        parts+= [g] if g.geom_type=='LineString' else [x for x in getattr(g,'geoms',[]) if x.geom_type=='LineString']
    m=linemerge(parts)
    ms=[m] if m.geom_type=='LineString' else list(m.geoms)
    for x in ms:
        x=x.simplify(0.0004)
        core=x.intersects(CORE)
        if x.length<((0.004 if nm else 0.03) if core else (0.05 if nm else 1e9)): continue
        if not core: x=x.simplify(0.001)
        L.append({'n':nm,'p':rnd(list(x.coords))})
d=json.load(open(PAGE_DATA))
m=mapping(W); d['water']={'type':m['type'],'coordinates':rnd(m['coordinates'])}; d['rivers']=L
json.dump(d,open(PAGE_DATA,'w'),ensure_ascii=False,separators=(',',':'))
print(len(ps), len(json.dumps(d['water'])), len(L), len(json.dumps(L)))
