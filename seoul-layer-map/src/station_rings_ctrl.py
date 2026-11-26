"""역 둘레 같은 필지 변화를 대조 세 가지와 견주고, 역 둘레 개발 정도를 함께 적는다(시험용).
    python3 -I station_rings_ctrl.py <pnu_price.npz> <loc.npz> <metro.json> <emd_topo.json> <출력 json> [gb_flags.npz]
- gb_flags.npz(gb_flags.py)를 주면 개통 5년 전 위치가 그린벨트(2026년 경계) 안인 필지를 역 고리와 대조에서 모두 뺀다.
- 대상 역: station_rings.py와 같다(T−5 ≥ 1990, T+5 ≤ 2026, 개통 때 1km 안에 먼저 열린 역 없음, 서울 안).
- 필지: T−5년에 정확한 위치(방법 0–2)가 있고 값이 0보다 큰 필지. T+5년에 열린 역 가운데 가장 가까운 역에 붙인다.
- 같은 필지 변화: log2(p_t / p_{T−5}), t = T−5…T+5, 같은 토지코드로 남은 필지만.
- 대조
  seoul  서울 전체 같은 필지 변화 중앙값
  sim    같은 구 · 같은 T−5 값 10분위 · T+5년에 열린 모든 역에서 1km 밖인 필지의 변화 중앙값을
         역 필지마다 빼고 모은 중앙값(비슷한 땅)
  future T+6…T+15년에 열릴 역 500m 안이면서 T+5년에 열린 모든 역에서 1km 밖인 필지(서울 전체에서)
  ring   1–2km 바깥이면서 T+5년에 열린 모든 역에서 1km 밖(앞 시험판과 같은 것)
- 개발 정도: T−5년 0–500m 필지(위치 방법 0–4) 가운데 T+5년에 같은 코드가 없는 비율."""
import sys, json, numpy as np, pandas as pd
from scipy.spatial import cKDTree
from pyproj import Transformer
from shapely.geometry import Polygon, MultiPolygon, Point
from shapely.ops import unary_union
Z = np.load(sys.argv[1]); L = np.load(sys.argv[2]); metro = json.load(open(sys.argv[3])); topo = json.load(open(sys.argv[4]))
GB = np.load(sys.argv[6]) if len(sys.argv) > 6 else None
yrs = sorted(int(k[1:]) for k in Z.files if k[0] == 'c')
C = {y: Z[f'c{y}'] for y in yrs}; P = {y: Z[f'p{y}'] for y in yrs}
tr = Transformer.from_crs(4326, 5186, always_xy=True).transform
sx, sy = topo['transform']['scale']; tx, ty = topo['transform']['translate']; arcs = []
for a in topo['arcs']:
    x = y = 0; pts = []
    for dx, dy in a: x += dx; y += dy; pts.append((x * sx + tx, y * sy + ty))
    arcs.append(pts)
def ring_(idx):
    out = []
    for i in idx:
        seg = arcs[i] if i >= 0 else arcs[~i][::-1]; out.extend(seg if not out else seg[1:])
    return out
polys = [Polygon(ring_(g['arcs'][0]), [ring_(r) for r in g['arcs'][1:]]) if g['type'] == 'Polygon' else
         MultiPolygon([Polygon(ring_(pp[0]), [ring_(r) for r in pp[1:]]) for pp in g['arcs']])
         for g in topo['objects']['seoul_neighborhoods_geo']['geometries']]
seoul = unary_union([p.buffer(0) for p in polys])
st = [dict(name=s['name'], T=s['first'], lines=sorted(s['opens']), xy=tr(s['lng'], s['lat'])) for s in metro['stations'] if seoul.contains(Point(s['lng'], s['lat']))]
# 서울 밖 역도 "가장 가까운 열린 역" 계산에는 넣는다
allst = [(s['first'], tr(s['lng'], s['lat'])) for s in metro['stations']]
aT = np.array([f for f, _ in allst]); axy = np.array([p for _, p in allst])
sxy = np.array([s['xy'] for s in st]); sT = np.array([s['T'] for s in st])
def eligible(i):
    T = sT[i]
    if T - 5 < 1990 or T + 5 > 2026: return False
    d = np.hypot(*(sxy - sxy[i]).T)
    return not np.any((sT < T) & (d <= 1000))
