"""「조선 후기」 단계에 그릴 한성부(성저십리) 바깥 경계 근사선: data/joseon_bound.json

python3 src/joseon_bound.py   (지도 자료 data/water.json, data/hanseong1910.json, data/joseon.json만 씀)

조선 후기 한성부 경계를 선으로 적은 사료는 없다. 이지가 「한성부 경계가 얼추 나왔다 싶으면 어느 정도 선을 그어도 될 것 같다」,
「조선 후기 바깥 경계를 해야 『대동지지』 화살표가 잘 읽힐 것 같다」고 해서(2026-11-27) 근거가 다른 근사선 두 개를 시안으로 보였고,
이지가 ga(사산금표 경계)를 골랐다(2026-11-27). 지도 자료에는 ga만 쓰고, na는 견주는 값만 찍는다.

- ga(사산금표 경계를 따라 그린 선): 『속대전』 사산금표와 「사산금표도」(1765, 영조 때 넓힌 금표 구역 점선)의 지명 차례
  (東道 대보동·수유현·우이천·상벌리·하벌리·장위리·송계교~중량포, 南道 중량포·전곶교·두모포~용산, 北道 대보동·보현봉·저서현·
  연서구관기·대조리~석관현, 西道 석관현·시위동·사천도관·성산·망원정~마포)를 지금 물길과 봉우리로 이은 것이다.
  동쪽 우이천→중랑천, 남쪽 한강, 서쪽 불광천→홍제천(모래내), 북쪽 족두리봉–향로봉–비봉–문수봉–보현봉–대성문–대동문 능선(직선으로 이음),
  대동문에서 우이천 위 끝까지 직선. 출처: 서울역사편찬원 『조선시대 다스림으로 본 성저십리』(2019) 98–102쪽(지명과 사산금표도 그림).
  같은 책 44쪽(김경록)은 경계가 「대체적으로 사산금표와 일치」, 100쪽(유승희)은 사산금표와 한성부 경계가 「달랐다」고 본다.
- na(1910년 선에서 중랑천 동쪽을 뺀 선): HGIS 1910년 한성부 경계(추정선)에서 중랑천 동쪽을 뺐다. 중랑천 동쪽(면목·중곡·능동 등)은
  조선 시대 양주 땅이었다가 갑오개혁 뒤 한성부가 됐다는 서술(서울지명사전 2009, 2차)에 따른 것이다.
  같은 책 37쪽(김경록)도 정도 초기 성저십리를 동쪽은 중랑천, 서쪽은 비봉에서 홍제천을 따라 한강까지로 적는다(고동환 2006 인용).
- 두 선 모두 남쪽은 한강 본류 북쪽 둑에서 자른다(HGIS 1910년 선은 노량진·흑석 쪽 남쪽 둑까지 들어가 있음, 까닭은 확인 못 함).
- 봉우리 좌표는 OSM 2026-11-22 추출본의 natural=peak(대성문·대동문은 안내판 점). 물길은 data/water.json의 OSM 하천선.
"""
import json, math, warnings
import pyproj
from shapely.geometry import shape, Point, Polygon, LineString, mapping
from shapely.ops import linemerge, substring, unary_union, transform
from paths import DATA
warnings.filterwarnings("ignore")
F = lambda n: f"{DATA}/{n}"

_to = pyproj.Transformer.from_crs(4326, 5186, always_xy=True).transform
_fr = pyproj.Transformer.from_crs(5186, 4326, always_xy=True).transform
P = lambda g: transform(_to, g)
G = lambda g: transform(_fr, g)

w = json.load(open(F("water.json"))); hs = json.load(open(F("hanseong1910.json"))); jo = json.load(open(F("joseon.json")))
gates = [p for p in jo["points"] if p["kind"] == "문"]
CEN = P(Point(sum(p["lng"] for p in gates) / len(gates), sum(p["lat"] for p in gates) / len(gates)))   # 도성 가운데(성문 7곳 평균)

def river(name):   # 같은 이름 하천선 가운데 가장 긴 이어진 줄기
    u = unary_union([P(shape(l["geom"])) for l in w["lines"] if l["name"] == name])
    m = u if u.geom_type == "LineString" else linemerge(u)
    return max(m.geoms, key=lambda g: g.length) if m.geom_type == "MultiLineString" else m

