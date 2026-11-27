"""1903·1907 옛 지도의 5서 경계(署界)를 따라 그려 data/seogye.json을 만든다

python3 src/seogye.py   (data/oldmap1903.json·oldmap1907.json의 기준점과 data/hanseong1910.json·data/tram.json을 읽음. 원본 사진은 필요 없음)

- 1899–1910년 도성 안은 그 시기 지도의 5서 경계를, 도성 밖은 HGIS 1910년 5부 선을 그린다
  (이지가 시안 「나. 도성 안 바꾸기」와 「1907 지도 선도 따라 그리기」를 고름, 2026-11-27).
  1899–1906년은 1903 「韓國京城全圖」, 1907–1910년은 1907 「實測詳密 最新京城全圖」의 선이다(옛 지도가 깔리는 해와 같음).
- 1903: 범례의 署界는 굵은 점선 사이에 ×표를 단 검은 선(坊界는 가는 쇄선, 電氣鐵道는 붉은 실선). 지도 본체 사진
  ($SLM_RAW/oldmaps/1903_한국경성전도_서울역사022829_사진2.jpg, 3750×3339)을 확대해 ×표 선을 눈으로 따라 찍었다.
  찍은 점과 사진 위 선의 어긋남은 대개 5px(약 11m) 안이다. 청계천 구간은 ×표가 물길 북쪽 둑에 붙어 있어 둑을 따랐다.
- 1907: 署界는 붉은 쇄선. 아카이브 상세 이미지 3번째(전도, 2667×3750)에서 붉은 잉크만 뽑아(HSV) 쇄선을 따라 찍고,
  SIFT 특징점 맞춤(호모그래피, 남은 어긋남 중앙값 0.14px)으로 1907 레이어가 쓰는 전도(1500×2109) 픽셀로 옮겼다. 아래 값은 옮긴 뒤의 전도 픽셀이다.
- 두 지도 모두 도성 안 여덟 구간만 있다. 西署·北署 선은 필운대(弼雲臺) 아래, 北署·東署 선은 大報壇 앞에서 끊기고,
  西署·南署 선은 남산 기슭 성벽 바로 앞에서 끝난다. 그 너머(산과 성 밖)는 두 지도에 그려져 있지 않다.
- 두 지도의 선은 따로 맞췄는데도 서로 중앙값 5–15m(가장 멀리 43m) 안에서 겹친다. HGIS 1910년 5부 선과는 다섯 구간이
  중앙값 11–32m로 가깝고, 中署·東署(종묘 서쪽 길 대 종묘 담 안, 중앙값 약 120m)와 西署·中署(육조거리 가운데 대 백운동천, 약 80m),
  西署·南署(약 40–46m) 구간이 다르다(이 스크립트가 출력함. 2026-11-27 HGIS 선을 고친 뒤 값).
- 좌표는 oldmap1903.py·oldmap1907.py와 같은 성문 7곳 아핀 맞춤으로 바꾼다.
- hgisOutside: HGIS 1910년 5부 안쪽 선에서 도성 안(data/tram.json의 한양도성 선으로 둘러싼 면)을 뺀 것.
- join: 옛 지도 선이 성벽에 닿기 전에 끊긴 두 곳(西署·北署 약 380m 앞, 北署·東署 약 710m 앞)을 HGIS 1910년 선으로 성벽까지 잇는 조각.
  끊긴 끝에서 30–60m 안에 있는 HGIS 선 가운데 성벽을 지나는 선을 골라, 끊긴 끝에서 성벽까지만 잘라 쓴다. 성벽에서 150m 안에서
  끝나는 선(西署·南署, 東署·南署)은 잇지 않는다(HGIS 선이 성벽에 닿는 곳과 성벽을 따라 50–215m 떨어져 있음).
"""
import json, os
import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon, mapping, shape
from shapely.ops import substring, unary_union
from pyproj import Transformer
from paths import DATA

NAMES = {"west_north": ("西署", "北署"), "north_middle": ("北署", "中署"), "north_east": ("北署", "東署"), "middle_east": ("中署", "東署"),
         "west_middle": ("西署", "中署"), "west_south": ("西署", "南署"), "middle_south": ("中署", "南署"), "east_south": ("東署", "南署")}