targets = [i for i in range(len(st)) if eligible(i)]
RINGS = [(0, 250), (250, 500), (500, 1000)]
res = []
for b in sorted({int(sT[i]) - 5 for i in targets}):
    group = [i for i in targets if sT[i] - 5 == b]
    X, Y, M = L[f'x{b}'], L[f'y{b}'], L[f'm{b}']; cb = C[b]; pb = P[b]
    has = ~np.isnan(X) & (pb > 0)
    ingb = GB[f'g{b}'].astype(bool) if GB is not None else np.zeros(len(cb), bool)
    gbshare_src = has.copy()
    if GB is not None: has = has & ~ingb
    exact = has & (M <= 2)
    gu = (cb // 10**14).astype(np.int64)
    # 구 안 T−5 값 10분위
    lp = np.log(np.where(pb > 0, pb, np.nan))
    dec = np.full(len(cb), -1, np.int64)
    df = pd.DataFrame({'gu': gu[pb > 0], 'lp': lp[pb > 0]})
    dec[pb > 0] = df.groupby('gu')['lp'].transform(lambda s: pd.qcut(s.rank(method='first'), 10, labels=False)).to_numpy()
    # 같은 필지 변화(서울 전체, b → t)
    LR = {}
    for t in range(b, b + 11):
        j = np.searchsorted(C[t], cb); j = np.minimum(j, len(C[t]) - 1)
        both = (C[t][j] == cb) & (pb > 0) & (P[t][j] > 0)
        lr = np.full(len(cb), np.nan, np.float32); lr[both] = np.log2(P[t][j[both]] / pb[both]); LR[t] = lr
    seoul_ref = {t: float(np.nanmedian(LR[t])) for t in LR}
    # 열린 역(T+5)까지 거리 — 같은 T끼리 공유
    for T in sorted({int(sT[i]) for i in group}):
        ref = T + 5
        op = np.where(aT <= ref)[0]; tree = cKDTree(axy[op])
        idx_has = np.where(gbshare_src)[0]; dmin = np.full(len(cb), np.nan); near = np.full(len(cb), -1)
        d_, k_ = tree.query(np.c_[X[idx_has], Y[idx_has]]); dmin[idx_has] = d_; near[idx_has] = op[k_]
        far = exact & (dmin > 1000)
        fu = np.where((aT > ref) & (aT <= T + 15))[0]
        if len(fu):
            dfu = np.full(len(cb), np.inf); dfu[idx_has] = cKDTree(axy[fu]).query(np.c_[X[idx_has], Y[idx_has]])[0]
            fut = far & (dfu < 500)
        else:
            fut = np.zeros(len(cb), bool)
        for i in [i for i in group if sT[i] == T]:
            s = st[i]; x0, y0 = sxy[i]
            # 이 역이 allst 안에서 몇 번인지(같은 좌표)
            me = np.where(np.hypot(*(axy - sxy[i]).T) < 1)[0]
            d = np.hypot(X - x0, Y - y0)
            mine = np.isin(near, me)
            rec = dict(name=s['name'], T=T, lines=s['lines'], years={}, n={}, dev=None, gb=None)
            a5 = gbshare_src & mine & (d < 500)
            if GB is not None and a5.sum() >= 20: rec['gb'] = float(ingb[a5].mean())
            a500 = has & mine & (d < 500)
            if a500.sum() >= 20:
                j = np.searchsorted(C[T + 5], cb[a500]); j = np.minimum(j, len(C[T + 5]) - 1)
                rec['dev'] = float(1 - (C[T + 5][j] == cb[a500]).mean())
            rec['n500'] = int(a500.sum())
            gus = np.unique(gu[exact & mine & (d < 1000)])
            simc = far & np.isin(gu, gus)
            ringc = far & (d >= 1000) & (d < 2000)
            for t in range(b, b + 11):
                lr = LR[t]; yr = {}
                # 비슷한 땅: (구, 10분위)별 대조 중앙값
                okc = simc & ~np.isnan(lr)
                cell = pd.DataFrame({'k': gu[okc] * 100 + dec[okc], 'v': lr[okc]}).groupby('k')['v'].agg(['median', 'size'])
                cell = cell[cell['size'] >= 10]['median']
                fv = lr[fut & ~np.isnan(lr)]; fref = float(np.median(fv)) if len(fv) >= 30 else None
                rv = lr[ringc & ~np.isnan(lr)]; rref = float(np.median(rv)) if len(rv) >= 30 else None
                for a, bb in RINGS:
                    sel = exact & mine & (d >= a) & (d < bb) & ~np.isnan(lr)
                    key = f'{a}-{bb}'
                    if sel.sum() < 20:
                        yr[key] = None; continue
                    v = lr[sel]; g = float(np.median(v))
                    adj = pd.Series(gu[sel] * 100 + dec[sel]).map(cell).to_numpy(dtype=float)
                    va = v - adj; va = va[~np.isnan(va)]
                    yr[key] = dict(raw=g, seoul=g - seoul_ref[t], sim=float(np.median(va)) if len(va) >= 20 else None,
                                   future=None if fref is None else g - fref, ring=None if rref is None else g - rref, n=int(sel.sum()))
                rec['years'][t - T] = yr
                rec['n'][t - T] = dict(sim=int(okc.sum()), future=int(len(fv)), ring=int(len(rv)))
            res.append(rec)
    print(b, len(group), '역')
json.dump(res, open(sys.argv[5], 'w'), ensure_ascii=False)
print('역', len(res))
