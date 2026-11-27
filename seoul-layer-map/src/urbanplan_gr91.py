"""1991판 『서울 도시계획 연혁』의 「토지구획정리사업」 연혁도(89.12 말 현재)에서 지구 50곳의 경계를 다시 그린다(시안).
python3 src/urbanplan_gr91.py [--check] → data/urbanplan_gr91.json, RAW/build/urbanplan_gr91_report.json, RAW/build/urbanplan_gr91_check.jpg

- 원자료: 서울도시공간포털 「서울의 변화 > 연혁집」에서 받은 1991image.zip의 HS_UB600GR_89_91AS.jpg(8529×6196).
  RAW/urbanplan/img91/에 풀어 둔다. 그림을 지도에 깔지 않고, 색칠된 면의 경계만 다시 그려 고시 번호·날짜와 함께 싣는다.
- 좌표 맞추기: 그림의 붉은 시 경계선(뼈대 1px)을 지금 서울 경계(data/emd_topo.json 법정동을 합친 것, EPSG:5186)에
  가장 가까운 점끼리 짝지어 아핀 변환(평행이동·회전·축척·기울임)으로 맞춘다(ICP). 2·3차 다항식은 구역을 하나씩 빼고 맞춰
  본 어긋남이 오히려 커서 쓰지 않는다. 검사: 그림의 5·10·15km 동심원 중심과 반지름, 한강 다리 15곳(OSM, --check).
- 면 뽑기: 빨강(60년대 이전)·노랑(60년대)·파랑(70년대)·연두(80년대) 색으로 나누고, 바탕 지도의 검은 글자·선과
  번호 글자(붉은 얇은 획)는 둘레 색으로 메운다. 9px 원으로 열기(opening)를 해서 시 경계선 같은 얇은 붉은 선을 지운다.
- 나누기: 같은 색 지구가 맞붙어 칠해진 곳은 9px 원으로 깎아 잘록한 곳에서 떨어지면 나누고(분수령), 그래도 붙어 있는 곳은
  CUTS의 자름선으로 자른다. 자름선은 1977판 「토지구획정리사업 현황」(HS_UB600GR_65_77AS.jpg, 지구마다 붉은 테두리가
  그려져 있음)을 1991판 좌표로 옮겨 겹쳐 보고 그 테두리를 따라 그었거나, 1991판에 남은 흰 틈을 따라 그었다.
- 번호 잇기: SEEDS의 점(1991판 픽셀, 번호 글자 근처의 면 안)이 든 조각에 그 번호를 붙인다. 한 조각에 번호가 여럿이면
  그림에서 나눌 수 없는 묶음으로 남긴다(3·4·7, 25·26, 39·46). 40 영동2추가는 29 영동2 안에 번호만 있어 면이 없다.
  24 화곡은 색이 없고 25·26 고리 안 빈 곳에 번호만 있어, 그 빈 곳을 면으로 삼는다(크기가 표의 2.5배라 참고용).
"""
import json, os, re, sys
sys.dont_write_bytecode = True
import numpy as np
import cv2
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from skimage.morphology import skeletonize
from skimage.segmentation import watershed
from shapely.geometry import Polygon, MultiPolygon, Point, mapping
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely import affinity
from shapely.ops import transform as stf
from pyproj import Transformer
from paths import DATA, RAW, WORK

SRC = os.path.join(RAW, "urbanplan", "img91", "HS_UB600GR_89_91AS.jpg")
OUT = os.path.join(DATA, "urbanplan_gr91.json")
REPORT = os.path.join(WORK, "urbanplan_gr91_report.json")
TOPO = os.path.join(DATA, "emd_topo.json")
MAPFRAME = (180, 560, 5640, 6000)   # 지도 칸(px). 오른쪽 표·범례 칸은 뺀다
COLORS = {1: "red", 2: "yellow", 3: "blue", 4: "green"}
ERA_COLOR = {"60년대 이전": "red", "60년대": "yellow", "70년대": "blue", "80년대": "green"}