TRACE_1903 = {  # 1903 사진2 픽셀
    "west_north": [[991, 1208], [1002, 1234], [1009, 1238], [1032, 1246], [1073, 1258], [1100, 1289], [1127, 1316], [1145, 1330], [1182, 1335], [1218, 1335], [1259, 1340], [1277, 1347], [1309, 1375], [1340, 1383], [1384, 1386]],
    "north_middle": [[1384, 1386], [1450, 1388], [1506, 1390], [1575, 1412], [1619, 1423], [1656, 1412], [1700, 1390], [1737, 1378], [1775, 1356], [1837, 1337], [1887, 1331], [1900, 1330]],
    "north_east": [[1900, 1330], [1900, 1237], [1905, 1203], [1913, 1153], [1917, 1120], [1915, 1097], [1912, 1053], [1908, 1020], [1907, 970], [1907, 930], [1915, 887]],
    "middle_east": [[1900, 1330], [1940, 1325], [2002, 1310], [2015, 1340], [1985, 1385], [1965, 1427], [1967, 1470], [1980, 1510], [2000, 1550], [2020, 1580], [2045, 1610], [2065, 1620], [2085, 1622], [2090, 1640], [2097, 1675], [2102, 1695], [2105, 1720], [2112, 1752], [2135, 1790], [2143, 1801]],
    "west_middle": [[1384, 1386], [1381, 1450], [1378, 1500], [1377, 1600], [1378, 1658], [1363, 1663], [1377, 1690], [1388, 1705], [1400, 1717], [1420, 1725], [1443, 1728], [1458, 1732]],
    "west_south": [[1458, 1732], [1458, 1740], [1457, 1767], [1453, 1790], [1448, 1827], [1443, 1840], [1427, 1860], [1413, 1877], [1402, 1893], [1390, 1910], [1373, 1937], [1363, 1960], [1358, 1993], [1357, 2047], [1357, 2080], [1355, 2140], [1345, 2186], [1337, 2230], [1334, 2267], [1359, 2283], [1381, 2311], [1406, 2355], [1441, 2433]],
    "middle_south": [[1458, 1732], [1500, 1735], [1601, 1750], [1680, 1765], [1730, 1782], [1800, 1792], [1859, 1800], [1950, 1801], [2050, 1802], [2143, 1801]],
    "east_south": [[2143, 1801], [2264, 1789], [2364, 1777], [2443, 1777], [2557, 1783], [2664, 1796], [2688, 1799]],
}
TRACE_1907 = {  # 1907 전도(1500×2109) 픽셀(상세 이미지 3번째에서 따라 찍고 옮긴 값)
    "west_north": [[193.0, 976.2], [236.8, 1004.3], [285.2, 1048.2], [325.7, 1048.2], [361.7, 1056.6], [365.6, 1072.3], [425.8, 1078.0]],
    "north_middle": [[425.8, 1078.0], [494.4, 1079.1], [518.0, 1084.7], [558.5, 1104.4], [590.6, 1096.5], [622.6, 1081.9], [671.0, 1060.5], [703.1, 1052.1], [733.4, 1051.0]],
    "north_east": [[733.4, 1051.0], [737.4, 1003.2], [744.1, 957.6], [750.3, 912.6], [748.6, 844.6], [750.3, 778.2]],
    "middle_east": [[733.4, 1051.0], [799.2, 1036.3], [809.9, 1065.0], [789.1, 1080.2], [775.6, 1107.2], [780.1, 1139.3], [798.1, 1189.3], [821.2, 1220.8], [843.7, 1225.3], [851.0, 1252.3], [855.5, 1293.4], [861.7, 1311.4], [875.2, 1329.9]],
    "west_middle": [[425.8, 1078.0], [425.8, 1084.7], [423.6, 1148.8], [421.9, 1212.9], [424.7, 1239.9], [412.3, 1247.8], [421.9, 1261.9], [440.4, 1282.7], [471.9, 1288.9]],
    "west_south": [[471.9, 1288.9], [468.6, 1318.1], [462.4, 1353.0], [446.6, 1371.5], [431.4, 1396.3], [418.5, 1415.4], [406.1, 1430.6], [405.0, 1443.5], [416.8, 1449.7], [412.3, 1465.4], [408.4, 1490.2], [406.1, 1534.1], [401.6, 1571.2], [393.8, 1602.7], [399.9, 1618.4], [418.5, 1627.4], [431.4, 1658.9], [446.6, 1690.4], [459.6, 1716.3]],
    "middle_south": [[471.9, 1288.9], [490.5, 1288.9], [509.6, 1293.4], [562.5, 1301.8], [603.0, 1309.1], [628.3, 1320.4], [659.2, 1327.7], [690.7, 1331.0], [721.6, 1331.0], [771.1, 1329.9], [839.2, 1331.6], [875.2, 1329.9]],
    "east_south": [[875.2, 1329.9], [966.3, 1327.7], [1020.8, 1315.8], [1065.8, 1320.3], [1120.4, 1327.1], [1200.2, 1331.6]],
}

T = Transformer.from_crs(4326, 5186, always_xy=True); Ti = Transformer.from_crs(5186, 4326, always_xy=True)

