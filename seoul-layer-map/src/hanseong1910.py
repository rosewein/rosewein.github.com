"""1914년 앞 한성부·경성부 경계: 국사편찬위원회 HGIS 역사적 행정구역(1910.5–1945.8)에서 뽑아 data/hanseong1910.json을 만든다.

python3 src/hanseong1910.py   (원자료: $SLM_RAW/hgis/hgis_admin_1910_1945.gpkg, HGIS 「행정구역 GIS 데이터(1910~1945년)」 zip 안의 gpkg)

- outline: 한성부(1910-05-10~09-30)와 경성부(1910-10-01~1914-02-28)의 바깥 경계. 두 시기가 같다(넓이 243.6㎢, 겹침 1.0).
- bu1910: 한성부 5부(1910-05-10~09-30). 중부 말고는 도성 밖 성저십리까지 나뉘어 있다.
- bm1911: 경성부 5부 8면. HGIS는 시작일을 1910-10-01로 두었지만 참고 칸에 「부와 면의 설정은 1911-04-01」이라고 적었다.
- HGIS 자료는 1910년 5월부터라 그 앞 경계는 없다. 1899–1910년에 이 경계를 쓰는 것은 그 사이 바깥 경계가 크게 바뀌지 않았다고 보는 것이다(확인 못 함).
- 다섯 부와 여덟 면은 서로 붙어 있으므로 먼저 서로 꼭 맞게 고친 뒤(clean) 경계선이 어긋나지 않게 한꺼번에 줄인다(shapely coverage_simplify).
"""
import json, os
import geopandas as gpd
import shapely
from shapely.geometry import mapping, MultiPolygon
from shapely.geometry.polygon import orient
from paths import RAW, DATA

GPKG = os.path.join(RAW, "hgis", "hgis_admin_1910_1945.gpkg")
TOL = 0.00025   # 도(°). 약 20–28m(지도 확대 한계에서 눈에 띄지 않는 정도)

def load(where):
    g = gpd.read_file(GPKG, layer="행정구역_GIS_폴리곤", where=where)
    return g.sort_values("key").reset_index(drop=True)

def d3geom(g):
    # d3-geo는 바깥 고리가 시계 방향이어야 작은 면으로 그린다(GeoJSON 표준과 반대)
    parts = g.geoms if g.geom_type == "MultiPolygon" else [g]
    return json.loads(json.dumps(mapping(MultiPolygon([orient(p, sign=-1.0) for p in parts])), default=list))

def rounded(gj, nd=4):
    def r(c): return [round(c[0], nd), round(c[1], nd)] if isinstance(c[0], float) else [r(x) for x in c]
    gj["coordinates"] = r(gj["coordinates"]); return gj

def km2(g): return round(gpd.GeoSeries([g], crs=4326).to_crs(5179).area.iloc[0] / 1e6, 1)

def clean(geoms):
    """HGIS 면은 이웃끼리 조금씩 겹치거나 떠 있어(coverage가 맞지 않음) 그대로 coverage_simplify하면 안쪽 선이 군데군데 빠진다
    (2026-11-27에 찾음: 1910년 5부 안쪽 선 0.58°가 0.46°로 줄어 도성 밖 선이 끊겨 보였고, 1911년 5부 8면은 이웃 사이에
    폭 1cm 안팎의 실금 44곳이 있었음). 모든 경계를 이어 작은 조각으로 나눈 뒤, 조각마다 가장 많이 겹치는 면에 붙이고
    (빈틈 조각은 맞닿은 변이 가장 긴 면에 붙임) 다시 합쳐 서로 꼭 맞는 면을 만든다. 넓이 차이는 모두 합쳐 100㎡ 아래"""
    faces = list(shapely.polygonize([shapely.union_all([g.boundary for g in geoms])]).geoms)
    tree = shapely.STRtree(geoms)
    own = [[] for _ in geoms]
    for f in faces:
        idx = tree.query(f)
        best = max([(geoms[i].intersection(f).area, i) for i in idx], default=(0, None))
        if best[0] < 0.5 * f.area:
            best = max((geoms[i].boundary.intersection(f.boundary).length, i) for i in idx)
        own[best[1]].append(f)
    out = [shapely.union_all(o) for o in own]
    assert shapely.coverage_is_valid(out)
    return shapely.coverage_simplify(out, TOL)

def parts(df):
    """안쪽 경계선(겹치는 변은 한 번만)과 이름 자리. 면은 바깥 경계 하나로 칠하므로 따로 두지 않는다"""
    simp = clean(list(df.geometry))
    lines = shapely.union_all([g.boundary for g in simp]).difference(shapely.union_all(simp).boundary.buffer(1e-6))
    # 서강 앞 한강 수면과 여의도는 북부(1911년 연희면)라서 서부(서강면)와의 경계가 서강 쪽 강둑을 따라 간다.
    # 한국민족문화대백과 「여의도」: 조선시대 한성부 북부 연희방 여의도계, 일제강점기 경성부 연희면. 물 위라고 지우지 않는다
    lines = shapely.line_merge(lines)
    ls = list(lines.geoms) if hasattr(lines, "geoms") else [lines]
    mesh = rounded({"type": "MultiLineString", "coordinates": [list(map(list, l.coords)) for l in ls]})
    labs = [{"name": n, "kind": t, "km2": km2(g0), "p": [round(c, 4) for c in g0.representative_point().coords[0]]}
            for n, t, g0 in zip(df["name"], df["type"], df.geometry)]
    return {"mesh": mesh, "labels": labs}

hs = load("key='11'")
bu = load("up_key='11'")
bm = load("up_key='2/10' and begin='19101001'")
outer = shapely.union_all(clean(list(bm.geometry)))
out = {
    "src": "국사편찬위원회 HGIS 역사적 행정구역 공간데이터(1910.5–1945.8)",
    "outline": rounded(d3geom(outer)), "km2": km2(hs.geometry.iloc[0]), "trust": int(hs.trust.iloc[0]),
    "bu1910": parts(bu), "bm1911": parts(bm),
}
p = os.path.join(DATA, "hanseong1910.json")
json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("outline", out["km2"], "km2 · 5부", len(out["bu1910"]["labels"]), "· 5부 8면", len(out["bm1911"]["labels"]), "·", os.path.getsize(p), "bytes")
