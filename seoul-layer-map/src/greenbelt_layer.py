"""그린벨트(개발제한구역) 레이어 자료: V-World 「용도지역지구정보」(dsId=24) 개발제한구역 전국 SHP에서 서울만 잘라 지도용으로 줄인다.
    python3 -I greenbelt_layer.py <지금 SHP(.shp 앞부분)> <기준일 YYYY-MM-DD> [<옛 SHP> <기준일> <옛 좌표계 EPSG>] [출력 json]
    예) greenbelt_layer.py AL_D032_00_20261109 2026-11-09 AL_00_D032_20160305 2016-03-05 5174
- 고유번호(A1) 8–9번째 글자가 '11'인 폴리곤이 서울이다. 지금 파일은 EPSG:5186, 2016년 파일은 .prj에 Bessel 중부원점으로
  적혀 있지만 EPSG:5174(수정 중부원점)로 바꿔야 지금 경계와 맞는다(겹침 비율 0.996, 2097로 바꾸면 0.68).
- 2015-12-24 파일에는 서울 폴리곤이 없다(2026-11-26 확인).
- 출력: {date, area_km2, geo(MultiPolygon 경위도, 8m 단순화), old: {date, area_km2, released_km2, added_km2}}"""
import sys, os, json, shapefile
from shapely.geometry import shape
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, transform
from pyproj import Transformer
HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
out = args.pop() if len(args) in (3, 6) else os.path.join(HERE, "..", "data", "greenbelt.json")
def load(f, epsg):
    cpg = open(f + ".cpg").read().upper() if os.path.exists(f + ".cpg") else "EUC-KR"
    r = shapefile.Reader(f, encoding="utf-8" if "UTF" in cpg else "cp949")
    g = unary_union([shape(sr.shape.__geo_interface__).buffer(0) for sr in r.iterShapeRecords() if sr.record[1][7:9] == "11"])
    return g if epsg == 5186 else transform(Transformer.from_crs(epsg, 5186, always_xy=True).transform, g)
now = load(args[0], 5186)
inv = Transformer.from_crs(5186, 4326, always_xy=True).transform
g = transform(inv, now.simplify(8))
ps = [orient(p, -1.0) for p in (g.geoms if hasattr(g, "geoms") else [g]) if p.area > 0]
r5 = lambda cs: [[round(x, 5), round(y, 5)] for x, y in cs]
res = {"date": args[1], "area_km2": round(now.area / 1e6, 2), "geo": [[r5(p.exterior.coords)] + [r5(i.coords) for i in p.interiors] for p in ps]}
if len(args) >= 5:
    old = load(args[2], int(args[4]))
    res["old"] = {"date": args[3], "area_km2": round(old.area / 1e6, 2), "released_km2": round(old.difference(now).area / 1e6, 2), "added_km2": round(now.difference(old).area / 1e6, 2)}
json.dump(res, open(out, "w"), ensure_ascii=False, separators=(",", ":"))
print({k: v for k, v in res.items() if k != "geo"}, "폴리곤", len(ps), os.path.getsize(out) // 1024, "KB →", out)
