"""철도 역 자리 대응 시안 페이지의 데이터(site/data.json, site/base.json)를 만든다.

python3 src/rail/site/build_data.py
입력: work/rail/station_match.json, work/rail/osm_rail_s.json·osm_rail_n.json
- base.json: OSM 선로(지금 선과 폐선·운휴 선). 차량기지·측선·건넘선, 공사·계획 선은 뺐다.
  shapely로 약 30m 허용 오차로 줄이고, 좌표는 1e4배 정수의 차분으로 담는다.
- data.json: 대응한 역 자리(점)와 구간 사건(점을 곧게 이은 선, 아직 OSM 선로를 따르지 않음).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
from paths import W
import json, re
from shapely.geometry import LineString

HERE = _os.path.dirname(_os.path.abspath(__file__))
R = json.load(open(W("rail", "station_match.json")))

# ---------- 바탕 선로 ----------
LIVE = {"rail", "narrow_gauge", "subway", "light_rail", "monorail", "funicular", "preserved"}
HISTR = {"abandoned", "disused", "razed"}
HK = ("abandoned:railway", "disused:railway", "razed:railway", "historic:railway", "was:railway", "railway:historic")
lines = {"live": [], "hist": []}
seen = set()
for f in "sn":
    for w in json.load(open(W("rail", f"osm_rail_{f}.json")))["ways"]:
        if w["id"] in seen or len(w["coords"]) < 2:
            continue
        seen.add(w["id"])
        if w.get("service") in ("yard", "siding", "crossover"):
            continue
        hist = w["railway"] in HISTR or any(w.get(k) for k in HK)
        if not hist and w["railway"] not in LIVE:
            continue
        g = LineString(w["coords"]).simplify(0.0003)
        q = [(round(x * 1e4), round(y * 1e4)) for x, y in g.coords]
        flat = [q[0][0], q[0][1]]
        for (a, b), (c, d) in zip(q, q[1:]):
            if (c, d) != (a, b):
                flat += [c - a, d - b]
        if len(flat) >= 4:
            lines["hist" if hist else "live"].append(flat)
json.dump(lines, open(_os.path.join(HERE, "base.json"), "w"), separators=(",", ":"))

# ---------- 역 자리와 구간 ----------
def cat(how):
    if "손 자리" in how or "추정" in how:
        return "est"
    if how in ("그대로", "다른 쪽 pbf · 그대로"):
        return "osm"
    return "ren"


RANK = {"osm": 0, "ren": 1, "est": 2}
OPEN = {"개통", "복원", "운행 재개"}
CLOSE = {"폐지", "운행 중단", "여객 중지", "영업 중지"}
pts, segs, specials = {}, [], []
for o in R:
    if o.get("특수"):
        specials.append(dict(t=o["표"], n=o["순번"], d=o["날짜"], e=o["사건"], l=o["노선"], s=o["구간"]))
        continue
    for sg in o["segs"]:
        ids = []
        for p in sg["pts"]:
            pi = p.get("pick_info")
            if not pi:
                continue
            pid = pi["id"] if not pi["id"].startswith("m") else "m" + pi["name"] + f"{pi['lat']:.4f}"
            c = cat(p["how"])
            x = pts.setdefault(pid, dict(id=pid, nm=pi["name"], lat=pi["lat"], lon=pi["lon"], c=c, k=pi["kind"],
                                         reg=pi["reg"], u=[]))
            if RANK[c] > RANK[x["c"]]:
                x["c"] = c
            x["u"].append(dict(r=o["표"][0] + o["순번"], d=o["날짜"], e=o["사건"], s=o["구간"], q=p["nm"],
                               h=p["how"], why=p.get("note", "")))
            ids.append(pid)
        if len(ids) < 2:
            continue
        ev = o["사건"]
        if sg["role"] == "전":
            kind = "close"
        elif sg["role"] == "후" or ev in OPEN or ev.startswith("이설"):
            kind = "open"
        elif ev in CLOSE:
            kind = "close"
        else:
            kind = "work"
        segs.append(dict(id=len(segs), t=o["표"], r=o["표"][0] + o["순번"], d=o["날짜"], e=ev, l=o["노선"],
                         s=o["구간"], g=o["지역"], k=kind, p=ids, km=o["연장"]))

# 닫힘 붙이기: 같은 노선의 닫힘 구간이 열린 구간의 양 끝을 모두 품으면 그날 닫는다(시안용 간단 규칙)
for s in segs:
    if s["k"] != "open":
        continue
    ends = {s["p"][0], s["p"][-1]}
    for c in segs:
        if c["k"] == "close" and c["d"] > s["d"] and (c["l"] == s["l"]) and ends <= set(c["p"]):
            if "x" not in s or c["d"] < s["x"]:
                s["x"] = c["d"]
    if s["g"] == "북" and "x" not in s:
        s["x"] = "1945-08-15"   # 북쪽은 1945년까지만(자료 범위)

for x in pts.values():
    x["lat"], x["lon"] = round(x["lat"], 5), round(x["lon"], 5)
    x["u"].sort(key=lambda u: u["d"])
data = dict(pts=sorted(pts.values(), key=lambda x: x["nm"]), segs=segs, specials=specials,
            made="2026-11-27", note="station_match.py 결과(1단계). 선은 역 자리를 곧게 이은 것")
json.dump(data, open(_os.path.join(HERE, "data.json"), "w"), ensure_ascii=False, separators=(",", ":"))
import collections
print(len(lines["live"]), len(lines["hist"]), sum(len(l) for l in lines["live"] + lines["hist"]) // 2, "꼭짓점")
print(len(pts), "역 자리", collections.Counter(x["c"] for x in pts.values()))
print(len(segs), "구간", collections.Counter(s["k"] for s in segs), sum(1 for s in segs if "x" in s), "닫힘 붙음")
print({f: _os.path.getsize(_os.path.join(HERE, f)) for f in ("base.json", "data.json")})
