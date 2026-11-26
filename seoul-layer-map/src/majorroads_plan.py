"""큰 도로 레이어(시안) 1단계: 『서울 도시계획 연혁』 도로 연혁도에 지금의 큰 도로가 광로·대로로 그려져 있는지 잰다.

python3 src/majorroads_plan.py   → data/majorroads_plan.json, RAW/build/majorroads_plan_report.json
python3 src/majorroads_plan.py --reuse   맞춤은 지난 보고서 것을 그대로 쓰고 링크 대조만 다시

원자료(이지의 다운로드 폴더에서 옮김)
- RAW/urbanplan/img77/  1977image.zip을 푼 것(HS_UB500RD_{27,36,52,62,65,66,71,72,76}_77LN.jpg)
- RAW/urbanplan/img91/  1991image.zip을 푼 것(HS_UB500RDB·RDU_{82,89}_91LN.jpg, 좌표 기준인 HS_UB600GR_89_91AS.jpg)
- RAW/nodelink/seoul_links.json  majorroads.py --links 가 국가교통정보센터 표준노드링크에서 서울 링크만 뽑은 것

연혁도마다 그린 것(그림 제목을 읽어 옮김)
- 1936 「京城市街地計劃街路」 조선총독부고시 제772호(1936.12.26)
- 1952 「서울都市計劃街路修正」 내무부고시 제23호(1952.3.25)
- 1962 「서울都市計劃街路再整備」 건설부고시 제177호(1962.12.8)
- 1965 「計劃街路의 現況」(1965년 9월 말 현재)
- 1966 「서울都市計劃街路再整備」 건설부고시 제2493호(1966.6.21)
- 1971 「서울都市計劃街路再整備」 건설부고시 제198호(1971.4.7)
- 1972 「서울都市計劃街路再整備」 건설부고시 제524호(1972.12.8)
- 1976 「서울都市計劃街路現況」(1976.12.31 현재)
- 1982·1989 1991판 「都市計劃街路(大路)」·「(廣路)」(1989판은 89.12 말 현재)
1927 「市區改正路線」은 붉은 선이 너비가 아니라 시행 주체를 가르므로 쓰지 않는다.
1977판 범례(1962·1976)에서 붉은 선은 광로·대로(너비 25m 이상), 초록 선은 중로다. 1991판은 대로·광로 그림 두 장을 합친다.

좌표 맞추기(연혁도 그림을 지도에 깔지 않고, 지금 도로를 그림 위로 옮겨 재는 데만 씀)
- 1991판: 토지구획정리 그림(GR_89)의 붉은 시 경계선을 지금 서울 경계에 ICP로 맞춘 뒤(도시계획 갈래와 같은 방법),
  같은 바탕 지도인 도로 그림을 SIFT로 GR_89에 맞춘다.
- 1977판 1965–1976 묶음: 1976 그림의 붉은 선(시 경계+광로·대로) 뼈대를 지금 서울 경계+표준노드링크 큰 도로에
  거리변환 위 닮음변환 탐색(양방향 거리)으로 맞추고 아핀 ICP로 다듬는다. 나머지 장은 SIFT로 1976 장에 맞춘다.
- 1977판 1936–1962 묶음(1:50,000, 바탕 지도가 다름): 1962 그림의 붉은 선을 지금 큰 도로에 맞추고 나머지는 SIFT로.
대조
- 표준노드링크 큰 도로 링크(majorroads.py가 고르는 것과 같음)를 25m마다 점으로 나눠 그림 위로 옮기고,
  TOL(70m) 안에 붉은 선이 있으면 그 점은 「그려져 있음」. 링크 점의 60% 넘게 그려져 있으면 그 해 연혁도에 있는 것으로 본다.
- 그 무렵 시 경계선(붉은 선)은 지운다: 1936·1949·1963 시역은 data/years.json의 동별 편입 연도로 합친 경계, 1976 뒤는 지금 경계.
  도시계획구역선(1936·1962 그림의 점선 등)은 지우지 못해, 그 선을 따라가는 길은 잘못 잡힐 수 있다.
"""
import json, os, sys
sys.dont_write_bytecode = True
import numpy as np
import cv2
from scipy.spatial import cKDTree
from scipy import optimize
from skimage.morphology import skeletonize
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union
from pyproj import Transformer
from paths import DATA, RAW, WORK

