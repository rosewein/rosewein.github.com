# 신도시·택지: 택지정보시스템(국토교통부·LX) 지구경계 SHP(EPSG:5186) + 지구정보·지구단계정보 CSV, 2026-10 고시월(2026-11-26 생성)
import json, sys, shapefile, pandas as pd, shapely
from shapely.geometry import shape, mapping, MultiPolygon, Point
from shapely.geometry.polygon import orient
from shapely.ops import transform, unary_union
from pyproj import Transformer
sys.path.insert(0,'/home/claude/sudo2'); from build2_util import rnd
J='/home/claude/raw/jigu/'
I=pd.read_csv(J+'지구정보_전국_20261126/BLS5_DSTRC_INFO.csv',encoding='cp949',dtype=str).set_index('지구지정번호')
M=pd.read_csv(J+'지구단계정보_전국_20261126/BLS5_DSTRC_MASTER.csv',encoding='cp949',dtype=str).set_index('지구지정번호')
P=pd.read_csv(J+'부분준공정보_전국_20261126/BLS5_DSTRC_PART.csv',encoding='cp949',dtype=str)
pfirst=P.groupby('지구지정번호')['부분준공일자'].min().to_dict()
tr=Transformer.from_crs(5186,4326,always_xy=True).transform
r=shapefile.Reader(J+'지구경계_전국_20261126_5186/the_geom',encoding='cp949')
d=json.load(open('/home/claude/sudo/page/data.json'))
ST=d['stations']
def D(s):
    s=(s or '').strip() if isinstance(s,str) else ''
    return f'{s[:4]}-{s[4:6]}-{s[6:8]}' if len(s)>=8 and s[:8].isdigit() else None
TODAY='2026-11-26'
out=[]; skipped=[]
for sr,rec in zip(r.shapes(),r.records()):
    code=rec[0]
    if code not in I.index: continue
    a=I.loc[code]
    if str(a['위치코드'])[:2] not in ('11','28','41'): continue
    ar=float(a['면적']) if isinstance(a['면적'],str) else float(str(rec[3]).replace(',','') or 0)
    if ar<100000: continue
    m=M.loc[code] if code in M.index else None
    d0=None; d0k=None
    for k in ('지구지정일자','개발계획승인일자','실시계획승인일자','사업시행시작일자'):
        v=D(a[k])
        if v: d0,d0k=v,k; break
    if not d0: skipped.append(a['지구명']); continue
    d1=D(a['준공일자'])
    if d1 and d1>TODAY: d1=None
    g=transform(tr,shape(sr.__geo_interface__)).buffer(0)
    g=g.simplify(0.00012,preserve_topology=True)
    g=shapely.set_precision(g,0.0001).buffer(0)
    ps=[g] if g.geom_type=='Polygon' else [p for p in getattr(g,'geoms',[]) if p.geom_type=='Polygon']
    ps=[orient(p,-1.0) for p in ps if p.area>1e-8]
    if not ps: continue
    G=MultiPolygon(ps)
    # 지구 안이나 둘레 500m 안 전철역 가운데 가장 먼저 연 역
    zone=G.buffer(0.0055)
    best=None
    for s in ST:
        if not zone.contains(Point(s['x'],s['y'])): continue
        for l,y,dt,*_ in s['ls']:
            if not y: continue
            key=dt or f'{y}'
            if best is None or key<best[2]: best=(s['n'].split('#')[0],l,key)
    num=lambda v: (int(float(v)) if isinstance(v,str) and v.strip() else None)
    out.append({'c':code,'n':a['지구명'].strip(),'k':a['택지구분코드명'],'law':(m['법령코드명1'] if m is not None and isinstance(m['법령코드명1'],str) else ''),
        'step':(m['단계코드명'] if m is not None and isinstance(m['단계코드명'],str) else ''),
        'd0':d0,'d0k':d0k.replace('일자',''),'d1':d1,'pc':D(pfirst.get(code)),'ar':round(ar/1e6,2),'pop':num(a['계획인구수']),'ho':num(a['건설호수']),
        'loc':a['위치명'] if isinstance(a['위치명'],str) else '','st':best,
        'geo':{'type':'MultiPolygon','coordinates':rnd(mapping(G)['coordinates'])}})
# 반월특수지역 하위 사업: 택지정보의 지구지정일(1977-04-22)은 반월특수지역(안산신도시) 지정일이라, 사업별 지정·고시일로 바꾸고 단계별 준공을 덧붙임
OVR={
 '41390MX2010001':dict(d0='1986-09-27',d0k='시화지구 지정(건설부 고시 제424호)',
   note='택지정보시스템에는 지구 지정일이 1977-04-22(반월특수지역 첫 지정일)로, 사업시행기간이 1977~2035년, 준공 예정일이 2035-12-31로 적혀 있어 전체 준공일은 없다. 시화호와 남·북측 간석지는 1998년 11월 확대지정으로 들어왔다. 경계는 지금 모양이다.',
   ph=[['시화1단계(정왕동 시화신도시·시화국가산업단지)','주거단지 1992~2002년, 산업단지 1993~2004년 차수별 준공. 사업 전체 준공은 2010년 12월(한국수자원공사)과 2020년 12월(시흥시)로 두 기관 누리집이 엇갈림'],
       ['시화MTV','2014년 12월 1차 지역부터 2025년 12월 10차 지역까지 차례로 준공(따로 그림)'],
       ['송산그린시티','2019년 1월 1차 지역 준공(따로 그림)']]),
 '41390KW2017001':dict(d0='2001-08-29',d0k='개발계획 고시(건교부 고시 제2001-222호)',pc='2014-12',
   note='택지정보시스템의 지구 지정일 1977-04-22는 반월특수지역 첫 지정일이다. 이 땅(시화호 북측 간석지)은 1998년 11월 반월특수지역에 들어왔다. 사업기간 2002~2027년.',
   ph=[['차수별 준공(한국수자원공사)','1차 2014.12(토취장), 2차 2015.10(2.03㎢), 3차 2016.12(2.81㎢), 4차 2017.11(1.42㎢), 5차 2018.12(0.09㎢), 6차 2020.06(0.14㎢), 7차 2020.09(0.34㎢), 8차 2021.09(0.03㎢), 9차 2022.03(0.36㎢), 10차 2025.12(0.68㎢)']]),
 '41390MX2010005':dict(d0='2008-03',d0k='개발계획 고시(국토부 고시 제2008-4호, 날짜는 달까지만 확인)',pc='2019-01',
   note='택지정보시스템의 지구 지정일 1977-04-22는 반월특수지역 첫 지정일이다. 이 땅(시화호 남측 간석지)은 1998년 11월 반월특수지역에 들어왔다. 준공 예정 2035-12-31(택지정보시스템).',
   ph=[['차수별 준공(한국수자원공사)','1차 지역 2019.01(1.44㎢)']]),
}
for o in out:
    if o['c'] in OVR: o.update(OVR[o['c']])
out.sort(key=lambda o:-o['ar'])
d['jigu']=out
d['src']['jigu']=['택지정보시스템 자료제공(국토교통부·한국국토정보공사), 2026-10 고시월','https://openapi.jigu.go.kr/main.do']
json.dump(d,open('/home/claude/sudo/page/data.json','w'),ensure_ascii=False,separators=(',',':'))
print(len(out),'skipped',skipped[:10],len(json.dumps(out)))
import collections
print(collections.Counter(o['d0'][:3] for o in out))
print([ (o['n'],o['d0'],o['d1'],o['st']) for o in out[:12]])
