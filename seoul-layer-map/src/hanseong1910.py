"""1914년 앞 한성부·경성부 경계: 국사편찬위원회 HGIS 역사적 행정구역(1910.5–1945.8)에서 뽑아 data/hanseong1910.json을 만든다.

python3 src/hanseong1910.py   (원자료: $SLM_RAW/hgis/hgis_admin_1910_1945.gpkg, HGIS 「행정구역 GIS 데이터(1910~1945년)」 zip 안의 gpkg)

- outline: 한성부(1910-05-10~09-30)와 경성부(1910-10-01~1914-02-28)의 바깥 경계. 두 시기가 같다(넓이 243.6㎢, 겹침 1.0).
- bu1910: 한성부 5부(1910-05-10~09-30). 중부 말고는 도성 밖 성저십리까지 나뉘어 있다.
- bm1911: 경성부 5부 8면. HGIS는 시작일을 1910-10-01로 두었지만 참고 칸에 「부와 면의 설정은 1911-04-01」이라고 적었다.
- HGIS 자료는 1910년 5월부터라 그 앞 경계는 없다. 1899–1910년에 이 경계를 쓰는 것은 그 사이 바깥 경계가 크게 바뀌지 않았다고 보는 것이다(확인 못 함).
- 다섯 부와 여덟 면은 서로 붙어 있으므로 경계선이 어긋나지 않게 한꺼번에 줄인다(shapely coverage_simplify).
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

def parts(df, outer):
    """안쪽 경계선(겹치는 변은 한 번만)과 이름 자리. 면은 바깥 경계 하나로 칠하므로 따로 두지 않는다"""
    simp = shapely.coverage_simplify(list(df.geometry), TOL)
    lines = shapely.union_all([g.boundary for g in simp]).difference(outer.boundary.buffer(1e-6))
    lines = shapely.line_merge(lines)
    ls = list(lines.geoms) if hasattr(lines, "geoms") else [lines]
    mesh = rounded({"type": "MultiLineString", "coordinates": [list(map(list, l.coords)) for l in ls]})
    labs = [{"name": n, "kind": t, "km2": km2(g0), "p": [round(c, 4) for c in g0.representative_point().coords[0]]}
            for n, t, g0 in zip(df["name"], df["type"], df.geometry)]
    return {"mesh": mesh, "labels": labs}

hs = load("key='11'")
bu = load("up_key='11'")
bm = load("up_key='2/10' and begin='19101001'")
outer = shapely.union_all(shapely.coverage_simplify(list(bm.geometry), TOL))
out = {
    "src": "국사편찬위원회 HGIS 역사적 행정구역 공간데이터(1910.5–1945.8)",
    "outline": rounded(d3geom(outer)), "km2": km2(hs.geometry.iloc[0]), "trust": int(hs.trust.iloc[0]),
    "bu1910": parts(bu, outer), "bm1911": parts(bm, outer),
}
p = os.path.join(DATA, "hanseong1910.json")
json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("outline", out["km2"], "km2 · 5부", len(out["bu1910"]["labels"]), "· 5부 8면", len(out["bm1911"]["labels"]), "·", os.path.getsize(p), "bytes")