IMG77 = os.path.join(RAW, "urbanplan", "img77")
IMG91 = os.path.join(RAW, "urbanplan", "img91")
LINKS = os.path.join(RAW, "nodelink", "seoul_links.json")
OUT = os.path.join(DATA, "majorroads_plan.json")
REPORT = os.path.join(WORK, "majorroads_plan_report.json")
TOL = 70.0
T4326 = Transformer.from_crs(4326, 5186, always_xy=True)
SHEETS = [  # (해, 판, 그림 이름들, 지울 시 경계의 해, 제목)
    (1936, "77", ["HS_UB500RD_36_77LN"], 1936, "京城市街地計劃街路(조선총독부고시 제772호, 1936.12.26)"),
    (1952, "77", ["HS_UB500RD_52_77LN"], 1949, "서울都市計劃街路修正(내무부고시 제23호, 1952.3.25)"),
    (1962, "77", ["HS_UB500RD_62_77LN"], 1949, "서울都市計劃街路再整備(건설부고시 제177호, 1962.12.8)"),
    (1965, "77", ["HS_UB500RD_65_77LN"], 1963, "計劃街路의 現況(1965년 9월 말 현재)"),
    (1966, "77", ["HS_UB500RD_66_77LN"], 1963, "서울都市計劃街路再整備(건설부고시 제2493호, 1966.6.21)"),
    (1971, "77", ["HS_UB500RD_71_77LN"], 1963, "서울都市計劃街路再整備(건설부고시 제198호, 1971.4.7)"),
    (1972, "77", ["HS_UB500RD_72_77LN"], 1963, "서울都市計劃街路再整備(건설부고시 제524호, 1972.12.8)"),
    (1976, "77", ["HS_UB500RD_76_77LN"], 2026, "서울都市計劃街路現況(1976.12.31 현재)"),
    (1982, "91", ["HS_UB500RDB_82_91LN", "HS_UB500RDU_82_91LN"], 2026, "都市計劃街路 大路·廣路(1982)"),
    (1989, "91", ["HS_UB500RDB_89_91LN", "HS_UB500RDU_89_91LN"], 2026, "都市計劃街路 大路·廣路(89.12 말 현재)"),
]


def apply(A, p): return p @ A[:, :2].T + A[:, 2]


def _gu_names():
    src = open(os.path.join(os.path.dirname(__file__), "build.py"), encoding="utf-8").read()
    s0 = src.index("GU = {"); return eval(src[s0 + 5: src.index("}", s0) + 1])


def era_polygon(year):
    """그 해 시역(5186). year >= 2026이면 지금 서울."""
    gu = _gu_names(); years = json.load(open(os.path.join(DATA, "years.json")))
    t = json.load(open(os.path.join(DATA, "emd_topo.json"))); sx, sy = t["transform"]["scale"]; tx, ty = t["transform"]["translate"]
    arcs = []
    for a in t["arcs"]:
        a = np.cumsum(np.array(a, float), axis=0); x, y = T4326.transform(a[:, 0] * sx + tx, a[:, 1] * sy + ty); arcs.append(np.c_[x, y])
    def ring(idx):
        pts = []
        for i in idx:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]; pts.extend(a.tolist() if not pts else a[1:].tolist())
        return pts
    gs = []
    for g in t["objects"]["seoul_neighborhoods_geo"]["geometries"]:
        p = g["properties"]
        if years.get(f"{gu[p['gu']]}/{p['nm']}", {}).get("y", 1914) > year: continue
        for q in ([g["arcs"]] if g["type"] == "Polygon" else g["arcs"]):
            gs.append(Polygon(ring(q[0]), [ring(r) for r in q[1:]]).buffer(0))
    return unary_union(gs).buffer(30).buffer(-30)


