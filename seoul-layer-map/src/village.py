"""마을버스 레이어: 해마다 11월 셋째 수요일 하루치 승하차 기록에서 마을버스가 선 정류장을 모으고,
정류장에서 걸어갈 만한 거리(300m) 안을 '버스가 닿는 땅'으로 본다.
시내버스 정류장 300m 밖인데 마을버스 정류장 300m 안인 곳 = 마을버스로만 닿는 곳.

입력: 연도별 CSV(열린데이터광장 OA-12912와 같은 열 구성)
출력: village.json
"""
import csv, io, json, re, sys, zipfile, datetime, collections, os
from shapely.geometry import Point, mapping
from shapely.ops import unary_union

B = "/home/claude/data/build"
GU = "종로|중구|용산|성동|광진|동대문|중랑|성북|강북|도봉|노원|은평|서대문|마포|양천|강서|구로|금천|영등포|동작|관악|서초|강남|송파|강동"
VILLAGE = re.compile(rf"^({GU})\d{{2}}(-\d)?$")
KX, KY = 88.4, 111.0   # 위도 37.5도 근처 1도 = km
R = 0.3                # 걸어서 닿는 거리(km)

# 정류장 좌표: 2026년 목록(kyckang/SeoulTransitMap_data)과 2019년 6월 「서울시 버스노선별 표준정류장ID 연계 좌표정보」
S26, S19 = {}, {}
for s in csv.DictReader(open("/home/claude/data/bus/raw/seoul_bus_stops.csv")):
    xy = (float(s["lng"]), float(s["lat"]))
    S26[s["node_id"]] = xy
    if s.get("ars_id"): S26.setdefault("ars:" + s["ars_id"].zfill(5), xy)
X19 = "/home/claude/data/bus/raw/stops_2019.json"
if os.path.exists(X19):
    for nid, ars, x, y in json.load(open(X19)):
        S19[nid] = (x, y)
        if ars: S19.setdefault("ars:" + ars.zfill(5), (x, y))


def lookup(year, nid, ars):
    first, second = (S19, S26) if year <= 2019 else (S26, S19)
    for D in (first, second):
        if nid and nid in D: return D[nid]
        if ars and ("ars:" + ars.zfill(5)) in D: return D["ars:" + ars.zfill(5)]
    return None


def third_wednesday(y):
    d = datetime.date(y, 11, 1)
    d += datetime.timedelta(days=(2 - d.weekday()) % 7)
    return (d + datetime.timedelta(days=14)).strftime("%Y%m%d")


def cover(pts):
    if not pts: return None
    return unary_union([Point(x * KX, y * KY).buffer(R, 16) for x, y in pts])


def to_lonlat(geom, tol=0.03):
    g = geom.simplify(tol)
    polys = list(g.geoms) if hasattr(g, "geoms") else [g]
    out = []
    for p in polys:
        if p.area < 0.01: continue
        rings = [p.exterior] + list(p.interiors)
        out.append([[[round(x / KX, 5), round(y / KY, 5)] for x, y in r.coords] for r in rings])
    return {"type": "MultiPolygon", "coordinates": out}


def process(year, rows, cols):
    """cols: 열 이름 → 위치. 2015년 파일엔 표준정류장ID가 없고 ARS 번호만 있다"""
    iNo, iA = cols["노선번호"], cols["버스정류장ARS번호"]
    iN = cols.get("표준버스정류장ID")
    v_st, c_st = set(), set(); v_routes = set(); miss = collections.Counter()
    for r in rows:
        no, ars = r[iNo].strip(), r[iA].strip()
        nid = r[iN].strip() if iN is not None else None
        is_v = bool(VILLAGE.match(no))
        if ars in ("", "~", "0") and not nid: continue
        xy = lookup(year, nid, ars)
        if not xy:
            miss["village" if is_v else "city"] += 1; continue
        (v_st if is_v else c_st).add(xy)
        if is_v: v_routes.add(no)
    vc, cc = cover(v_st), cover(c_st)
    only = vc.difference(cc) if vc is not None and cc is not None else vc
    rec = {"y": year, "v_routes": len(v_routes), "v_stops": len(v_st), "c_stops": len(c_st),
           "v_area": round(vc.area, 1) if vc is not None else 0, "only_area": round(only.area, 1) if only is not None else 0,
           "c_area": round(cc.area, 1) if cc is not None else 0, "miss": dict(miss),
           "stops": sorted([round(x, 5), round(y, 5)] for x, y in v_st), "only": to_lonlat(only) if only is not None else None}
    print(year, {k: v for k, v in rec.items() if k not in ("stops", "only")}, file=sys.stderr)
    return rec


def read_csv(b, day=None):
    rd = csv.reader(io.StringIO(b.decode("cp949", errors="replace")))
    head = [h.strip().strip('"') for h in next(rd)]
    cols = {h: i for i, h in enumerate(head)}
    rows = [r for r in rd if len(r) >= len(head) - 1 and (day is None or r[0].strip() == day)]
    return cols, rows


def load(path, year):
    day = third_wednesday(year)
    if path.endswith(".zip"):
        z = zipfile.ZipFile(path)
        name = [n for n in z.namelist() if f"{year}11" in n] or z.namelist()
        cols, rows = read_csv(z.read(name[0]), day)
        return cols, rows, day
    data = open(path, "rb").read()
    cols, rows = read_csv(data, day)
    if not rows:  # 하루치 파일(2026)
        cols, rows = read_csv(data); day = rows[0][0] if rows else day
    return cols, rows, day


if __name__ == "__main__":
    out_path = f"{B}/village.json"
    res = json.load(open(out_path)) if os.path.exists(out_path) else {"years": {}}
    for arg in sys.argv[1:]:
        y, p = arg.split("=", 1)
        cols, rows, day = load(p, int(y))
        rec = process(int(y), rows, cols); rec["day"] = day
        res["years"][y] = rec
    json.dump(res, open(out_path, "w"), ensure_ascii=False, separators=(",", ":"))
    print("bytes", os.path.getsize(out_path), file=sys.stderr)