# 그림 오른쪽 표(원본 해상도로 읽음). 면적㎡, 고시 칸의 약칭은 표에 적힌 그대로. 〃는 위 칸과 같음
TABLE = """1|번대|1229776|총고22(37.1.19)
2|공덕|897893|〃
3|청량리|1109721|〃
4|사근|1755630|〃
5|한남|411614|〃
6|신당|424184|〃
7|용두|1961123|〃
8|영등포|5256893|총고96(37.2.2)
9|대현|1578076|〃
10|돈암|2327273|〃
11|중앙제1|742898|내고38(52.6.14)
12|중앙제2|589021|내고140(53.8.20)
13|동대문|267057|내고502(60.2.8)
14|불광|1189848|내고554(61.1.11)
15|수유|1393933|〃
16|뚝도|1354041|〃
17|면목|1101473|건고94(62.3.5)
18|성산|2246097|건고256(63.3.8)
19|화양|2110459|건고2402(66.5.10)
20|망우|6450757|〃
21|연희|800129|건고2432(66.5.26)
22|창동|2793064|건고2514(66.7.1)
23|역촌|4344485|건고2515(66.7.1)
24|화곡|1025142|건공226(66.11.24)
25|김포|4706355|건공3008(66.12.28)
26|경인|6918713|〃
27|시흥|5746241|〃
28|영동|12737831|〃
29|영동2|13071858|〃
30|도봉|2661649|〃
31|천호|2621577|〃
32|신림|3420032|〃
33|중곡|3138095|건특단12,359(67.8.10)
34|개봉|959663|건공164(68.5.14)
35|개봉2|1030810|건공24(70.3.11)
36|홍남|556356|건고159(71.3.10)
37|이수|8028277|건공165(71.4.8)
38|신림추가|2006621|건고244(71.5.5)
39|영동1추가|991736|〃
40|영동2추가|85369|〃
41|잠실|11223191|〃
42|화양추가|1522423|건고666(71.11.26)
43|암사|1697094|건고3(75.5.18)
44|장안평|1933063|〃
45|구로|1461602|건고14(77.1.31)
46|이수추가|76608|건고343(79.9.21)
47|강동|363636|건고150(80.5.20)
48|가락|7455066|건고197(80.7.2)
49|개포|6491289|건고113(81.4.11)
50|양재|154664|건고188(83.6.15)"""
AREA_NOTE = {35: "표의 면적 칸 끝자리가 빠져 있어(1,030,81–) 1,030,810으로 둠"}
NAME_NOTE = {36: "지구명 「홍남」은 표 표기 그대로"}

