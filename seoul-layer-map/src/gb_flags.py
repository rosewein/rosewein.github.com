"""필지 위치에 개발제한구역(그린벨트) 여부를 붙인다(분석용, 결과 파일은 공개 저장소에 넣지 않음).
    python3 -I gb_flags.py <개발제한구역 SHP(.shp 앞부분)> <loc.npz> <출력 npz> [인코딩=cp949]
- SHP: V-World 「용도지역지구정보」(dsId=24) 「개발제한구역지관리/개발제한구역」 전국 파일. EPSG:5186이어야 한다.
- 고유번호(A1) 8–9번째 글자가 '11'인 서울 폴리곤만 쓴다.
- 출력: g{연도} = loc.npz의 x{연도}, y{연도}와 같은 순서의 0/1(위치 없는 필지는 0), 그리고 서울 그린벨트 면적."""
import sys, numpy as np, shapefile, shapely
from shapely.geometry import shape
from shapely.ops import unary_union
src, locf, out = sys.argv[1:4]; enc = sys.argv[4] if len(sys.argv) > 4 else "cp949"
r = shapefile.Reader(src, encoding=enc)
gs = [shape(sr.shape.__geo_interface__).buffer(0) for sr in r.iterShapeRecords() if sr.record[1][7:9] == "11"]
gb = unary_union(gs); shapely.prepare(gb)
L = np.load(locf); res = {"area_km2": np.array(gb.area / 1e6)}
for k in L.files:
    if k[0] != "x": continue
    y = k[1:]; X, Y = L[f"x{y}"], L[f"y{y}"]; ok = ~np.isnan(X)
    g = np.zeros(len(X), np.uint8); g[ok] = shapely.contains_xy(gb, X[ok], Y[ok]); res[f"g{y}"] = g
np.savez_compressed(out, **res)
print("서울 그린벨트", round(gb.area / 1e6, 2), "㎢, 폴리곤", len(gs), "· 1995년 필지 중", int(res["g1995"].sum()), "개가 안에 있음")
