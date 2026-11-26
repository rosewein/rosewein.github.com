"""역 둘레 땅값 레이어 자료: station_rings_ctrl.py 결과(json)를 지도용으로 줄이고 고리 모양을 붙인다.
    python3 -I station_land_layer.py <rings_ctrl.json> [출력 json] [--gb=<그린벨트를 넣어 돌린 rings_ctrl json>] [--platforms=<json>]   (출력 기본: data/station_land.json)
- --platforms(station_platforms.py 출력)를 주면 고리 중심을 처음 연 노선의 승강장으로, 보로노이 칸을 노선별 승강장으로 만들고
  같은 역 승강장의 칸을 합친다. rings_ctrl.json도 같은 --platforms로 돌린 것이어야 범위가 맞는다.
- --gb를 주면 역마다 개통 5년 전 500m 안 필지 가운데 2026년 그린벨트 안인 비율(gb)을 붙인다(값은 그린벨트 필지를 넣은 계산 그대로).

- 값: 같은 필지 변화에서 '비슷한 땅'(같은 구 · 개통 5년 전 값 10분위 같음 · 열린 역 1km 밖) 변화를 뺀 것(%).
  개통 해로부터 −5…+5년, 고리 0–250 · 250–500 · 500–1000m. 고리 안 필지가 20개 미만이면 null.
  서울 전체와 견준 값(s)도 함께 둔다.
- 고리 모양: 역에서 r m 고리 ∩ 개통 5년 뒤 열려 있는 역들의 보로노이 칸(그 역에 가장 가까운 땅) ∩ 서울.
  필지를 가장 가까운 역에만 붙인 계산과 같은 범위다. 좌표는 EPSG:5186에서 자르고 경위도로 돌려 소수 5자리.
- 필지 위치·대응표 같은 중간 자료는 넣지 않는다(역별 중앙값만)."""
import sys, os, json
import numpy as np
from pyproj import Transformer
from shapely.geometry import Point, Polygon, MultiPolygon, MultiPoint, mapping
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, voronoi_diagram, transform
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "..", "data")
pos = [a for a in sys.argv[1:] if not a.startswith("--")]; opt = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--"))
R = json.load(open(pos[0])); OUT = pos[1] if len(pos) > 1 else os.path.join(DATA, "station_land.json")
GBS = {(r["name"], r["T"]): r.get("gb") for r in json.load(open(opt["gb"]))} if "gb" in opt else {}
metro = json.load(open(os.path.join(DATA, "metro.json"))); topo = json.load(open(os.path.join(DATA, "emd_topo.json")))
fwd = Transformer.from_crs(4326, 5186, always_xy=True).transform
inv = Transformer.from_crs(5186, 4326, always_xy=True).transform
# 서울 경계(법정동 합침, 경위도)
sx, sy = topo["transform"]["scale"]; tx, ty = topo["transform"]["translate"]; arcs = []
for a in topo["arcs"]:
    x = y = 0; pts = []
    for dx, dy in a: x += dx; y += dy; pts.append((x * sx + tx, y * sy + ty))
    arcs.append(pts)
def ring(idx):
    out = []
    for i in idx:
        seg = arcs[i] if i >= 0 else arcs[~i][::-1]; out.extend(seg if not out else seg[1:])
    return out
polys = [Polygon(ring(g["arcs"][0]), [ring(r) for r in g["arcs"][1:]]) if g["type"] == "Polygon" else
         MultiPolygon([Polygon(ring(pp[0]), [ring(r) for r in pp[1:]]) for pp in g["arcs"]])
         for g in topo["objects"]["seoul_neighborhoods_geo"]["geometries"]]
seoul_ll = unary_union([p.buffer(0) for p in polys]); seoul = transform(fwd, seoul_ll)
PF = json.load(open(opt["platforms"]))["stations"] if "platforms" in opt else None
if PF is not None:
    assert [(q["name"], q["first"]) for q in PF] == [(s["name"], s["first"]) for s in metro["stations"]], "platforms json이 metro.json과 순서가 다름"
    allst = [(y, fwd(x, yy), k) for k, q in enumerate(PF) for _, y, x, yy in q["pf"]]
