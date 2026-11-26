import json, re, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom
from paths import CODE, DATA, RAW, WORK
B = DATA
ST = json.load(open(f"{RAW}/subway/stations_seoul.json"))
DATES = json.load(open(f"{B}/metro_dates.json")) if os.path.exists(f"{B}/metro_dates.json") else {}
EXTRA = json.load(open(f"{B}/metro_extra.json")) if os.path.exists(f"{B}/metro_extra.json") else {"stations": [], "lines": []}

COLORS = {"1호선":"#0052A4","2호선":"#00A84D","3호선":"#EF7C1C","4호선":"#00A5DE","5호선":"#996CAC","6호선":"#CD7C2F",
"7호선":"#747F00","8호선":"#E6186C","9호선":"#BDB092","경의중앙선":"#77C4A3","경춘선":"#0C8E72","공항철도":"#0090D2",
"수인분당선":"#F5A200","신분당선":"#D4003B","우이신설선":"#B0CE18","신림선":"#6789CA","서해선":"#8FC31F","GTX-A":"#9A6292"}

def num(code):
    m = re.match(r"^([A-Z]*)(\d+)(?:-(\d+))?$", code)
    return (m.group(1), int(m.group(2)), int(m.group(3) or 0)) if m else (code, 0, 0)

by = {}
for s in ST:
    ln = "GTX-A" if s["line"] == "GTXA" else s["line"]
    by.setdefault(ln, {})[s["fr_code"]] = s
for st in EXTRA.get("stations", []):
    by.setdefault(st["line"], {})[st["fr_code"]] = st

def seq(ln, codes):
    return [by[ln][c] for c in codes if c in by[ln]]

def sorted_codes(ln, pred=lambda c: True):
    return sorted([c for c in by.get(ln, {}) if pred(c)], key=num)

SEQS = {}
SEQS["1호선"] = [seq("1호선", sorted_codes("1호선", lambda c: not c.startswith("P"))),
               seq("1호선", ["141", "P142", "P143", "P144", "P145", "P146"]), seq("1호선", ["P144", "P144-1"])]
SEQS["2호선"] = [seq("2호선", sorted_codes("2호선", lambda c: "-" not in c) + ["201"]),
               seq("2호선", ["211", "211-1", "211-2", "211-3", "211-4"]), seq("2호선", ["234", "234-1", "234-2", "234-3", "234-4"])]
for ln in ["3호선", "4호선", "7호선", "9호선", "서해선", "수인분당선", "우이신설선", "신림선", "공항철도"]:
    SEQS[ln] = [seq(ln, sorted_codes(ln))]
SEQS["신분당선"] = [seq("신분당선", sorted(by["신분당선"], key=lambda c: int(c[1:])))]
SEQS["5호선"] = [seq("5호선", sorted_codes("5호선", lambda c: not c.startswith("P"))),
               seq("5호선", ["548"] + sorted_codes("5호선", lambda c: c.startswith("P")))]
SEQS["6호선"] = [seq("6호선", ["610", "611", "612", "613", "614", "615", "610"]), seq("6호선", ["610"] + [c for c in sorted_codes("6호선") if num(c)[1] >= 616])]
SEQS["8호선"] = [seq("8호선", sorted_codes("8호선", lambda c: c.startswith("B"))[::-1] + sorted_codes("8호선", lambda c: not c.startswith("B")))]
SEQS["경의중앙선"] = [seq("경의중앙선", [c for c in sorted_codes("경의중앙선") if c.startswith("K1")]),
                  seq("경의중앙선", ["K110", "K826"] + [c for c in sorted_codes("경의중앙선") if c.startswith("K3")]),
                  seq("경의중앙선", ["P313", "P312", "K315"])]
SEQS["경춘선"] = [seq("경춘선", ["P117", "P118", "P119", "P120", "P121", "P122", "P123", "P124"]), seq("경춘선", ["P116", "P120"])]
if "GTX-A" in by:
    SEQS["GTX-A"] = [seq("GTX-A", sorted_codes("GTX-A", lambda c: c.startswith("G"))), seq("GTX-A", sorted_codes("GTX-A", lambda c: c.startswith("X")))]

def dist(a, b):
    return math.hypot((a["lng"] - b["lng"]) * 88.4, (a["lat"] - b["lat"]) * 111.0)

# merge stations across lines
stations = []
def sid(s):
    for i, t in enumerate(stations):
        if t["name"] == s["name"] and dist(t, s) < 0.45:
            if t.pop("_nodot", False):   # 먼저 만든 노선이 점 자리를 넘긴 역(metro_extra의 "nodot")
                t["lat"], t["lng"] = s["lat"], s["lng"]
            return i
    stations.append({"name": s["name"], "lat": s["lat"], "lng": s["lng"], "opens": {}, "dates": {}})
    if s.get("nodot"): stations[-1]["_nodot"] = True
    return len(stations) - 1

def year(d):
    return int(d[:4])

