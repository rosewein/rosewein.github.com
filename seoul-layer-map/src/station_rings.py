"""역 둘레 고리별 땅값 변화를 네 가지 방식으로 계산(시험용).
    python3 station_rings.py <pnu_price.npz> <loc.npz> <seoul-layer-map 폴더> <출력 json>
- 대상: 서울 안 역 중 처음 열린 해 T의 앞뒤 5년이 1990–2026에 들고, 개통 때 1km 안에 먼저 열린 역이 없던 곳.
- 필지는 T+5년에 열려 있는 역 가운데 가장 가까운 역에만 붙인다. 고리: 0–250, 250–500, 500–1000m.
  바깥 비교 고리: 그 역에서 1–2km이면서 T+5년에 열린 어느 역에서도 1km 넘게 떨어진 필지.
- 위치: exact = 지금 코드·다른 시점 지적도·이력 사슬(방법 0–2), all = 같은 본번·이웃 본번 대신까지(0–4).
- 가(횡단면): 그 해 고리 안 필지 ㎡당 공시지가 중앙값. 나(같은 필지): T−5년과 그 해 모두 있는 필지의 log2 변화율 중앙값."""
import sys, json, numpy as np
from scipy.spatial import cKDTree
from pyproj import Transformer
from shapely.geometry import Polygon, MultiPolygon, Point
from shapely.ops import unary_union
Z = np.load(sys.argv[1]); L = np.load(sys.argv[2]); base = sys.argv[3]
yrs = sorted(int(k[1:]) for k in Z.files if k[0] == 'c')
C = {y: Z[f'c{y}'] for y in yrs}; P = {y: Z[f'p{y}'] for y in yrs}
X = {y: L[f'x{y}'] for y in yrs}; Y = {y: L[f'y{y}'] for y in yrs}; M = {y: L[f'm{y}'] for y in yrs}
seoul_med = {y: float(np.median(P[y][P[y] > 0])) for y in yrs}
tr = Transformer.from_crs(4326, 5186, always_xy=True).transform
# 서울 경계(법정동 합침)
topo = json.load(open(f'{base}/data/emd_topo.json'))
sx, sy = topo['transform']['scale']; tx, ty = topo['transform']['translate']
arcs = []
for a in topo['arcs']:
    x = y = 0; pts = []
    for dx, dy in a: x += dx; y += dy; pts.append((x*sx+tx, y*sy+ty))
    arcs.append(pts)
def ring(idx):
    out = []
    for i in idx:
        seg = arcs[i] if i >= 0 else arcs[~i][::-1]; out.extend(seg if not out else seg[1:])
    return out
polys = []
for g in topo['objects']['seoul_neighborhoods_geo']['geometries']:
    polys.append(Polygon(ring(g['arcs'][0]), [ring(r) for r in g['arcs'][1:]]) if g['type'] == 'Polygon' else
                 MultiPolygon([Polygon(ring(pp[0]), [ring(r) for r in pp[1:]]) for pp in g['arcs']]))
seoul = unary_union([p.buffer(0) for p in polys])
m = json.load(open(f'{base}/data/metro.json'))
st = [dict(name=s['name'], T=s['first'], opens=s['opens'], xy=tr(s['lng'], s['lat'])) for s in m['stations'] if seoul.contains(Point(s['lng'], s['lat']))]
sxy = np.array([s['xy'] for s in st]); sT = np.array([s['T'] for s in st])
def eligible(i):
    s = st[i]; T = s['T']
    if T - 5 < 1990 or T + 5 > 2026: return False
    d = np.hypot(*(sxy - sxy[i]).T)
    return not np.any((sT < T) & (d <= 1000))
