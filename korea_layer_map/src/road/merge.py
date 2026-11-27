import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW as _RAW, D as _D, W as _W  # 경로는 src/paths.py 한곳에서 정한다
import json,csv,math,collections
d=json.load(open(_W("road","osm_mw2.json")))
mz={int(r["순번"]):r for r in csv.DictReader(open(_D("road","민자고속도로_개통일_20261127.csv"),encoding="utf-8-sig"))}
OP={'신공항하이웨이(주)':1,'천안논산고속도로(주)':2,'新대구부산고속도로주식회사':3,'서울고속도로주식회사':(4,5),'부산울산고속도로(주)':6,
'경수고속도로 주식회사':7,'서울춘천고속도로':8,'서울춘천고속도로(주)':8,'인천대교(주)':9,'경기고속도로(주)':10,'제2서해안고속도로':11,
'수도권서부고속도로(주)':12,'제2영동고속도로':13,'부산신항제2배후도로':14,'인천김포고속도로(주)':15,'상주영천고속도로(주)':16,
'서울북부고속도로':17,'제이경인연결고속도로(주)':18,'옥산오창고속도로':19,'서울문산고속도로(주)':20,'경기동서순환도로(주)':21,
'화성광주고속도로(주)':22,'포천화도고속도로(주)':23,'포천화도고속도로주식회사':23,'서부내륙고속도로(주)':24}
feats=[]; notes=collections.Counter(); L=collections.Counter()
def flen(cs):
    return sum(math.hypot((x2-x1)*111320*math.cos(math.radians(y1)),(y2-y1)*110574) for (x1,y1),(x2,y2) in zip(cs,cs[1:]))/1000
for w in d["ways"]:
    op=w["op"]; od=w["od"]
    if w["name"]=="평택화성고속도로": key=10; note="OSM 운영자 태그(한국도로공사)를 경기고속도로로 고쳐 읽음"
    elif op in ("한국도로공사",""): continue
    elif w["ref"]=="55" and "대구부산" in op and max(y for x,y in w["coords"])<35.2785: continue  # 재정 파일에 중앙 대동~삼락으로 들어감
    else: key=OP[op]; note=""
    if key==(4,5): key=5 if od=="2007-12-28" else 4
    r=mz[key]; csvd=r["개통일"]
    if len(csvd)==10:
        if od and od>csvd: date=od; note=(note+"; " if note else "")+f"OSM 날짜를 씀(이어진 구간이 {od}에 열림)"
        else:
            date=csvd
            if od and od!=csvd: note=(note+"; " if note else "")+f"OSM 날짜 {od} 대신 보도 날짜"
        chk=r["확인 정도"]
    else:
        date=od or ""; chk="OSM 날짜(달만 운영평가와 맞음)" if od else "날짜 없음"
    notes[note]+=1
    cs=[[round(x,5),round(y,5)] for x,y in w["coords"]]; L[key]+=flen(cs)
    feats.append({"type":"Feature","properties":dict(ref=w["ref"],name=w["name"],osm_way=w["id"],owner="민자",operator=r["운영 법인"],
        geom_date=date,route_date=date,row=f"민자 {key}",geom_kind="신설",section=r["구간"],check=chk,fill="",note=note),
        "geometry":{"type":"LineString","coordinates":cs}})
print("민자 피처",len(feats)); print(notes.most_common())
for k in sorted(L): print(k,mz[k]["운영 법인"][:14],round(L[k]/2,1),"km(한쪽) 보도",mz[k]["보도 연장(km)"])
g=json.load(open(_W("road","재정고속도로_선형_20261127.geojson")))
out=[]
for f in g["features"]:
    p=f["properties"]
    q=dict(ref=p["ref"],name=p["name"],osm_way=p["osm_way"],owner="재정",operator="한국도로공사",geom_date=p["geom_date"],route_date=p["route_date"],
        row=f"재정 {p['geom_row']}" if p["geom_row"] else "",route_row=f"재정 {p['route_row']}" if p["route_row"] else "",
        geom_kind=p["geom_kind"],section=p["geom_section"],check=p["check"],fill=p["fill"],note=p["note"])
    out.append({"type":"Feature","properties":q,"geometry":f["geometry"]})
for f in feats: f["properties"]["route_row"]=f["properties"]["row"]
allf=out+feats
json.dump({"type":"FeatureCollection","features":allf},open(_W("road","전국고속도로_선형_20261127.geojson"),"w"),ensure_ascii=False,separators=(",",":"))
# 연말마다 길이(양방향 합/2)
yr=collections.defaultdict(float)
for f in allf:
    dte=f["properties"]["route_date"]
    if dte: yr[int(dte[:4])]+=flen(f["geometry"]["coordinates"])/2
acc=0; cum={}
for y in range(1968,2027): acc+=yr.get(y,0); cum[y]=acc
print({y:round(cum[y]) for y in (1970,1980,1990,2000,2010,2020,2022,2026)})
json.dump(cum,open(_W("road","cum_len.json"),"w"))