else:
    allst = [(s["first"], fwd(s["lng"], s["lat"]), k) for k, s in enumerate(metro["stations"])]
env = seoul.envelope.buffer(20000)
_cells = {}
def cells(ref):
    if ref not in _cells:
        pts = sorted({(round(x, 1), round(y, 1)) for f, (x, y), _ in allst if f <= ref})
        vd = voronoi_diagram(MultiPoint(pts), envelope=env)
        _cells[ref] = list(vd.geoms)
    return _cells[ref]
def cell_of(ref, xy):
    p = Point(xy)
    for c in cells(ref):
        if c.contains(p) or c.touches(p): return c
    raise RuntimeError("보로노이 칸을 못 찾음")
def station_cell(ref, k):   # 역 k의 승강장 가운데 ref년에 열린 것들의 칸을 합친 것
    return unary_union([cell_of(ref, xy) for f, xy, kk in allst if kk == k and f <= ref])
def geo(g):
    g = transform(inv, g.simplify(4))
    if g.is_empty: return None
    ps = [orient(p, sign=-1.0) for p in (g.geoms if hasattr(g, "geoms") else [g]) if p.geom_type == "Polygon" and p.area > 0]
    r5 = lambda cs: [[round(x, 5), round(y, 5)] for x, y in cs]
    return [[r5(p.exterior.coords)] + [r5(i.coords) for i in p.interiors] for p in ps]
pct = lambda v: None if v is None else round(100 * (2 ** v - 1), 1)
RINGS = [(0, 250), (250, 500), (500, 1000)]
inside = [(k, s) for k, s in enumerate(metro["stations"]) if seoul_ll.contains(Point(s["lng"], s["lat"]))]
out = []
for r in R:
    cand = [(k, s) for k, s in inside if s["name"] == r["name"] and s["first"] == r["T"]]
    assert len(cand) == 1, (r["name"], r["T"], len(cand))
    k, s = cand[0]; T = r["T"]
    ll = PF[k]["center"] if PF else [s["lng"], s["lat"]]   # 고리 중심(--platforms면 처음 연 노선 승강장)
    xy = fwd(*ll)
    c = station_cell(T + 5, k).intersection(seoul)
    shapes = [geo(Point(xy).buffer(b, quad_segs=24).difference(Point(xy).buffer(a, quad_segs=24)).intersection(c) if a else
                  Point(xy).buffer(b, quad_segs=24).intersection(c)) for a, b in RINGS]
    first_line = min(s["opens"], key=lambda l: (s["opens"][l], l))
    rec = {"name": r["name"], "T": T, "date": s.get("dates", {}).get(first_line, str(T)),
           "lines": sorted(s["opens"], key=lambda l: (s["opens"][l], l)), "lng": round(ll[0], 6), "lat": round(ll[1], 6),
           "dev": None if r["dev"] is None else round(r["dev"], 3), "n500": r["n500"],
           "gb": None if GBS.get((r["name"], T)) is None else round(GBS[(r["name"], T)], 3),
           "v": [[pct((r["years"][str(k)][f"{a}-{b}"] or {}).get("sim")) for k in range(-5, 6)] for a, b in RINGS],
           "s": [[pct((r["years"][str(k)][f"{a}-{b}"] or {}).get("seoul")) for k in range(-5, 6)] for a, b in RINGS],
           "n": [(r["years"]["5"][f"{a}-{b}"] or {}).get("n") for a, b in RINGS],
           "geo": shapes}
    out.append(rec)
out.sort(key=lambda r: (r["T"], r["name"]))
json.dump({"ctrl": "비슷한 땅", "rel": [-5, 5], "rings": [[a, b] for a, b in RINGS], "stations": out},
          open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
print("역", len(out), "크기", os.path.getsize(OUT) // 1024, "KB →", OUT)