targets = [i for i in range(len(st)) if eligible(i)]
RINGS = [(0, 250), (250, 500), (500, 1000), (0, 500)]
def assign(yr_open, xs, ys, i):
    """xs, ys 필지가 T+5년에 열린 역 중 가장 가까운 역이 i인지, 그 거리, 다른 열린 역까지 최소 거리."""
    open_idx = np.where(sT <= yr_open)[0]
    tree = cKDTree(sxy[open_idx])
    d, k = tree.query(np.c_[xs, ys], k=1)
    return open_idx[k] == i, d
trees = {}
for y in yrs:
    ok = ~np.isnan(X[y]); trees[y] = (cKDTree(np.c_[X[y][ok], Y[y][ok]]), np.where(ok)[0])
res = []
for i in targets:
    s = st[i]; T = s['T']; x0, y0 = sxy[i]
    rec = dict(name=s['name'], T=T, lines=sorted(s['opens'].keys()), xy=[x0, y0], years={})
    base_y = T - 5
    # 기준 해 필지(같은 필지 방식용)
    tb, ib = trees[base_y]; nb = ib[tb.query_ball_point([x0, y0], 2000)]
    mine_b, dmin_b = assign(T + 5, X[base_y][nb], Y[base_y][nb], i)
    db = np.hypot(X[base_y][nb] - x0, Y[base_y][nb] - y0)
    for t in range(T - 5, T + 6):
        tt, it = trees[t]; nt = it[tt.query_ball_point([x0, y0], 2000)]
        mine, dmin = assign(T + 5, X[t][nt], Y[t][nt], i)
        d = np.hypot(X[t][nt] - x0, Y[t][nt] - y0); mt = np.where(P[t][nt] > 0, M[t][nt], 9); pt = P[t][nt]
        yr = {}
        for lab, allow in (('exact', 2), ('all', 4)):
            okm = mt <= allow
            cs = {}
            for a, b in RINGS:
                sel = okm & mine & (d >= a) & (d < b)
                cs[f'{a}-{b}'] = [float(np.median(pt[sel])) if sel.sum() >= 20 else None, int(sel.sum())]
            sel = okm & (d >= 1000) & (d < 2000) & (dmin > 1000)
            cs['ctrl'] = [float(np.median(pt[sel])) if sel.sum() >= 20 else None, int(sel.sum())]
            # 같은 필지: 기준 해에 있던 필지 중 t년에도 같은 코드
            cb = C[base_y][nb]; ok2 = (M[base_y][nb] <= allow)
            j = np.searchsorted(C[t], cb); j = np.minimum(j, len(C[t]) - 1); both = (C[t][j] == cb) & ok2 & (P[base_y][nb] > 0) & (P[t][j] > 0)
            lr = np.full(len(cb), np.nan); lr[both] = np.log2(P[t][j[both]] / P[base_y][nb][both])
            sp = {}
            for a, b in RINGS:
                sel = both & mine_b & (db >= a) & (db < b)
                sp[f'{a}-{b}'] = [float(np.nanmedian(lr[sel])) if sel.sum() >= 20 else None, int(sel.sum())]
            sel = both & (db >= 1000) & (db < 2000) & (dmin_b > 1000)
            sp['ctrl'] = [float(np.nanmedian(lr[sel])) if sel.sum() >= 20 else None, int(sel.sum())]
            yr[lab] = dict(cs=cs, sp=sp)
        rec['years'][t] = yr
    res.append(rec)
# 서울 전체 같은 필지 변화율(기준 해 → t)
seoul_sp = {}
for b0 in sorted({r['T'] - 5 for r in res}):
    for t in range(b0, min(b0 + 11, 2027)):
        j = np.searchsorted(C[t], C[b0]); j = np.minimum(j, len(C[t]) - 1); both = (C[t][j] == C[b0]) & (P[b0] > 0) & (P[t][j] > 0)
        seoul_sp[f'{b0}-{t}'] = float(np.median(np.log2(P[t][j[both]] / P[b0][both])))
json.dump(dict(stations=res, seoul_med=seoul_med, seoul_sp=seoul_sp), open(sys.argv[4], 'w'), ensure_ascii=False)
print('역', len(res))
