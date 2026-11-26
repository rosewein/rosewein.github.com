"""사건 시점 시험 그림용 계열 계산.
    python3 -I station_events.py <pnu_price.npz> <loc.npz> <metro.json> <출력 json>
묶음마다 기준 해 b를 두고 1990–2026 모든 해에 대해
- sp: 기준 해 필지 가운데 t년에도 같은 코드로 남은 필지의 log2(p_t/p_b) 중앙값 − 서울 전체 같은 계산
- cs: log2(묶음 중앙값_t / 서울 중앙값_t) − log2(묶음 중앙값_b / 서울 중앙값_b)
- n_sp, n_cs, keep(기준 해 필지 가운데 남은 비율)
역 묶음은 정확한 위치(방법 0–2)만 쓰고, 기준 연도 ref에 열려 있는 역 가운데 가장 가까운 역이 묶음 안 역이면서 500m 안인 필지."""
import sys, json, numpy as np
from scipy.spatial import cKDTree
from pyproj import Transformer
Z = np.load(sys.argv[1]); L = np.load(sys.argv[2]); metro = json.load(open(sys.argv[3]))
yrs = sorted(int(k[1:]) for k in Z.files if k[0] == 'c')
C = {y: Z[f'c{y}'] for y in yrs}; P = {y: Z[f'p{y}'] for y in yrs}
tr = Transformer.from_crs(4326, 5186, always_xy=True).transform
st = [(s['name'], s['first'], tr(s['lng'], s['lat'])) for s in metro['stations']]
seoul_med = {y: float(np.median(P[y][P[y] > 0])) for y in yrs}
_loc = {}
def loc(y):
    if y not in _loc: _loc[y] = (L[f'x{y}'], L[f'y{y}'], L[f'm{y}'])
    return _loc[y]
def station_mask(names, ref, r=500):
    op = [(n, xy) for n, f, xy in st if f <= ref]
    nm = np.array([n for n, _ in op]); xy = np.array([p for _, p in op]); tree = cKDTree(xy)
    ing = np.isin(nm, list(names))
    def f(y):
        X, Y, M = loc(y); ok = ~np.isnan(X) & (M <= 2)
        out = np.zeros(len(X), bool)
        d, k = tree.query(np.c_[X[ok], Y[ok]])
        out[np.where(ok)[0]] = ing[k] & (d < r)
        return out
    return f