missing = []
nostraight = []
lines = []
for ln, seqs in SEQS.items():
    D = DATES.get(ln, {})
    edges = []
    for sq in seqs:
        ids, dts, inf = [], [], []
        for s in sq:
            rec = D.get(s["name"])
            if not rec or not rec.get("open"):
                missing.append(f"{ln}/{s['name']}"); ids.append(None); dts.append(None); inf.append(False); continue
            i = sid(s)
            stations[i]["opens"][ln] = year(rec["open"]); stations[i]["dates"][ln] = rec["open"].replace("-", ".")
            if rec.get("note"): stations[i].setdefault("notes", []).append(f'{ln}: {rec["note"]}')
            ids.append(i); dts.append(year(rec["open"])); inf.append(bool(rec.get("infill")))
        # edges: infill stations inherit the link date of their nearest non-infill neighbours
        def anchor(k, step):
            j = k
            while 0 <= j < len(ids) and (ids[j] is None or inf[j]):
                j += step
            return dts[j] if 0 <= j < len(ids) else None
        for k in range(len(ids) - 1):
            if ids[k] is None or ids[k + 1] is None or ids[k] == ids[k + 1]:
                continue
            a = dts[k] if not inf[k] else anchor(k, -1)
            b = dts[k + 1] if not inf[k + 1] else anchor(k + 1, 1)
            cand = [x for x in (a, b) if x is not None]
            e = {"a": ids[k], "b": ids[k + 1], "open": max(cand) if cand else max(dts[k], dts[k + 1])}
            A, Bq = [sq[k]["lng"], sq[k]["lat"]], [sq[k + 1]["lng"], sq[k + 1]["lat"]]
            gp = geom.find_snap([ln], sq[k]["name"], sq[k + 1]["name"], A, Bq)
            if gp:
                e["p"], e["_ends"] = gp, (A, Bq)   # 역 점까지 잇는 선은 아래 「역 점 잇기」에서
            else: nostraight.append(f"{ln}:{sq[k]['name']}-{sq[k+1]['name']}")
            edges.append(e)
    lines.append({"name": ln, "color": COLORS.get(ln, "#888"), "edges": edges})
# 역 점 잇기: 선은 OSM 선로를 따라가고(geom.find_snap), 그 노선의 역 좌표가 지도에 찍히는 역 점일 때만
# 선로 위 자리에서 역 점까지 짧은 선을 잇는다. 환승역에서 점이 다른 노선 자리에 있으면 잇지 않는다(승강장이 따로 있음).
STUB = []
for L in lines:
    for e in L["edges"]:
        ends = e.pop("_ends", None)
        if not ends: continue
        p = e["p"]
        for side, idx, X in ((0, e["a"], ends[0]), (-1, e["b"], ends[1])):
            st = stations[idx]
            if [st["lng"], st["lat"]] != X: continue
            gap = geom._m(p[side], X)
            if gap <= 3: p[side] = X
            elif side == 0: p.insert(0, X)
            else: p.append(X)
            if gap > 40: STUB.append(f"{L['name']}:{st['name']} {gap:.0f}m")
        e["p"] = geom.rnd(p)
print("역 점까지 이은 선(40m 넘는 것):", sorted(set(STUB)), file=sys.stderr)
for st in stations:
    st.pop("_nodot", None)
for st in stations:
    st["first"] = min(st["opens"].values())
    if st.get("notes"): st["note"] = " / ".join(st.pop("notes"))
print("straight (no OSM path):", nostraight, file=sys.stderr)
print("missing dates:", len(missing), missing[:60], file=sys.stderr)

# events: group by line+date
events = []
for ln, seqs in SEQS.items():
    D = DATES.get(ln, {})
    groups = {}
    order = {}
    for sq in seqs:
        for k, s in enumerate(sq):
            rec = D.get(s["name"])
            if not rec or not rec.get("open"): continue
            key = (rec["open"], bool(rec.get("infill")))
            if s["name"] not in groups.setdefault(key, []): groups[key].append(s["name"])
    for (d, infill), names in sorted(groups.items()):
        if infill:
            txt = f'{ln} {"·".join(names)}역 신설'
        elif len(names) == 1:
            txt = f"{ln} {names[0]}역 개통"
        else:
            txt = f"{ln} {names[0]}–{names[-1]} 개통({len(names)}개 역)"
        events.append({"year": year(d), "date": d.replace("-", "."), "kind": "metro", "color": COLORS.get(ln), "text": txt, "sort": 4})
OV = {("1974-08-15","1호선"): "1호선 개통. 서울역–청량리 지하 구간에 경부·경인·경원선 전철 직결",
 ("1978-12-09","경의중앙선"): "경원선 용산–청량리 전철 운행(당시 1호선 계통, 지금의 경의중앙선 구간)",
 ("1980-10-31","2호선"): "2호선 첫 개통: 신설동–성수–종합운동장",
 ("1983-09-16","2호선"): "2호선 을지로입구–성수 개통",
 ("1984-05-22","2호선"): "2호선 서울대입구–신도림–을지로입구 개통으로 순환선 완성",
 ("1996-02-29","2호선"): "2호선 신정지선 신정네거리까지 연장",
 ("1996-03-20","2호선"): "2호선 신정지선 까치산까지 연장",
 ("2000-12-15","6호선"): "6호선 응암순환–상월곡 개통",
 ("2005-12-16","경의중앙선"): "중앙선 전철 청량리–덕소 개통",
 ("2009-07-01","경의중앙선"): "경의선 전철 개통(서울역·가좌–문산)",
 ("2012-12-15","경의중앙선"): "경의선 용산선 구간 가좌–공덕 개통",
 ("2013-11-04","경춘선"): "경춘선 광운대 발착 운행 시작",
 ("2016-09-26","경춘선"): "경춘선 청량리 발착 운행 시작",
 ("2010-12-29","공항철도"): "공항철도 김포공항–서울역 개통",
 ("2024-08-10","8호선"): "8호선 별내선 연장(암사–별내)"}
for e in events:
    k = (e["date"].replace(".", "-"), next((ln for ln in COLORS if COLORS[ln] == e["color"]), ""))
    if k in OV: e["text"] = OV[k]
json.dump({"lines": lines, "stations": stations}, open(f"{B}/metro.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump(events, open(f"{B}/metro_events.json", "w"), ensure_ascii=False, indent=0)
print(len(stations), "stations", sum(len(l["edges"]) for l in lines), "edges", len(events), "events", file=sys.stderr)