# 자름선(1991판 픽셀). 근거: 77 = 1977판 연혁도의 지구 테두리를 1991판 좌표로 옮겨 따라 그음, 91 = 1991판에 남은 흰 틈·잘록한 곳
CUTS = {
  "14|23":  ([(2080, 2350), (2160, 2343), (2205, 2336), (2250, 2308), (2330, 2276)], "77"),
  "20|17":  ([(4335, 2724), (4390, 2730), (4430, 2760), (4470, 2775), (4520, 2784)], "77"),
  "15|22":  ([(3490, 1935), (3640, 1943), (3790, 1957)], "91"),
  "16|19":  ([(4262, 3390), (4262, 3590)], "91"),
  "41|31":  ([(4788, 3630), (4800, 3790)], "91"),
  "32|38":  ([(2646, 4380), (2676, 4490)], "91"),
  "32|38b": ([(2410, 4385), (2428, 4403), (2470, 4418), (2505, 4432), (2528, 4452), (2570, 4458), (2665, 4466)], "91"),
  "38|39":  ([(3035, 4395), (3035, 4650)], "91"),
}
# 번호마다 면 안의 점(1991판 픽셀). 번호 글자가 면 밖에 찍힌 곳(3·4·7 등)은 가장 가까운 면 안에 둔다
SEEDS = {
 1: [(2290, 4050)], 2: [(2600, 3470)], 3: [(3800, 2800)], 4: [(3900, 3050)], 7: [(3760, 3080)],
 5: [(3220, 3560)], 6: [(3510, 3080)], 8: [(1930, 3680)], 9: [(2480, 3200)], 10: [(3420, 2700)],
 11: [(3280, 3010), (3070, 3020), (3135, 3062), (3265, 3120), (3100, 3135)],
 12: [(2775, 2983), (2970, 3160), (2910, 3240), (2860, 3498)],
 13: [(3560, 2960)], 14: [(2200, 2250)], 23: [(2180, 2600)],
 15: [(3600, 2120)], 22: [(3700, 1800)], 30: [(3800, 1420)],
 16: [(4050, 3440)], 19: [(4380, 3480)], 17: [(4370, 2870)], 20: [(4219, 2140), (4260, 2450), (4300, 2650)],
 18: [(2010, 3210)], 21: [(2350, 3020)], 25: [(1425, 3212)], 26: [(1375, 3755)], 27: [(2020, 4820)],
 28: [(3400, 3976)], 29: [(3858, 3800)], 31: [(5050, 3550)], 41: [(4527, 3972)],
 32: [(2200, 4330)], 38: [(2745, 4500)], 39: [(3046, 4505)], 37: [(3122, 4281)], 46: [(3190, 4433)],
 33: [(4302, 3250)], 34: [(1410, 4470)], 35: [(1350, 4300), (1460, 4320)], 36: [(2290, 2880)],
 42: [(4336, 3622)], 43: [(4956, 3332)], 44: [(4120, 3020)], 45: [(1900, 4180)],
 47: [(4900, 3690)], 48: [(4950, 4150)], 49: [(3870, 4560)], 50: [(3598, 4420), (3610, 4520)],
}
HOLE_SEED = (24, "25·26", (1325, 3478))
NOTES = {
 "3·4·7": "1991판에는 세 지구 사이 경계가 그려져 있지 않아 한 면으로 둠. 세 지구 모두 총고22(37.1.19)",
 "25·26": "1991판에는 두 지구 사이 경계가 그려져 있지 않아 한 면으로 둠. 두 지구 모두 건공3008(66.12.28)",
 "39·46": "1991판에서 두 지구를 나눌 선을 찾지 못함. 46 이수추가(76,608㎡)는 이 면의 일부로 보임(추정)",
 "24": "1991판에 색이 없고 25·26 고리 안 빈 곳에 번호만 있음. 빈 곳 전체를 면으로 삼아 표 면적의 약 2.5배(참고용)",
 "18": "면적이 표의 약 1.8배. 2001판 연혁집이 60년대 시행 지구로 꼽은 「서교」가 1991판 표에는 없어, 같은 노란 면에 함께 칠해졌을 수 있음(추정)",
 "37": "표 면적(8,028,277㎡)에 견주면 1991판의 37번 면이 아주 작음(약 0.13배). 둘레 파란 면(38·39·46)을 더해도 표의 절반이 안 됨. 표 숫자와 그림 중 어느 쪽이 맞는지 확인 못 함",
 "50": "1991판에서 번호는 노란 28 영동 안에 있고, 그 옆 길을 따라 연두 띠가 가늘게 칠해져 있어 그 띠를 면으로 삼음(확신 낮음)",
 "40": "29 영동2 면 안에 번호만 있고 따로 칠한 면이 없음",
}

def parse_table():
    rows, last = [], None
    for line in TABLE.split("\n"):
        no, name, area, ntc = line.split("|")
        no = int(no)
        raw = ntc
        if ntc == "〃": ntc = last
        last = ntc
        m = re.match(r"^(총고|내고|건고|건공|건특단)([\d,]+)\((\d+)\.(\d+)\.(\d+)\)$", ntc)
        yy, mm, dd = int(m.group(3)), int(m.group(4)), int(m.group(5))
        era = "60년대 이전" if no <= 12 else "60년대" if no <= 34 else "70년대" if no <= 46 else "80년대"
        rows.append({"no": no, "name": name, "areaTbl": int(area), "noticeRaw": raw, "notice": ntc,
                     "agency": m.group(1), "noticeNo": m.group(2), "date": f"19{yy:02d}-{mm:02d}-{dd:02d}",
                     "year": 1900 + yy, "eraTbl": era})
    return rows