PEAK = {"족두리봉": (126.94296, 37.61796), "향로봉": (126.95117, 37.62511), "비봉": (126.95625, 37.62561), "문수봉": (126.97163, 37.63243),
        "보현봉": (126.97422, 37.62858), "대성문": (126.97717, 37.63327), "대동문": (126.9859, 37.64047)}
pk = {n: P(Point(*xy)) for n, xy in PEAK.items()}
jr, ui, hj, bg = river("중랑천"), river("우이천"), river("홍제천"), river("불광천")
# 방향(확인함): 중랑천 위→한강, 우이천 발원지→중랑천 합류, 불광천 위 끝→홍제천 합류, 홍제천 위→한강
d_ui = jr.project(Point(ui.coords[-1])); d_bg = hj.project(Point(bg.coords[-1]))
m_jr, m_hj = Point(jr.coords[-1]), Point(hj.coords[-1])
S = 4000   # 한강 너머로 내린 거리(m). 한강 수면을 빼면서 잘린다

_wa = P(shape(w["area"])).buffer(0)
han = max(_wa.geoms, key=lambda g: g.area) if _wa.geom_type == "MultiPolygon" else _wa   # 한강 본류에 이어진 수면
def cut_han(g):
    g = g.difference(han)
    if g.geom_type == "MultiPolygon": g = [x for x in g.geoms if x.contains(CEN)][0]
    g = g.buffer(90).buffer(-90)   # 청계천·정릉천처럼 한강 수면에 이어진 좁은 물길이 낸 틈을 메움
    return max(g.geoms, key=lambda x: x.area) if g.geom_type == "MultiPolygon" else g

ring = [(m_hj.x, m_hj.y - S), (m_jr.x, m_jr.y - S)]
ring += list(substring(jr, jr.length, d_ui).coords)            # 중랑천 하구 → 우이천 합류(거슬러 올라감)
ring += list(ui.coords)[::-1]                                   # 우이천 → 발원지
ring += [(pk[n].x, pk[n].y) for n in ["대동문", "대성문", "보현봉", "문수봉", "비봉", "향로봉", "족두리봉"]]
ring += list(bg.coords)                                         # 불광천 → 홍제천 합류
ring += list(substring(hj, d_bg, hj.length).coords)            # 홍제천(모래내) → 한강
ga = cut_han(Polygon(ring).buffer(0))

o1910 = P(shape(hs["outline"])).buffer(0)
east = Polygon([(jr.coords[0][0], jr.coords[0][1] + 6000)] + list(jr.coords) +
               [(m_jr.x, m_jr.y - S), (m_jr.x + 20000, m_jr.y - S), (m_jr.x + 20000, jr.coords[0][1] + 6000)]).buffer(0)
na = cut_han(o1910.difference(east))

def line(g):
    ln = G(LineString(g.exterior.coords).simplify(15))
    return [[round(x, 5), round(y, 5)] for x, y in ln.coords]

def dist8(g):   # 도성 가운데에서 8방위로 선까지(km), 『대동지지』 강역과 견주려고
    out = {}
    for nm, dx, dy in [("동", 1, 0), ("동남", 1, -1), ("남", 0, -1), ("서남", -1, -1), ("서", -1, 0), ("서북", -1, 1), ("북", 0, 1), ("동북", 1, 1)]:
        n = math.hypot(dx, dy); ray = LineString([(CEN.x, CEN.y), (CEN.x + dx / n * 30000, CEN.y + dy / n * 30000)])
        x = ray.intersection(g.exterior); pts = [x] if x.geom_type == "Point" else list(getattr(x, "geoms", []))
        out[nm] = round(min(CEN.distance(p) for p in pts) / 1000, 1) if pts else None
    return out

out = {"note": "조선 후기 한성부 바깥 경계 근사선. 경계를 적은 사료는 없어 「사산금표도」(1765) 금표 경계를 지금 물길·봉우리로 이음. 만든 법은 src/joseon_bound.py",
       "line": line(ga), "km2": round(ga.area / 1e6, 1)}
json.dump(out, open(F("joseon_bound.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("ga(지도)", out["km2"], "km2", len(out["line"]), "pts", dist8(ga))
print("na(견줌)", round(na.area / 1e6, 1), "km2", dist8(na))
