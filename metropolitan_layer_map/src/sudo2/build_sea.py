import json, pyarrow.parquet as pq, shapely, shapely.wkb
from shapely.geometry import shape, box, mapping, MultiPolygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, polylabel
FR=box(123.8,35.6,130.0,39.6)
t=pq.read_table('/home/claude/ext/vuski_admdongkor/parquet/simplified/sido_20261001_light.parquet').to_pylist()
parts=[]; labs=[]
for r in t:
    if any(k in r['sidonm'] for k in ('서울','인천','경기')): continue
    g=shapely.wkb.loads(r['geometry']).buffer(0).intersection(FR)
    if g.is_empty: continue
    parts.append(g)
    lg=g if g.geom_type=='Polygon' else max(g.geoms,key=lambda p:p.area)
    if lg.area>0.02: 
        p=polylabel(lg,0.005); labs.append([r['sidonm'].replace('특별자치도','').replace('충청남도','충남').replace('충청북도','충북'),round(p.x,3),round(p.y,3)])
# 휴전선 아래 내륙 띠(비무장지대 남쪽·1963년 철원→연천 편입 지역 등): 시대 경계가 비는 곳을 땅으로 채움. 북쪽 내륙에는 매립지가 없음
IN=box(126.62,37.72,127.9,38.4)
for r in t:
    if any(k in r['sidonm'] for k in ('서울','인천','경기')):
        g=shapely.wkb.loads(r['geometry']).buffer(0).intersection(IN)
        if not g.is_empty: parts.append(g)
ne=json.load(open('/home/claude/raw/ne/ne_10m_admin_0_countries.geojson'))
prk=[f for f in ne['features'] if f['properties'].get('ADM0_A3')=='PRK'][0]
pg=shape(prk['geometry']).buffer(0.012).intersection(FR)
parts.append(pg)
lg=pg if pg.geom_type=='Polygon' else max(pg.geoms,key=lambda p:p.area)
labs.append(['북한(지금 경계)',126.55,38.45])
# 자연지구 북한 선과 지금 경기 경계 사이의 가는 틈을 닫음(강 하구가 없는 위도 37.85 이북 내륙만)
CL=box(126.62,37.85,127.9,38.4)
u=unary_union(parts)
gapfill=u.intersection(CL).buffer(0.025).buffer(-0.025).intersection(CL)
land=unary_union([u,gapfill]).simplify(0.002,preserve_topology=True)
def og(g):
    if g.geom_type=='Polygon': g=orient(g,-1.0)
    else: g=MultiPolygon([orient(p,-1.0) for p in g.geoms if p.area>1e-6])
    m=mapping(g)
    def rnd(o):
        if isinstance(o,(list,tuple)):
            if o and isinstance(o[0],(int,float)): return [round(o[0],4),round(o[1],4)]
            return [rnd(x) for x in o]
        return o
    return {'type':m['type'],'coordinates':rnd(m['coordinates'])}
d=json.load(open('/home/claude/sudo/page/data.json'))
d['nb']=og(land); d['nbLabels']=labs
json.dump(d,open('/home/claude/sudo/page/data.json','w'),ensure_ascii=False,separators=(',',':'))
print(labs, len(json.dumps(d['nb'])))