def load_seoul_boundary():
    t = json.load(open(TOPO))
    sx, sy = t["transform"]["scale"]; tx, ty = t["transform"]["translate"]
    arcs = []
    for a in t["arcs"]:
        a = np.cumsum(np.array(a, float), axis=0); arcs.append(np.c_[a[:, 0]*sx+tx, a[:, 1]*sy+ty])
    def ring(idx):
        pts = []
        for i in idx:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            pts.extend(a.tolist() if not pts else a[1:].tolist())
        return pts
    gs = []
    for g in t["objects"]["seoul_neighborhoods_geo"]["geometries"]:
        polys = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
        gs += [Polygon(ring(p[0]), [ring(r) for r in p[1:]]).buffer(0) for p in polys]
    u = unary_union(gs)
    xy = np.array(u.exterior.coords)
    T = Transformer.from_crs(4326, 5186, always_xy=True)
    xy = np.array(T.transform(xy[:, 0], xy[:, 1])).T
    pts = []
    for a, b in zip(xy[:-1], xy[1:]):
        n = max(1, int(np.hypot(*(b - a)) // 10))
        pts += [a + (b - a) * t for t in np.arange(n) / n]
    return np.array(pts)

def apply(A, p): return p @ A[:, :2].T + A[:, 2]

def fit_affine(img_hsv, tgt):
    """붉은 시 경계선 뼈대를 지금 서울 경계에 ICP로 맞춘다. 반환: 아핀 A(2×3, px→EPSG:5186), 뼈대 점, 잔차"""
    h, s, v = img_hsv[..., 0], img_hsv[..., 1], img_hsv[..., 2]
    im = IMG.astype(np.int16)
    b, g, r = im[..., 0], im[..., 1], im[..., 2]
    red = ((r - g > 55) & (r - b > 35)).astype(np.uint8)
    red[:, MAPFRAME[2]:] = 0
    blob = cv2.morphologyEx(red, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21)))
    blob = cv2.dilate(blob, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    thin = (red & (1 - blob)).astype(bool)
    ys, xs = np.nonzero(skeletonize(thin)); src = np.c_[xs, ys].astype(float)
    tree = cKDTree(tgt)
    sx0, sy0 = src.min(0); sx1, sy1 = src.max(0); tx0, ty0 = tgt.min(0); tx1, ty1 = tgt.max(0)
    k = ((tx1 - tx0) / (sx1 - sx0) + (ty1 - ty0) / (sy1 - sy0)) / 2
    A = np.array([[k, 0, tx0 - k * sx0], [0, -k, ty1 + k * sy0]])
    for thr in [3000]*5 + [1500]*5 + [700]*5 + [300]*8 + [150]*8 + [100]*10:
        d, i = tree.query(apply(A, src)); m = d < thr
        A = np.linalg.lstsq(np.c_[src[m], np.ones(m.sum())], tgt[i[m]], rcond=None)[0].T
    d, _ = tree.query(apply(A, src))
    bnd = src[d < 300]
    # 8개 방향 구역을 하나씩 빼고 맞춰, 뺀 구역의 어긋남(중앙값)을 잰다
    cen = bnd.mean(0); ang = np.arctan2(bnd[:, 1] - cen[1], bnd[:, 0] - cen[0]); cv = []
    for kk in range(8):
        lo = -np.pi + kk * np.pi / 4; te = (ang >= lo) & (ang < lo + np.pi / 4); B = A.copy()
        for thr in [300]*5 + [150]*5 + [100]*8:
            d2, i2 = tree.query(apply(B, bnd[~te])); mm = d2 < thr
            B = np.linalg.lstsq(np.c_[bnd[~te][mm], np.ones(mm.sum())], tgt[i2[mm]], rcond=None)[0].T
        d3, _ = tree.query(apply(B, bnd[te])); cv.append(float(np.median(d3[d3 < 300])))
    d, _ = tree.query(apply(A, bnd)); m = d < 150
    stat = {"boundaryPts": int(len(bnd)), "within150m": round(float(m.mean()), 3),
            "medianM": round(float(np.median(d[m])), 1), "p90M": round(float(np.percentile(d[m], 90)), 1),
            "holdoutMedianM": [round(x) for x in cv],
            "mPerPx": [round(float(np.hypot(A[0, 0], A[1, 0])), 4), round(float(np.hypot(A[0, 1], A[1, 1])), 4)],
            "rotDeg": round(float(np.degrees(np.arctan2(A[1, 0], A[0, 0]))), 3)}
    # 어긋남이 큰 경계 구간(지금 경계와 150m 넘게 떨어진 뼈대 점 무리)
    far = bnd[d > 150]
    if len(far):
        cc = cKDTree(far); groups = []; seen = np.zeros(len(far), bool)
        for j in range(len(far)):
            if seen[j]: continue
            idx = cc.query_ball_point(far[j], 60); stack = list(idx); seen[idx] = True; mem = set(idx)
            while stack:
                q = stack.pop()
                for t in cc.query_ball_point(far[q], 60):
                    if not seen[t]: seen[t] = True; mem.add(t); stack.append(t)
            if len(mem) >= 30:
                pts = far[list(mem)]; ll = Transformer.from_crs(5186, 4326, always_xy=True).transform(*apply(A, pts.mean(0, keepdims=True))[0])
                groups.append({"px": [int(x) for x in pts.mean(0)], "lonlat": [round(ll[0], 4), round(ll[1], 4)], "n": len(mem),
                               "maxM": round(float(tree.query(apply(A, pts))[0].max()))})
        stat["farSegments"] = groups
    return A, stat

def ring_check(A):
    """그림의 5·10·15km 동심원 중심과 반지름을 찾아 맞춘 좌표로 옮긴다(검사용)"""
    from scipy.signal import fftconvolve
    im = IMG.astype(np.int16); b, g, r = im[..., 0], im[..., 1], im[..., 2]
    mx = np.maximum(np.maximum(r, g), b); mn = np.minimum(np.minimum(r, g), b)
    gray = ((mx < 200) & (mx - mn < 40)).astype(np.float32); gray[:, MAPFRAME[2]:] = 0
    s = float(np.hypot(A[0, 0], A[1, 0])); f = 4
    small = cv2.resize(gray, (gray.shape[1] // f, gray.shape[0] // f), interpolation=cv2.INTER_AREA)
    score = np.zeros_like(small)
    for R in (5000, 10000, 15000):
        rp = R / s / f; n = int(rp + 4); yy, xx = np.mgrid[-n:n+1, -n:n+1]
        K = (np.abs(np.hypot(xx, yy) - rp) < 1.0).astype(np.float32); K /= K.sum()
        resp = fftconvolve(small, K, mode="same"); score += (resp - resp.mean()) / resp.std()
    cy, cx = np.unravel_index(np.argmax(score), score.shape)
    ys, xs = np.nonzero(gray); best = None
    for dx in range(-8, 9, 2):
        for dy in range(-8, 9, 2):
            c = np.array([cx * f + dx, cy * f + dy], float); tot = 0; rads = []
            for R in (5000, 10000, 15000):
                rp = R / s; sel = (np.abs(xs - c[0]) < rp + 60) & (np.abs(ys - c[1]) < rp + 60)
                hh, e = np.histogram(np.hypot(xs[sel] - c[0], ys[sel] - c[1]), bins=np.arange(rp - 40, rp + 40, 1.0))
                k = np.argmax(hh); tot += hh[k]; rads.append(float(e[k] + 0.5))
            if best is None or tot > best[0]: best = (tot, c, rads)
    _, c, rads = best
    X = apply(A, c[None])[0]
    ll = Transformer.from_crs(5186, 4326, always_xy=True).transform(*X)
    # 비교: 고종즉위40년 칭경기념비(OSM 노드 좌표). 옛 도로원표가 그 곁에 있었다고 알려져 있음(확인 안 함)
    ref = Transformer.from_crs(4326, 5186, always_xy=True).transform(126.9775146, 37.570483)
    return {"centerPx": [int(c[0]), int(c[1])], "centerLonLat": [round(ll[0], 5), round(ll[1], 5)],
            "distToMonumentM": round(float(np.hypot(X[0] - ref[0], X[1] - ref[1])), 1),
            "ringMPerPx": [round(R / rp, 4) for R, rp in zip((5000, 10000, 15000), rads)]}

BRIDGES = ["성산대교", "양화대교", "당산철교", "서강대교", "마포대교", "원효대교", "한강철교 A선", "한강대교", "동작대교", "반포대교",
           "한남대교", "동호대교", "성수대교", "영동대교", "잠실대교", "잠실철교", "천호대교"]   # 1989년에 있던 한강 다리

def bridge_check(A):
    """--check: 지금 한강 다리(OSM)를 그림 좌표로 옮겨, 다리와 수직 방향으로 그림의 다리 선이 얼마나 비켜 있는지 잰다(m).
    다리 방향(대개 남북)과 나란한 어긋남은 잴 수 없다. RAW/osm/seoul/Seoul.osm.pbf와 pip install osmium이 필요"""
    import osmium
    from shapely.geometry import LineString, shape
    from scipy.ndimage import map_coordinates, gaussian_filter1d
    want = set(BRIDGES); found = {}
    class Hd(osmium.SimpleHandler):
        def way(self, w):
            nm = w.tags.get("name", "")
            if nm in want and (w.tags.get("man_made") == "bridge" or w.tags.get("bridge:name")):
                try: found.setdefault(nm, []).append([(n.lon, n.lat) for n in w.nodes])
                except Exception: pass
    Hd().apply_file(os.path.join(RAW, "osm/seoul/Seoul.osm.pbf"), locations=True)
    T = Transformer.from_crs(4326, 5186, always_xy=True)
    wa = stf(lambda x, y, z=None: T.transform(x, y), shape(json.load(open(os.path.join(DATA, "water.json")))["area"]))
    Ai = np.linalg.inv(np.r_[A, [[0, 0, 1]]])[:2]
    dark = 255 - IMG.astype(np.float32).mean(2); out = []
    for nm in BRIDGES:
        if nm not in found: out.append({"name": nm, "note": "OSM에서 못 찾음"}); continue
        p = np.array(T.transform(*np.array(max(found[nm], key=lambda q: LineString(q).length)).T)).T
        L = LineString(p).intersection(wa)
        if L.is_empty: out.append({"name": nm, "note": "물 위 구간 없음"}); continue
        if L.geom_type != "LineString": L = max(L.geoms, key=lambda g: g.length)
        q = np.array(L.coords); pa, pc = apply(Ai, q[[0, -1]])
        v = pc - pa; u = v / np.hypot(*v); nrm = np.array([-u[1], u[0]]); offs = np.arange(-80, 81, 0.5)
        prof = gaussian_filter1d(np.array([map_coordinates(dark, [(pa + np.outer(np.linspace(.1, .9, 60), v) + o * nrm)[:, 1],
                                                                   (pa + np.outer(np.linspace(.1, .9, 60), v) + o * nrm)[:, 0]], order=1).mean() for o in offs]), 4)
        out.append({"name": nm, "offsetM": round(float(offs[np.argmax(prof)] * np.hypot(A[0, 0], A[1, 0])))})
    return out

def segment(hsv):
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    col = {1: ((h >= 165) | (h <= 8)) & (s > 80) & (v > 100),
           2: (h >= 20) & (h <= 36) & (s > 70) & (v > 120),
           3: (h >= 88) & (h <= 112) & (s > 45) & (v > 100),
           4: (h >= 37) & (h <= 60) & (s > 45) & (v > 100)}
    x0, y0, x1, y1 = MAPFRAME
    inframe = np.zeros(h.shape, bool); inframe[y0:y1, x0:x1] = True
    unk = (v < 170) & ~np.any(list(col.values()), axis=0)
    lab = np.zeros(h.shape, np.int8)
    k9 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    for k, m in col.items():
        m = (m & inframe).astype(np.uint8)
        op = cv2.morphologyEx(m, cv2.MORPH_OPEN, k9).astype(bool)
        lab[op] = k; unk |= (m.astype(bool) & ~op)
    unk &= (lab == 0)
    idx = ndi.distance_transform_edt(unk, return_distances=False, return_indices=True)
    lab = lab[idx[0], idx[1]]; lab[~inframe] = 0
    return lab

def split_pieces(lab):
    H, W = lab.shape
    work = np.zeros((H, W), np.int32); pieces = []; k = 0
    for col in (1, 2, 3, 4):
        m = (lab == col).astype(np.uint8)
        hol = ndi.binary_fill_holes(m) & ~m.astype(bool)          # 번호 동그라미 같은 작은 구멍은 메운다
        hc, hn = ndi.label(hol); hs = ndi.sum(hol, hc, range(1, hn + 1))
        m[np.isin(hc, [t + 1 for t, v in enumerate(hs) if v < 5000])] = 1
        for pl, _ in CUTS.values():
            cv2.polylines(m, [np.array(pl, np.int32)], False, 0, 3)
        cc, n = ndi.label(m)
        sizes = ndi.sum(m, cc, range(1, n + 1))
        for i, sz in enumerate(sizes, 1):
            if sz < 400: continue
            sl = ndi.find_objects((cc == i).astype(np.int8))[0]
            y0, y1 = max(0, sl[0].start - 2), sl[0].stop + 2; x0, x1 = max(0, sl[1].start - 2), sl[1].stop + 2
            sub = cc[y0:y1, x0:x1] == i
            e = cv2.erode(sub.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
            ec, en = ndi.label(e); es = ndi.sum(e, ec, range(1, en + 1))
            mk = np.zeros_like(ec); j = 0
            for t, s2 in enumerate(es, 1):
                if s2 > 300: j += 1; mk[ec == t] = j
            parts = sub.astype(np.int32) if j <= 1 else watershed(-ndi.distance_transform_edt(sub), mk, mask=sub)
            for t in range(1, parts.max() + 1):
                pm = parts == t
                if pm.sum() < 200: continue
                k += 1; work[y0:y1, x0:x1][pm] = k
                pieces.append({"pid": k, "color": col, "px": int(pm.sum())})
    owner = {}
    for no, pts in SEEDS.items():
        for (x, y) in pts:
            p = int(work[y, x])
            if p == 0:
                win = work[max(0, y - 60):y + 60, max(0, x - 60):x + 60]; yy, xx = np.nonzero(win)
                if not len(yy): print("씨앗이 면 밖에 있음", no, (x, y), file=sys.stderr); continue
                q = np.argmin(np.hypot(xx + max(0, x - 60) - x, yy + max(0, y - 60) - y))
                p = int(work[yy[q] + max(0, y - 60), xx[q] + max(0, x - 60)])
            owner.setdefault(p, set()).add(no)
    for pc in pieces: pc["nos"] = sorted(owner.get(pc["pid"], []))
    kern = np.ones((3, 3), np.uint8)
    for pc in pieces:   # 번호 없는 조각은 같은 색으로 가장 길게 맞닿은 조각에 붙이고, 없으면 버린다(시 경계선 토막 등)
        if pc["nos"]: continue
        m = (work == pc["pid"]).astype(np.uint8)
        ring = cv2.dilate(m, kern, iterations=2).astype(bool) & ~m.astype(bool)
        nb = work[ring]; nb = nb[(nb > 0) & (nb != pc["pid"])]
        cand = [(int(np.sum(nb == q)), int(q)) for q in np.unique(nb) if pieces[q - 1]["color"] == pc["color"] and pieces[q - 1]["nos"]]
        if cand:
            q = max(cand)[1]; work[work == pc["pid"]] = q; pieces[q - 1]["px"] += pc["px"]; pc["mergedInto"] = q
        else:
            pc["dropped"] = True; work[work == pc["pid"]] = 0
    return work, pieces

def mask_polys(m):
    cn, hier = cv2.findContours(m.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    if hier is None: return out
    hier = hier[0]
    for i, c in enumerate(cn):
        if hier[i][3] != -1 or len(c) < 4: continue
        holes = []; j = hier[i][2]
        while j != -1:
            if len(cn[j]) >= 4: holes.append(cn[j][:, 0, :] + 0.5)
            j = hier[j][0]
        p = Polygon(cn[i][:, 0, :] + 0.5, holes).buffer(0)
        if p.area > 50: out.append(p)
    return out

def label_point(m):
    """면 안에서 가장자리에서 가장 먼 점(px). 지구 이름 글자 자리 후보"""
    d = cv2.distanceTransform(m.astype(np.uint8), cv2.DIST_L2, 5)
    y, x = np.unravel_index(np.argmax(d), d.shape); return float(x), float(y)

def main():
    global IMG
    IMG = cv2.imread(SRC)
    if IMG is None: sys.exit(f"원자료가 없음: {SRC}")
    hsv = cv2.cvtColor(IMG, cv2.COLOR_BGR2HSV)
    tgt = load_seoul_boundary()
    A, fit = fit_affine(hsv, tgt)
    fit["rings"] = ring_check(A)
    if "--check" in sys.argv: fit["bridges"] = bridge_check(A)
    print("맞춤", json.dumps(fit, ensure_ascii=False), file=sys.stderr)
    lab = segment(hsv)
    work, pieces = split_pieces(lab)
    rows = {r["no"]: r for r in parse_table()}
    to_ll = Transformer.from_crs(5186, 4326, always_xy=True)
    units = {}
    for pc in pieces:
        if not pc["nos"] or pc.get("dropped") or pc.get("mergedInto"): continue
        key = "·".join(map(str, pc["nos"]))
        units.setdefault(key, {"pids": [], "colors": set()})
        units[key]["pids"].append(pc["pid"]); units[key]["colors"].add(COLORS[pc["color"]])
    masks = {k: np.isin(work, u["pids"]) for k, u in units.items()}
    hn, hkey, (hx, hy) = HOLE_SEED
    cl = cv2.morphologyEx(masks[hkey].astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41)))
    hole = ndi.binary_fill_holes(cl) & ~cl.astype(bool); hc, _ = ndi.label(hole)
    if hc[hy, hx]:
        masks[str(hn)] = (hc == hc[hy, hx]) & ~masks[hkey]; units[str(hn)] = {"pids": [], "colors": {"none"}}
    feats = []
    for key, m in masks.items():
        g = unary_union(mask_polys(m)).simplify(1.5)
        gm = affinity.affine_transform(g, [A[0, 0], A[0, 1], A[1, 0], A[1, 1], A[0, 2], A[1, 2]])
        gl = stf(lambda x, y, z=None: to_ll.transform(x, y), gm)
        gl = MultiPolygon([gl]) if gl.geom_type == "Polygon" else gl
        gl = MultiPolygon([orient(q, sign=-1.0) for q in gl.geoms])   # d3-geo는 바깥 고리가 시계 방향이어야 면 안쪽으로 읽는다
        lx, ly = label_point(m); ll = to_ll.transform(*apply(A, np.array([[lx, ly]]))[0])
        nos = [int(x) for x in key.split("·")]
        at = sum(rows[n]["areaTbl"] for n in nos)
        drawn = sorted(units[key]["colors"])
        feats.append({"key": key, "nos": nos, "names": [rows[n]["name"] for n in nos],
                      "year": min(rows[n]["year"] for n in nos), "date": min(rows[n]["date"] for n in nos),
                      "drawn": drawn[0] if len(drawn) == 1 else drawn,
                      "colorMatchesTable": all(ERA_COLOR[rows[n]["eraTbl"]] in drawn for n in nos) if "none" not in drawn else None,
                      "areaTbl": at, "areaDrawn": round(gm.area), "ratio": round(gm.area / at, 2),
                      "lab": [round(ll[0], 5), round(ll[1], 5)],
                      "note": NOTES.get(key, ""),
                      "geom": json.loads(json.dumps(mapping(gl), default=float))})
    for f in feats:  # 좌표를 소수 다섯째 자리로
        f["geom"]["coordinates"] = [[[[round(x, 5), round(y, 5)] for x, y in ring] for ring in poly] for poly in f["geom"]["coordinates"]]
    feats.sort(key=lambda f: f["nos"][0])
    have = {n for f in feats for n in f["nos"]}
    table = []
    for n, r in rows.items():
        r = dict(r); r["feature"] = next((f["key"] for f in feats if n in f["nos"]), None)
        if n in AREA_NOTE: r["areaNote"] = AREA_NOTE[n]
        if n in NAME_NOTE: r["nameNote"] = NAME_NOTE[n]
        if n not in have: r["note"] = NOTES.get(str(n), "")
        table.append(r)
    out = {"id": "gr91", "title": "토지구획정리사업(89.12 말 현재)",
           "src": "서울특별시, 『서울 도시계획 연혁』(1991) 연혁도 「토지구획정리사업」(HS_UB600GR_89_91AS)",
           "method": "연혁도의 색칠된 면 경계를 다시 그림. 그림은 싣지 않음",
           "fit": {"A": [[round(x, 6) for x in row] for row in A.tolist()], "crs": "EPSG:5186", **fit},
           "cuts": {k: {"px": v[0], "basis": v[1]} for k, v in CUTS.items()},
           "features": feats, "table": table}
    json.dump(out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    os.makedirs(WORK, exist_ok=True)
    json.dump({"fit": fit, "pieces": pieces, "features": [{k: v for k, v in f.items() if k != "geom"} for f in feats]},
              open(REPORT, "w"), ensure_ascii=False, indent=1)
    # 확인 그림: 원본 위에 뽑은 면 테두리와 번호
    ov = IMG.copy()
    for f in feats:
        m = masks[f["key"]].astype(np.uint8)
        cn, _ = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(ov, cn, -1, (0, 0, 0), 3)
        lx, ly = label_point(m)
        cv2.putText(ov, f["key"], (int(lx) - 25, int(ly) + 10), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 6)
        cv2.putText(ov, f["key"], (int(lx) - 25, int(ly) + 10), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 2)
    for pl, _ in CUTS.values():
        cv2.polylines(ov, [np.array(pl, np.int32)], False, (255, 0, 255), 4)
    cv2.imwrite(os.path.join(WORK, "urbanplan_gr91_check.jpg"), ov, [cv2.IMWRITE_JPEG_QUALITY, 82])
    print(f"{len(feats)}개 면, {len(have)}개 번호 → {OUT}", file=sys.stderr)
    for f in feats:
        print(f["key"], "·".join(f["names"]), f["year"], f["drawn"], f["areaTbl"], f["areaDrawn"], f["ratio"], file=sys.stderr)

if __name__ == "__main__":
    main()
