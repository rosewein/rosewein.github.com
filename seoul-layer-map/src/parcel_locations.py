"""해마다 공시지가 필지에 위치(EPSG:5186 대표점)와 찾은 방법을 붙인다. 분석용 중간 파일, 저장소에 넣지 않음.
    python3 build_locations.py <pnu_price.npz> <lineage.pkl> <출력 loc.npz> <지적도 대표점 npz ...(앞쪽이 우선)>
방법 코드: 0 A 2026 코드 / 1 B 다른 시점 지적도 코드 / 2 L 이력 사슬 / 3 C 같은 본번 무리 중앙 / 4 D 본번 ±5 무리 중앙 / 5 못 찾음"""
import sys, pickle, numpy as np
Z = np.load(sys.argv[1]); fwd, _ = pickle.load(open(sys.argv[2], 'rb'))
codes, xs, ys = [], [], []
for i, f in enumerate(sys.argv[4:]):
    P = np.load(f); c = P['c']
    if codes:
        have = np.concatenate(codes); keep = ~np.isin(c, have)
    else:
        keep = np.ones(len(c), bool)
    codes.append(c[keep]); xs.append(P['x'][keep]); ys.append(P['y'][keep])
    print(f, '추가', keep.sum())
first_n = len(codes[0])
ac = np.concatenate(codes); ax = np.concatenate(xs); ay = np.concatenate(ys)
src = np.concatenate([np.full(len(c), i) for i, c in enumerate(codes)])
o = np.argsort(ac); ac, ax, ay, src = ac[o], ax[o], ay[o], src[o]
aset = set(ac.tolist())
def find(c):
    i = np.searchsorted(ac, c); i = np.minimum(i, len(ac) - 1); ok = ac[i] == c
    return i, ok
# 본번 무리 중앙
bk = ac // 10000; ub, inv = np.unique(bk, return_inverse=True)
bx = np.bincount(inv, ax) / np.bincount(inv); by = np.bincount(inv, ay) / np.bincount(inv)
def resolve(p):
    k = 0
    while p in fwd and k < 20:
        p = fwd[p]; k += 1
        if p in aset: return p
    return None
out = {}
for y in sorted(int(k[1:]) for k in Z.files if k[0] == 'c'):
    c = Z[f'c{y}']; n = len(c)
    X = np.full(n, np.nan); Y = np.full(n, np.nan); M = np.full(n, 5, np.int8)
    i, ok = find(c)
    X[ok] = ax[i[ok]]; Y[ok] = ay[i[ok]]; M[ok] = np.where(src[i[ok]] == 0, 0, 1)
    rest = np.where(~ok)[0]
    for j in rest:
        t = resolve(int(c[j]))
        if t is not None:
            k = np.searchsorted(ac, t); X[j] = ax[k]; Y[j] = ay[k]; M[j] = 2
    rest = np.where(M == 5)[0]
    q = c[rest] // 10000
    k = np.searchsorted(ub, q); k = np.minimum(k, len(ub) - 1); hit = ub[k] == q
    X[rest[hit]] = bx[k[hit]]; Y[rest[hit]] = by[k[hit]]; M[rest[hit]] = 3
    rest = np.where(M == 5)[0]
    q = c[rest] // 10000; g = q // 10000; num = q % 10000
    lo = np.searchsorted(ub, g * 10000 + np.maximum(num - 5, 0)); hi = np.searchsorted(ub, g * 10000 + num + 5, side='right')
    for j, a, b, nm in zip(rest, lo, hi, num):
        if b > a:
            cand = ub[a:b] % 10000; kk = a + int(np.argmin(np.abs(cand - nm)))
            X[j] = bx[kk]; Y[j] = by[kk]; M[j] = 4
    out[f'x{y}'] = X.astype(np.float32); out[f'y{y}'] = Y.astype(np.float32); out[f'm{y}'] = M
    if y % 5 == 0: print(y, np.bincount(M, minlength=6) / n)
np.savez(sys.argv[3], **out)
