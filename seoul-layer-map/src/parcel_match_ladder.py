"""단계별 위치 찾기 비율(최종). A 2026 코드 / B 2016–2026 코드 / L 이력 사슬(dsId=13, CC BY) / M 30588 접수 묶음의 이동 후 필지가
2026 지적도에서 반경 250m 안에 모여 있음(4유형) / C 같은 본번 / D 본번 ±5 / 나머지
    python3 parcel_match_ladder.py <pnu_price.npz> <lineage.pkl> <mov_links.pkl> <cad2026_pts.npz> <출력 json>
"""
import sys, pickle, json, numpy as np
Z = np.load(sys.argv[1]); fwd, why = pickle.load(open(sys.argv[2], 'rb')); links = pickle.load(open(sys.argv[3], 'rb'))
P = np.load(sys.argv[4]); pos = dict(zip(P['c'].tolist(), zip(P['x'].tolist(), P['y'].tolist())))
C = {int(k[1:]): Z[k] for k in Z.files if k[0] == 'c'}
now = C[2026]; later = np.unique(np.concatenate([C[y] for y in range(2016, 2027)])); later_set = set(later.tolist())
def resolve(p):
    k = 0
    while p in fwd and k < 20:
        p = fwd[p]; k += 1
        if p in later_set: return p
    return None
mloc = {}
for p, (a, y, it) in links.items():
    pts = np.array([pos[q] for q in a.tolist() if q in pos])
    if len(pts) == 0: continue
    c = np.median(pts, axis=0); r = np.percentile(np.hypot(*(pts - c).T), 90)
    mloc[p] = (c, r)
lb = np.unique(later // 10000)
out = {}
print(' 연도     A    A+B   +L   +M250  +C    +D   나머지  | M 전부(퍼짐 무관)')
for y in sorted(C):
    if y >= 2016: continue
    c = C[y]; n = len(c)
    a = np.isin(c, now); b = ~a & np.isin(c, later); rest = ~(a | b)
    idx = np.where(rest)[0]
    l = np.zeros(n, bool); l[idx[[resolve(int(p)) is not None for p in c[idx]]]] = True; rest &= ~l
    idx = np.where(rest)[0]
    r = np.array([mloc[p][1] if p in mloc else np.inf for p in c[idx].tolist()])
    m_all = np.zeros(n, bool); m_all[idx[np.isfinite(r)]] = True
    mm = np.zeros(n, bool); mm[idx[r <= 250]] = True; rest &= ~mm
    cc = rest & np.isin(c // 10000, lb); rest &= ~cc
    q = (c // 10000)[rest]; g = q // 10000; num = q % 10000
    lo = np.searchsorted(lb, g*10000 + np.maximum(num-5, 0)); hi = np.searchsorted(lb, g*10000 + num + 5, side='right')
    d = np.zeros(n, bool); d[np.where(rest)[0][hi > lo]] = True; rest &= ~d
    parts = [a.sum(), b.sum(), l.sum(), mm.sum(), cc.sum(), d.sum()]
    cum = np.cumsum(parts) / n * 100
    out[y] = dict(zip('A B L M250 C D'.split(), map(int, parts)), rest=int(rest.sum()), M_any=int(m_all.sum()), n=int(n))
    print(f'{y} ' + ' '.join(f'{v:5.1f}' for v in cum) + f'  {rest.mean()*100:5.1f}  | {m_all.sum()/n*100:4.1f}')
json.dump(out, open(sys.argv[5], 'w'))
