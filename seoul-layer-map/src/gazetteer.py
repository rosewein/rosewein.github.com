"""경유지·기종점 지명을 좌표로 바꾼다. 우선순위: 별칭 → 지하철·철도역 → 법정동 → 버스 정류장 이름."""
import json, csv, re, statistics, os
from collections import defaultdict
from paths import CODE, DATA, RAW, WORK
B = RAW

def _centroid(geom):
    xs, ys, n = 0, 0, 0
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    for poly in polys:
        for x, y in poly[0]:
            xs += x; ys += y; n += 1
    return (xs / n, ys / n)

STATION = {}
for s in json.load(open(f"{B}/subway/raw/sudo.json"))["DATA"]:
    STATION.setdefault(s["name"], (s["lng"], s["lat"]))
for s in json.load(open(f"{DATA}/rail.json"))["stations"]:
    nm = re.sub(r"\(.*?\)", "", s["name"])
    STATION.setdefault(nm, (s["lng"], s["lat"]))

DONG, GU = {}, {}
for f in json.load(open(f"{B}/raw/seoul_neighborhoods_geo.json"))["features"]:
    DONG[f["properties"]["EMD_KOR_NM"]] = _centroid(f["geometry"])
for f in json.load(open(f"{B}/raw/seoul_municipalities_geo.json"))["features"]:
    GU[f["properties"]["SIG_KOR_NM"]] = _centroid(f["geometry"])
# '종로1가' 같은 가 단위를 묶은 대표점
for k in list(DONG):
    m = re.match(r"^(.+?)(\d+)가$", k)
    if m:
        base = m.group(1)
        DONG.setdefault(base, DONG[k])

STOPS = defaultdict(list)
for r in csv.DictReader(open(f"{B}/bus/raw/seoul_bus_stops.csv")):
    try:
        STOPS[r["name"]].append((float(r["lng"]), float(r["lat"])))
    except ValueError:
        pass

ALIAS = json.load(open(f"{DATA}/place_alias.json")) if os.path.exists(f"{DATA}/place_alias.json") else {}

def _median(pts):
    return (statistics.median(p[0] for p in pts), statistics.median(p[1] for p in pts))

def _spread(pts):
    """점들이 얼마나 흩어져 있는지(km, 중앙값 기준 최대 거리의 80분위)."""
    if len(pts) == 1: return 0
    mx, my = _median(pts)
    ds = sorted(((x - mx) * 88.4) ** 2 + ((y - my) * 111.0) ** 2 for x, y in pts)
    return ds[int(len(ds) * 0.8) - 1 if len(ds) > 1 else 0] ** 0.5

def clean(name):
    n = name.strip()
    n = re.sub(r"\s+", "", n)
    n = re.sub(r"(종점|차고지|기점|입구앞|앞|사거리|삼거리|네거리|로터리|오거리)$", lambda m: "" if m.group(1) in ("종점", "차고지", "기점", "앞") else m.group(1), n)
    return n

def locate(name):
    """(lng, lat, method) 또는 None"""
    if not name:
        return None
    raw = name.strip()
    n = clean(raw)
    if n in ALIAS:
        v = ALIAS[n]
        if isinstance(v, list): return (v[0], v[1], "alias")
        n = v
    base = re.sub(r"역$", "", n)
    if base in ALIAS and n not in ALIAS:
        v = ALIAS[base]
        if isinstance(v, list): return (v[0], v[1], "alias")
        n = v
    cands = [n, re.sub(r"역$", "", n)]
    for c in cands:
        if c in STATION: return (*STATION[c], "station")
    for c in cands:
        if c in DONG: return (*DONG[c], "dong")
        if c + "동" in DONG: return (*DONG[c + "동"], "dong")
        if c in GU: return (*GU[c], "gu")
    for c in (raw, n, n + "역", n + "사거리", n + "삼거리", n + "입구"):
        if c in STOPS: return (*_median(STOPS[c]), "stop")
    # 정류장 이름 앞부분 일치(예: '화곡동' → '화곡동종점')
    pref = [k for k in STOPS if k.startswith(n) and len(n) >= 2]
    if pref and len(n) >= 3:
        pts = [p for k in pref for p in STOPS[k]]
        if _spread(pts) < 2.5:
            return (*_median(pts), "stop-prefix")
    if len(n) >= 3:
        cont = [k for k in STOPS if n in k]
        if cont:
            pts = [p for k in cont for p in STOPS[k]]
            if _spread(pts) < 2.0:
                return (*_median(pts), "stop-contains")
    m = re.match(r"^(.+?)(?:\d+|본)동$", n)
    if m and m.group(1) + "동" in DONG: return (*DONG[m.group(1) + "동"], "dong-num")
    if n.endswith("리") and n[:-1] + "동" in DONG: return (*DONG[n[:-1] + "동"], "ri-dong")
    m = re.match(r"^(.+?동)\d*", n)
    if m and m.group(1) in DONG: return (*DONG[m.group(1)], "dong-prefix")
    return None

if __name__ == "__main__":
    import sys
    for q in sys.argv[1:]:
        print(q, locate(q))