def affine(json_name):
    om = json.load(open(os.path.join(DATA, json_name)))
    P = np.array([[g["px"], g["py"]] for g in om["gcp"]], float)
    G = np.array([T.transform(g["lng"], g["lat"]) for g in om["gcp"]])
    return np.linalg.lstsq(np.c_[P, np.ones(len(P))], G, rcond=None)[0]

def lines(trace, M):
    out = []
    for k, pts in trace.items():
        xy = np.c_[np.array(pts, float), np.ones(len(pts))] @ M
        out.append({"id": k, "between": list(NAMES[k]), "coords": [[round(a, 6), round(b, 6)] for a, b in (Ti.transform(x, y) for x, y in xy)]})
    return out

sets = [
    {"map": "1903", "title": "한국경성전도", "from": 1899, "to": 1906, "lines": lines(TRACE_1903, affine("oldmap1903.json"))},
    {"map": "1907", "title": "실측상밀 최신경성전도", "from": 1907, "to": 1910, "lines": lines(TRACE_1907, affine("oldmap1907.json"))},
]

hs = json.load(open(os.path.join(DATA, "hanseong1910.json")))
mesh = shape(hs["bu1910"]["mesh"])
wall = Polygon(json.load(open(os.path.join(DATA, "tram.json")))["wall"])
outside = shapely.line_merge(mesh.difference(wall))
def rnd(g):
    gj = mapping(g)
    def r(c): return [round(c[0], 5), round(c[1], 5)] if isinstance(c[0], float) else [r(x) for x in c]
    return {"type": gj["type"], "coordinates": r(gj["coordinates"])}

# 끊긴 끝 잇기(EPSG:5186에서 계산)
to5186g = lambda g: shapely.transform(g, lambda c: np.array(T.transform(c[:, 0], c[:, 1])).T)
to4326g = lambda g: shapely.transform(g, lambda c: np.array(Ti.transform(c[:, 0], c[:, 1])).T)
wallM, meshM = to5186g(wall), to5186g(mesh)
hl = list(shapely.line_merge(meshM).geoms)
junc = [Point(c) for l in to5186g(outside).geoms for c in (l.coords[0], l.coords[-1]) if wallM.exterior.distance(Point(c)) < 5]
for st in sets:
    st["join"] = []
    ls = {l["id"]: to5186g(LineString(l["coords"])) for l in st["lines"]}
    for k, g in ls.items():
        others = unary_union([v for kk, v in ls.items() if kk != k])
        for c in (g.coords[0], g.coords[-1]):
            p = Point(c)
            if others.distance(p) < 30 or wallM.exterior.distance(p) < 150: continue
            cand = [(l.distance(p), l, j) for l in hl for j in junc if l.distance(p) < 60 and l.distance(j) < 5]
            if not cand: print("잇지 못함", st["map"], k); continue
            _, l, j = min(cand, key=lambda t: (t[0], t[2].distance(p)))
            a, b = sorted((l.project(p), l.project(j)))
            seg = to4326g(substring(l, a, b))
            st["join"].append({"id": k, "between": list(NAMES[k]), "m": round(substring(l, a, b).length), "coords": [[round(x, 6), round(y, 6)] for x, y in seg.coords]})
    print(st["map"], "잇는 조각", [(j["id"], j["m"]) for j in st["join"]])

json.dump({"sets": sets, "hgisOutside": rnd(outside)}, open(os.path.join(DATA, "seogye.json"), "w"), ensure_ascii=False, separators=(",", ":"))

# 견주기: 1903 선 대 1907 선, 각 선 대 HGIS 1910년 5부 선(선 위 10m마다 가장 가까운 상대 선까지 거리)
to5186 = lambda c: LineString(np.array(T.transform(*np.array(c).T)).T)
mesh5186 = shapely.transform(mesh, lambda c: np.array(T.transform(c[:, 0], c[:, 1])).T)
other = {s["map"]: unary_union([to5186(l["coords"]) for l in s["lines"]]) for s in sets}
def stat(g, target):
    d = np.array([target.distance(g.interpolate(t)) for t in np.arange(0, g.length, 10)])
    return f"중앙값 {np.median(d):.0f}m·최대 {d.max():.0f}m"
for s in sets:
    o = "1907" if s["map"] == "1903" else "1903"
    for l in s["lines"]:
        g = to5186(l["coords"])
        print(f'{s["map"]} {l["id"]:13s} {"·".join(l["between"])} {g.length/1000:.2f}km  HGIS까지 {stat(g, mesh5186)}  {o} 선까지 {stat(g, other[o])}')
print("seogye.json", os.path.getsize(os.path.join(DATA, "seogye.json")), "bytes")