def densify(xy, step=10):
    pts = []
    for a, b in zip(xy[:-1], xy[1:]):
        n = max(1, int(np.hypot(*(b - a)) // step)); pts += [a + (b - a) * t for t in np.arange(n) / n]
    return np.array(pts)


def boundary_pts(year=2026):
    u = era_polygon(year); geoms = getattr(u, "geoms", [u])
    return np.vstack([densify(np.array(g.exterior.coords)) for g in geoms])


def big_links():
    """majorroads.py의 select_links()와 같은 링크(고속·도시고속, 주간선, 보조간선, 왕복 6차로 이상)."""
    from majorroads import select_links
    return select_links()


def road_pts(lanes_min=2):
    L = json.load(open(LINKS)); pts = []
    for l in L:
        if l["ROAD_RANK"] in ("101", "102", "103", "104") and l["LANES"] >= lanes_min and l["ROAD_USE"] == "0":
            pts.append(densify(np.array(l["pts"]), 20))
    return np.vstack(pts)


def red_mask(path, ed):
    I = cv2.imread(path)
    if I is None: sys.exit(f"원자료가 없음: {path}")
    I = I.astype(np.int16); b, g, r = I[..., 0], I[..., 1], I[..., 2]
    m = ((r - g > 60) & (r - b > 40)) if ed == "77" else ((r - g > 50) & (r - b > 10))
    m = m.astype(np.uint8)
    if ed == "91": m[:, int(m.shape[1] * 0.68):] = 0   # 오른쪽 범례 칸
    return m


def skel(m, boxes=()):
    m = m.copy(); W = m.shape[1]; s = W / 1600
    for (x0, y0, x1, y1) in boxes: m[int(y0 * s):int(y1 * s), int(x0 * s):int(x1 * s)] = 0
    ys, xs = np.nonzero(skeletonize(m.astype(bool))); return np.c_[xs, ys].astype(float)


def icp(A, src, tgt, thrs):
    tree = cKDTree(tgt)
    for thr in thrs:
        d, i = tree.query(apply(A, src)); m = d < thr
        A = np.linalg.lstsq(np.c_[src[m], np.ones(m.sum())], tgt[i[m]], rcond=None)[0].T
    d, _ = tree.query(apply(A, src)); m = d < 150
    return A, {"near150": round(float(m.mean()), 3), "medianM": round(float(np.median(d[m])), 1), "p90M": round(float(np.percentile(d[m], 90)), 1),
               "mPerPx": [round(float(np.hypot(A[0, 0], A[1, 0])), 3), round(float(np.hypot(A[0, 1], A[1, 1])), 3)],
               "rotDeg": round(float(np.degrees(np.arctan2(A[1, 0], A[0, 0]))), 2)}


def chamfer(src, tgt, k_lo, k_hi, cx, cy, both=None, trunc=600, search=1500, res=40.0, rot=3):
    """닮음변환(축척·회전·이동)을 거리변환 위에서 찾는다. both가 있으면 그 점들에서 src까지의 거리도 더한다(줄어드는 쪽으로 쏠리지 않게)."""
    x0, y0 = tgt.min(0) - 4000; x1, y1 = tgt.max(0) + 4000; nx, ny = int((x1 - x0) / res), int((y1 - y0) / res)
    img = np.full((ny, nx), 255, np.uint8); ij = ((tgt - [x0, y0]) / res).astype(int); img[ny - 1 - ij[:, 1], ij[:, 0]] = 0
    dt = cv2.distanceTransform(img, cv2.DIST_L2, 5) * res
    sub = src[np.random.default_rng(0).choice(len(src), min(15000, len(src)), replace=False)]; sc = sub.mean(0)
    def tf(P):
        k, th, tx, ty = P; c, s = np.cos(th), np.sin(th); q = sub - sc
        return k * (c * q[:, 0] + s * q[:, 1]) + tx, k * (s * q[:, 0] - c * q[:, 1]) + ty
    def cost(P):
        X, Y = tf(P); i = ((X - x0) / res).astype(int); j = ny - 1 - ((Y - y0) / res).astype(int)
        ok = (i >= 0) & (i < nx) & (j >= 0) & (j < ny); d = np.full(len(X), float(trunc)); d[ok] = dt[j[ok], i[ok]]
        c = np.minimum(d, trunc).mean()
        if both is not None: c += np.minimum(cKDTree(np.c_[X, Y]).query(both)[0], trunc).mean()
        return c
    cands = []
    for k in np.linspace(k_lo, k_hi, 9):
        for th in np.radians(np.arange(-rot, rot + 0.1, 1.0)):
            for dx in range(-2 * search, 2 * search + 1, search):
                for dy in range(-2 * search, 2 * search + 1, search):
                    P = [k, th, cx + dx, cy + dy]; cands.append((cost(P), P))
    cands.sort(key=lambda t: t[0]); best = None
    for _, P in cands[:6]:
        r = optimize.minimize(cost, P, method="Powell", bounds=[(k_lo, k_hi), (-0.1, 0.1), (P[2] - search, P[2] + search), (P[3] - search, P[3] + search)])
        if best is None or r.fun < best.fun: best = r
    k, th, tx, ty = best.x; c, s = np.cos(th), np.sin(th)
    A = np.array([[k * c, k * s, 0.0], [k * s, -k * c, 0.0]]); A[:, 2] = [tx, ty] - A[:, :2] @ sc
    return A, round(float(best.fun), 1)


def sift_to(ref_path, A_ref, paths, F=0.5):
    sift = cv2.SIFT_create(nfeatures=60000); fl = cv2.FlannBasedMatcher(dict(algorithm=1, trees=5), dict(checks=64))
    g = lambda p: cv2.resize(cv2.imread(p, cv2.IMREAD_GRAYSCALE), None, fx=F, fy=F, interpolation=cv2.INTER_AREA)
    k0, d0 = sift.detectAndCompute(g(ref_path), None); out = {}
    for p in paths:
        k1, d1 = sift.detectAndCompute(g(p), None)
        good = [a for a, b in fl.knnMatch(d1, d0, k=2) if a.distance < 0.75 * b.distance]
        p1 = np.float32([k1[a.queryIdx].pt for a in good]) / F; p0 = np.float32([k0[a.trainIdx].pt for a in good]) / F
        H, inl = cv2.estimateAffine2D(p1, p0, ransacReprojThreshold=6, maxIters=20000, confidence=0.999); inl = inl.ravel().astype(bool)
        res = np.linalg.norm(apply(H, p1[inl]) - p0[inl], axis=1)
        A = (np.vstack([A_ref, [0, 0, 1]]) @ np.vstack([H, [0, 0, 1]]))[:2]
        out[os.path.basename(p)[:-4]] = (A, {"siftInliers": int(inl.sum()), "residPxMed": round(float(np.median(res)), 2), "residPx90": round(float(np.percentile(res, 90)), 2)})
    return out


def register():
    rep, aff = {}, {}
    Bd = boundary_pts(); R = road_pts()
    # 1991판: GR_89 시 경계 ICP → 도로 그림 SIFT
    gr = os.path.join(IMG91, "HS_UB600GR_89_91AS.jpg"); I = cv2.imread(gr).astype(np.int16)
    red = ((I[..., 2] - I[..., 1] > 55) & (I[..., 2] - I[..., 0] > 35)).astype(np.uint8); red[:, 5640:] = 0   # 지도 칸 오른쪽 표는 뺌
    blob = cv2.dilate(cv2.morphologyEx(red, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    thin = (red & (1 - blob)).astype(bool)   # 칠한 지구 면은 빼고 얇은 시 경계선만
    ys, xs = np.nonzero(skeletonize(thin)); src = np.c_[xs, ys].astype(float)
    sx0, sy0 = src.min(0); sx1, sy1 = src.max(0); tx0, ty0 = Bd.min(0); tx1, ty1 = Bd.max(0)
    k = ((tx1 - tx0) / (sx1 - sx0) + (ty1 - ty0) / (sy1 - sy0)) / 2
    A = np.array([[k, 0, tx0 - k * sx0], [0, -k, ty1 + k * sy0]])
    A, st = icp(A, src, Bd, [3000] * 5 + [1500] * 5 + [700] * 5 + [300] * 8 + [150] * 8 + [100] * 10)
    rep["HS_UB600GR_89_91AS"] = st; aff["HS_UB600GR_89_91AS"] = A
    for nm, (A2, st2) in sift_to(gr, A, [os.path.join(IMG91, f"{n}.jpg") for n in
                                       ["HS_UB500RDB_82_91LN", "HS_UB500RDU_82_91LN", "HS_UB500RDB_89_91LN", "HS_UB500RDU_89_91LN"]]).items():
        aff[nm] = A2; rep[nm] = st2
    # 1977판 1965–1976: 1976 장을 경계+큰 도로에 맞춤
    p76 = os.path.join(IMG77, "HS_UB500RD_76_77LN.jpg")
    src = skel(red_mask(p76, "77"), [(1115, 1000, 1305, 1180), (270, 150, 630, 230), (1290, 0, 1600, 1600), (0, 0, 95, 1600)])
    k0 = (Bd[:, 0].max() - Bd[:, 0].min()) / (np.percentile(src[:, 0], 99.5) - np.percentile(src[:, 0], 0.5))
    A, c = chamfer(src, np.vstack([R, Bd]), k0 * 0.85, k0 * 1.15, *Bd.mean(0), both=Bd[::5])
    A, st = icp(A, src, np.vstack([R, Bd]), [300] * 6 + [150] * 8 + [80] * 10); st["chamfer"] = c
    rep["HS_UB500RD_76_77LN"] = st; aff["HS_UB500RD_76_77LN"] = A
    for nm, (A2, st2) in sift_to(p76, A, [os.path.join(IMG77, f"HS_UB500RD_{y}_77LN.jpg") for y in ("65", "66", "71", "72")]).items():
        aff[nm] = A2; rep[nm] = st2
    # 1977판 1936–1962(1:50,000, 바탕 지도가 다름): 1962 장의 붉은 선을 이미 맞춘 1966 장의 붉은 선(4년 뒤 계획선)에 맞춘다.
    # 지금 큰 도로에 바로 맞추면 아직 뚫리지 않은 계획선 때문에 축척이 어긋난 자리에서 멈췄다(5.0 m/px 경계, 2026-11-26 시험).
    p62 = os.path.join(IMG77, "HS_UB500RD_62_77LN.jpg")
    src = skel(red_mask(p62, "77"), [(1034, 846, 1406, 1200), (0, 0, 1600, 80)])
    T66 = apply(aff["HS_UB500RD_66_77LN"], skel(red_mask(os.path.join(IMG77, "HS_UB500RD_66_77LN.jpg"), "77"), [(970, 900, 1150, 1120), (270, 150, 700, 230)]))
    cx, cy = apply(aff["HS_UB500RD_76_77LN"], np.array([[2474.0, 2270.0]]))[0]
    A, c = chamfer(src, T66, 3.5, 6.5, cx, cy, trunc=400, search=1000, rot=4)
    A, st = icp(A, src, T66, [250] * 6 + [150] * 8 + [80] * 10); st["chamfer"] = c
    d, _ = cKDTree(R).query(apply(A, src)); mm = d < 150
    st["vsRoadsNear150"] = round(float(mm.mean()), 3); st["vsRoadsMedianM"] = round(float(np.median(d[mm])), 1)
    rep["HS_UB500RD_62_77LN"] = st; aff["HS_UB500RD_62_77LN"] = A
    for nm, (A2, st2) in sift_to(p62, A, [os.path.join(IMG77, f"HS_UB500RD_{y}_77LN.jpg") for y in ("36", "52")]).items():
        aff[nm] = A2; rep[nm] = st2
    return aff, rep


def sheet_mask(names, ed, by, aff, bnd_cache):
    M = None
    for nm in names:
        m = red_mask(os.path.join(IMG77 if ed == "77" else IMG91, f"{nm}.jpg"), ed); A = aff[nm]
        if by not in bnd_cache: bnd_cache[by] = boundary_pts(by)
        Ai = np.linalg.inv(np.vstack([A, [0, 0, 1]]))[:2]; mpp = float(np.hypot(A[0, 0], A[1, 0]))
        for part in np.split(bnd_cache[by], np.where(np.hypot(*np.diff(bnd_cache[by], axis=0).T) > 50)[0] + 1):
            cv2.polylines(m, [apply(Ai, part).astype(np.int32).reshape(-1, 1, 2)], False, 0, thickness=max(3, int(2 * 90 / mpp)))
        if M is None: M, A0, mpp0 = m, A, mpp
        else:
            H = (np.linalg.inv(np.vstack([A0, [0, 0, 1]])) @ np.vstack([A, [0, 0, 1]]))[:2]
            M = np.maximum(M, cv2.warpAffine(m, H, (M.shape[1], M.shape[0]), flags=cv2.INTER_NEAREST))
    r = max(1, int(round(TOL / mpp0)))
    Md = cv2.dilate(M, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    frame = np.zeros_like(M); h, w = M.shape
    frame[int(h * .03):int(h * .97), int(w * .03):int(w * (.66 if ed == "91" else .97))] = 1
    return Md, frame, A0


def load_registration():
    """--reuse: 지난번 맞춤(RAW/build/majorroads_plan_report.json의 affine)을 그대로 쓴다. 고르는 링크만 바뀌었을 때."""
    r = json.load(open(REPORT))
    return {k: np.array(v) for k, v in r["affine"].items()}, r["fit"]


def main():
    aff, rep = load_registration() if "--reuse" in sys.argv else register()
    print("맞춤", json.dumps(rep, ensure_ascii=False), file=sys.stderr)
    links = big_links(); P, own = [], []
    for k, l in enumerate(links):
        ls = LineString(l["pts"]); n = max(2, int(ls.length // 25) + 1)
        P.append(np.array([ls.interpolate(t, normalized=True).coords[0] for t in np.linspace(0, 1, n)])); own += [k] * n
    P = np.vstack(P); own = np.array(own); cnt = np.bincount(own, None, len(links))
    res = {l["LINK_ID"]: {"in": [], "on": []} for l in links}; bc = {}; summ = []
    for yr, ed, names, by, title in SHEETS:
        Md, frame, A = sheet_mask(names, ed, by, aff, bc)
        q = apply(np.linalg.inv(np.vstack([A, [0, 0, 1]]))[:2], P); i = np.round(q[:, 0]).astype(int); j = np.round(q[:, 1]).astype(int)
        ok = (i >= 0) & (i < Md.shape[1]) & (j >= 0) & (j < Md.shape[0])
        ins = np.zeros(len(P), bool); ins[ok] = frame[j[ok], i[ok]] > 0
        hit = np.zeros(len(P), bool); hit[ok] = Md[j[ok], i[ok]] > 0
        cov = np.bincount(own, ins, len(links)) / cnt; frac = np.bincount(own, hit & ins, len(links)) / np.maximum(np.bincount(own, ins, len(links)), 1)
        km = 0.0
        for k, l in enumerate(links):
            if cov[k] > 0.5:
                res[l["LINK_ID"]]["in"].append(yr)
                if frac[k] >= 0.6: res[l["LINK_ID"]]["on"].append(yr); km += l["LENGTH"] / 1000
        summ.append({"year": yr, "title": title, "sheets": names, "onKm": round(km)})
        print(yr, title, "광로·대로로 그려진 큰 도로", round(km), "km", file=sys.stderr)
    years = [s[0] for s in SHEETS]
    out = {"note": "표준노드링크 큰 도로 링크마다, 그 해 연혁도 그림이 덮는 범위 안이면 in, 광로·대로(25m 이상)로 그려져 있으면 on. 링크는 2026-11-11 판",
           "sheets": summ, "years": years,
           "links": {k: [v["on"], [y for y in years if y not in v["in"]]] for k, v in res.items()}}
    json.dump(out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    os.makedirs(WORK, exist_ok=True)
    json.dump({"fit": rep, "affine": {k: v.round(6).tolist() for k, v in aff.items()}, "sheets": summ}, open(REPORT, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
