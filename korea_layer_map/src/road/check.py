import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW as _RAW, D as _D, W as _W  # 경로는 src/paths.py 한곳에서 정한다
import json,collections,math,csv
ED=["2008-11-05","2009-12-16","2010-12-31","2011-12-07","2012-11-20","2013-11-28","2014-11-17","2015-12-31","2016-12-23","2017-12-21","2018-12-21","2019-09-20","2020-11-30","2021-12-09","2022-07-08","2023-12-18","2024-11-29","2025-12-30","2026-11-11"]
wf={w["id"]:w for w in json.load(open(_W("road","way_first.json")))}
gj=json.load(open(_W("road","재정고속도로_선형_20261127.geojson")))
rows={int(r["순번"]):r for r in csv.DictReader(open(_D("road","재정고속도로_구간표_20261127.csv"),encoding="utf-8-sig"))}
def flen(cs):
    s=0
    for (x1,y1),(x2,y2) in zip(cs,cs[1:]):
        s+=math.hypot((x2-x1)*111320*math.cos(math.radians(y1)),(y2-y1)*110574)
    return s/1000
def exp_idx(d):
    for i,e in enumerate(ED):
        if e>=d: return i
    return None
agg=collections.defaultdict(lambda:collections.Counter())
for f in gj["features"]:
    p=f["properties"]
    if not p["geom_row"]: continue
    w=wf.get(p["osm_way"]); L=flen(f["geometry"]["coordinates"])
    if not w or not w["first"]: agg[p["geom_row"]]["판에 없음"]+=L; continue
    fi=ED.index(w["first"]); ei=exp_idx(p["geom_date"])
    if ei is None: agg[p["geom_row"]]["판보다 늦은 개통"]+=L; continue
    if p["geom_date"]<ED[0]: k="맞음" if fi==0 else f"늦게 실림 +{fi}"
    else:
        dfi=fi-ei
        k="맞음" if dfi==0 else (f"늦게 실림 +{dfi}" if dfi>0 else f"먼저 실림 {dfi}")
    agg[p["geom_row"]][k]+=L
bad=[]
for i in sorted(agg):
    c=agg[i]; T=sum(c.values()); ok=c["맞음"]
    if ok/T<0.8:
        r=rows[i]; bad.append(i)
        print(f"{i:3} {r['개통일']} {r['노선(지금 이름)']} {r['구간']} ({r['성격']}) 합 {T:.1f}km: "+", ".join(f"{k} {v:.1f}" for k,v in c.most_common()))
tot=collections.Counter()
for c in agg.values(): tot.update(c)
T=sum(tot.values()); print(f"전체 {T:.0f}km: "+", ".join(f"{k} {v:.0f}" for k,v in tot.most_common()))
