import json, os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom
from paths import CODE, DATA, RAW, WORK
B = DATA
# --resnap: 원자료(rail_parts) 없이 지금 data/rail.json의 선형만 선로에 다시 맞춘다(아래 resnap()).
RESNAP = "--resnap" in sys.argv
ST = [] if RESNAP else json.load(open(f"{RAW}/subway/stations_seoul.json"))
ALL = [] if RESNAP else json.load(open(f"{RAW}/subway/raw/sudo.json"))["DATA"]
PREF = ["1호선", "경의중앙선", "경춘선", "공항철도", "서해선", "수인분당선", "4호선", "2호선", "3호선", "5호선", "6호선", "7호선", "8호선", "9호선"]
coord = {}
for ln in PREF[::-1]:
    for s in ALL:
        if s["line"] == ln:
            coord[s["name"]] = (s["lng"], s["lat"])
ALIAS = json.load(open(f"{B}/rail_alias.json")) if os.path.exists(f"{B}/rail_alias.json") else {}

parts = [json.load(open(f)) for f in sorted(glob.glob(f"{WORK}/rail_parts/*.json"))]
segs_in = [sg for p in parts for sg in p.get("segments", [])]
st_in = [st for p in parts for st in p.get("stations", [])]

def y(d):
    return int(str(d)[:4]) if d else None

stations, index = [], {}
info = {}
for st in st_in:
    info.setdefault(st["name"], {}).update({k: v for k, v in st.items() if v not in (None, "")})
missing = []
def sid(name, line):
    nm = ALIAS.get(name, name)
    if nm in index:
        i = index[nm]
        if line not in stations[i]["lines"]: stations[i]["lines"].append(line)
        return i
    rec = info.get(name) or info.get(nm) or {}
    if rec.get("lat") and rec.get("lng"):
        lng, lat = rec["lng"], rec["lat"]
    elif nm in coord:
        lng, lat = coord[nm]
    else:
        missing.append(name); return None
    stations.append({"name": nm, "lng": lng, "lat": lat, "lines": [line],
                     "open": y(rec.get("open")), "openLabel": (rec.get("open") or "").replace("-", "."),
                     "close": y(rec.get("close")), "closeLabel": (rec.get("close") or "").replace("-", "."), "note": rec.get("note", "")})
    index[nm] = len(stations) - 1
    return index[nm]

NETLINES = {"경인선": ["1호선"], "경부선": ["1호선"], "경부고속철도": ["1호선"], "경원선": ["1호선", "경의중앙선"],
            "중앙선": ["경의중앙선"], "경춘선": ["경춘선", "경의중앙선"], "망우선": ["경춘선", "경의중앙선"]}
def netlines(line):
    if line.startswith("경의선") or line.startswith("용산선"): return ["경의중앙선", "공항철도"]
    return NETLINES.get(line, [])

def resnap():
    """data/rail.json의 선형을 지금 방식(geom.via_paths의 snap)으로 다시 그린다. 원자료(rail_parts) 없이 선형만 고칠 때 쓴다.
    선로 자료에 없는 역(옛 역)이 사이에 낀 구간은 앞뒤로 이어진 구간을 묶어 한꺼번에 다시 자른다.
    v1.7.2에서 썼다. rail_build.py를 처음부터 돌려도 같은 선형이 나온다."""
    R = json.load(open(f"{B}/rail.json"))
    S, segs, n, i = R["stations"], R["segs"], 0, 0
    nm = lambda k: S[k]["name"]
    while i < len(segs):
        e, L = segs[i], netlines(segs[i]["line"])
        if not (e.get("p") and L and geom.known(L, nm(e["a"]))):
            i += 1; continue
        grp = [i]
        while grp and not geom.known(L, nm(segs[grp[-1]]["b"])):
            x = grp[-1] + 1
            ok = x < len(segs) and segs[x]["line"] == e["line"] and segs[x]["a"] == segs[grp[-1]]["b"] and segs[x].get("p")
            grp = grp + [x] if ok else None
        if not grp:
            i += 1; continue
        names = [nm(e["a"])] + [nm(segs[g]["b"]) for g in grp]
        coords = {nm(k): (S[k]["lng"], S[k]["lat"]) for k in [e["a"]] + [segs[g]["b"] for g in grp]}
        for g, pp in zip(grp, geom.via_paths(L, names, coords, snap=True)):
            if pp:
                segs[g]["p"] = geom.rnd(pp); n += 1
        i = grp[-1] + 1
    json.dump(R, open(f"{B}/rail.json", "w"), ensure_ascii=False, separators=(",", ":"))
    print("resnap:", n, "segs", file=sys.stderr)

if RESNAP:
    resnap(); sys.exit()
segs = []
straight = []
for sg in segs_in:
    via = sg.get("via") or [sg["from"], sg["to"]]
    ids = [sid(n, sg["line"]) for n in via]
    names = [ALIAS.get(n, n) for n in via]
    coords = {ALIAS.get(n, n): ((stations[i]["lng"], stations[i]["lat"]) if i is not None else None) for n, i in zip(via, ids)}
    paths = geom.via_paths(netlines(sg["line"]), names, coords, snap=True) if netlines(sg["line"]) else [None] * (len(via) - 1)
    for k in range(len(ids) - 1):
        if ids[k] is None or ids[k + 1] is None: continue
        e = {"line": sg["line"], "a": ids[k], "b": ids[k + 1], "open": y(sg["open"]), "openLabel": sg["open"].replace("-", "."),
             "close": y(sg.get("close")), "closeLabel": (sg.get("close") or "").replace("-", "."), "note": sg.get("note", "")}
        if paths[k]:
            e["p"] = geom.rnd(paths[k])   # 끝은 via_paths(snap=True)가 역 좌표로 맞춤
        else: straight.append(f'{sg["line"]}:{via[k]}-{via[k+1]}')
        segs.append(e)
print("straight rail:", straight, file=sys.stderr)
# station open fallback: earliest segment touching it
for i, st in enumerate(stations):
    touching = [s["open"] for s in segs if i in (s["a"], s["b"])]
    if st["open"] is None and touching:
        st["open"] = min(touching); st["openLabel"] = str(st["open"])
    if st["open"] is None: st["open"] = 9999
print("missing coords:", sorted(set(missing)), file=sys.stderr)

events = []
seen = set()
for sg in segs_in:
    k = (sg["line"], sg["open"])
    if k in seen: continue
    seen.add(k)
    if sg.get("noEvent"):
        pass
    else:
      events.append({"year": y(sg["open"]), "date": sg["open"].replace("-", "."), "kind": "rail", "text": sg.get("event") or f'{sg["line"]} {sg["from"]}–{sg["to"]} 개통', "sort": 0})
    if sg.get("close") and sg.get("closeEvent") is not False:
        events.append({"year": y(sg["close"]), "date": sg["close"].replace("-", "."), "kind": "rail", "text": sg.get("closeEvent") or f'{sg["line"]} {sg["from"]}–{sg["to"]} 폐선', "sort": 0})
for st in st_in:
    if st.get("close") and st.get("closeEvent", True):
        events.append({"year": y(st["close"]), "date": st["close"].replace("-", "."), "kind": "rail", "text": f'{st["name"]}역 폐역' + (f' ({st["note"]})' if st.get("note") and len(st["note"]) < 40 else ""), "sort": 0})
for p in parts: events += p.get("extra_events", [])
json.dump({"stations": stations, "segs": segs}, open(f"{B}/rail.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump(events, open(f"{B}/rail_events.json", "w"), ensure_ascii=False, indent=0)
print(len(stations), "stations", len(segs), "segs", len(events), "events", file=sys.stderr)