def dong_mask(codes):
    def f(y): return np.isin(C[y] // 10**11, codes)
    return f
_seoul_sp = {}
def seoul_sp(b, t):
    if (b, t) not in _seoul_sp:
        j = np.searchsorted(C[t], C[b]); j = np.minimum(j, len(C[t]) - 1)
        both = (C[t][j] == C[b]) & (P[b] > 0) & (P[t][j] > 0)
        _seoul_sp[(b, t)] = float(np.median(np.log2(P[t][j[both]] / P[b][both])))
    return _seoul_sp[(b, t)]
def gu_ctrl(names, ref, gus, r=1000):
    """같은 구 안에서 ref 해에 열린 모든 역에서 r m 넘게 떨어진 필지(정확한 위치만)."""
    xy = np.array([p for n, f, p in st if f <= ref]); tree = cKDTree(xy)
    def f(y):
        X, Y, M = loc(y); ok = ~np.isnan(X) & (M <= 2) & np.isin(C[y] // 10**14, gus)
        out = np.zeros(len(X), bool)
        d, _ = tree.query(np.c_[X[ok], Y[ok]])
        out[np.where(ok)[0]] = d > r
        return out
    return f
def gu_rest(dongs):
    gus = sorted({d // 1000 for d in dongs})
    def f(y): g = C[y] // 10**11; return np.isin(g // 1000, gus) & ~np.isin(g, dongs)
    return f
_ctrl_cache = {}
def ctrl_by_gu(ctrl, key, b, t):
    """대조 필지의 구별 log2(p_t/p_b) 중앙값 {구: (중앙값, 필지 수)}."""
    if (key, b, t) in _ctrl_cache: return _ctrl_cache[(key, b, t)]
    mb = ctrl(b) & (P[b] > 0); cb = C[b][mb]; pb = P[b][mb]
    j = np.searchsorted(C[t], cb); j = np.minimum(j, len(C[t]) - 1); both = (C[t][j] == cb) & (P[t][j] > 0)
    lr = np.log2(P[t][j[both]] / pb[both]); g = cb[both] // 10**14
    out = {int(u): (float(np.median(lr[g == u])), int((g == u).sum())) for u in np.unique(g)}
    _ctrl_cache[(key, b, t)] = out
    return out
def series(mask, b, ctrl=None):
    mb = mask(b) & (P[b] > 0); cb = C[b][mb]; pb = P[b][mb]
    base_cs = np.log2(np.median(pb) / seoul_med[b])
    out = dict(b=b, n_base=int(mb.sum()), years={})
    for t in yrs:
        j = np.searchsorted(C[t], cb); j = np.minimum(j, len(C[t]) - 1)
        both = (C[t][j] == cb) & (P[t][j] > 0)
        sp = float(np.median(np.log2(P[t][j[both]] / pb[both])) - seoul_sp(b, t)) if both.sum() >= 20 else None
        mt = mask(t) & (P[t] > 0)
        cs = float(np.log2(np.median(P[t][mt]) / seoul_med[t]) - base_cs) if mt.sum() >= 20 else None
        g = float(np.median(np.log2(P[t][j[both]] / pb[both]))) if both.sum() >= 20 else None
        spc, nc = None, 0
        if ctrl and both.sum() >= 20:
            cg = ctrl_by_gu(ctrl, id(ctrl), b, t); gg = cb[both] // 10**14
            adj = np.array([cg[x][0] if x in cg and cg[x][1] >= 20 else np.nan for x in gg])
            lr = np.log2(P[t][j[both]] / pb[both]) - adj; ok = ~np.isnan(lr)
            if ok.sum() >= 20: spc = float(np.median(lr[ok]))
            nc = int(sum(v[1] for k, v in cg.items() if k in set(gg.tolist())))
        out['years'][t] = dict(sp=sp, spc=spc, cs=cs, n_sp=int(both.sum()), n_ctrl=nc, n_cs=int(mt.sum()), keep=float(both.sum() / max(1, len(cb))))
    return out
G7a = ['마들', '중계', '공릉', '먹골', '중화', '상봉', '면목', '사가정', '용마산', '중곡']
G7b = ['자양', '청담', '강남구청', '학동', '숭실대입구', '상도', '장승배기', '신대방삼거리', '보라매', '신풍', '천왕']
GS = ['양재시민의숲', '청계산입구']
def gus_of(mask, b, share=0.1):
    g = C[b][mask(b)] // 10**14; u, n = np.unique(g, return_counts=True); return [int(x) for x in u[n >= share * n.sum()]]
groups = {
    '7호선 1996 구간': (station_mask(G7a, 2001), 1990, G7a, 2001),
    '7호선 2000 구간': (station_mask(G7b, 2005), 1990, G7b, 2005),
    '신분당선 신설역': (station_mask(GS, 2016), 2001, GS, 2016),
    '진관동(은평뉴타운)': (dong_mask([11380114]), 2002, [11380114], None),
    '마곡동(마곡지구)': (dong_mask([11500105]), 2005, [11500105], None),
}
res = {}
for k, (m, b, ids, ref) in groups.items():
    if ref: gus = sorted({int(x) for x in C[b][m(b)] // 10**14}); ctrl = gu_ctrl(ids, ref, gus)
    else: gus = sorted({d // 1000 for d in ids}); ctrl = gu_rest(ids)
    res[k] = series(m, b, ctrl); res[k]['ctrl_gus'] = gus
# 서울 전체 한 해 변화(같은 필지, 앞 해 → 그 해)
res['_seoul_yoy'] = {t: seoul_sp(t - 1, t) for t in yrs[1:]}
res['_seoul_med'] = seoul_med
json.dump(res, open(sys.argv[4], 'w'), ensure_ascii=False)
for k, v in res.items():
    if k.startswith('_'): continue
    print(k, '기준', v['b'], '필지', v['n_base'], '대조 구', v['ctrl_gus'])
    for t in range(1990, 2027, 2):
        r = v['years'][t]
        f = lambda x: '   -  ' if x is None else f'{100*(2**x-1):+6.1f}'
        print(f'  {t} 서울대비 {f(r["sp"])} 같은구대비 {f(r["spc"])} (n {r["n_sp"]:5d}, 대조 {r["n_ctrl"]:6d}, 남음 {100*r["keep"]:3.0f}%)')
