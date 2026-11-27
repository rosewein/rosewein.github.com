# 시화 간석지: 1994년 1월 시화방조제 물막이 뒤 드러난 간석지가 SGIS 행정경계에 들어 있지 않아 바다로 보이던 문제를 메움
# 범위 = 반월특수지역 세 구역(택지정보 지구경계) − OSM 수면(시화호·탄도호·수로 등 natural=water). OSM에서 이 범위 안에 해안선이 없음을 확인함
import json, sys, shapely
from shapely.geometry import shape, mapping, MultiPolygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
sys.path.insert(0,'/home/claude/sudo2'); from build2_util import rnd
P='/home/claude/sudo/page/data.json'
d=json.load(open(P))
R=unary_union([shape(o['geo']).buffer(0) for o in d['jigu'] if o['c'] in ('41390MX2010001','41390MX2010005','41390KW2017001')])
W=[];coast=[]
for ln in open('/home/claude/raw/osm/sh.geojsonseq'):
    ln=ln.strip('\x1e\n ')
    if not ln: continue
    f=json.loads(ln); p=f['properties']
    if p.get('natural')=='coastline': coast.append(shape(f['geometry'])); continue
    if f['geometry']['type'] in ('Polygon','MultiPolygon') and p.get('natural')=='water' and p.get('water') not in ('pond','wastewater','basin'):
        W.append(shape(f['geometry']).buffer(0))
T=R.difference(unary_union(W)).buffer(0.0003).buffer(-0.0003)
print('coastline crossing region (km):', round(unary_union(coast).intersection(T).length*100,2))
# 해안선 바깥(바다 쪽) 조각을 뺌: OSM 해안선은 진행 방향 왼쪽이 육지
from shapely.ops import polygonize, unary_union as UU, nearest_points
from shapely.geometry import Point
CL=[c for c in coast if c.intersects(T.buffer(0.01))]
faces=list(polygonize(UU([T.boundary]+[c.intersection(T.buffer(0.001)) for c in CL])))
keep=[]
def is_land(pt):
    best=None
    for c in CL:
        dd=c.distance(pt)
        if best is None or dd<best[0]: best=(dd,c)
    c=best[1]; t=c.project(pt); a=c.interpolate(max(t-1e-5,0)); b=c.interpolate(min(t+1e-5,c.length))
    return (b.x-a.x)*(pt.y-a.y)-(b.y-a.y)*(pt.x-a.x)>0
for f in faces:
    if not f.within(T.buffer(1e-6)): continue
    if is_land(f.representative_point()): keep.append(f)
print('faces',len(faces),'land faces',len(keep))
T=UU(keep).buffer(0.0002).buffer(-0.0002)
T=shapely.set_precision(T.simplify(0.0002,preserve_topology=True),0.0001).buffer(0)
ps=[T] if T.geom_type=='Polygon' else list(T.geoms)
ps=[orient(p,-1.0) for p in ps if p.area>5e-6]
m=mapping(MultiPolygon(ps))
d['tidal']={'y0':1994,'geo':{'type':'MultiPolygon','coordinates':rnd(m['coordinates'])}}
json.dump(d,open(P,'w'),ensure_ascii=False,separators=(',',':'))
k=111.32*0.794*110.57
print(len(ps), round(sum(p.area for p in ps)*k,1),'km2')
