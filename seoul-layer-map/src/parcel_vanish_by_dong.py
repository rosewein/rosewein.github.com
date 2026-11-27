"""해마다 동별로 '2016–2026년 파일에 같은 코드가 없는' 필지 비율을 세고, 같은 본번 대체(C)가 사라진 비율이 높은 동에 얼마나 몰리는지,
그리고 역 둘레 비교에 쓸 역이 있는 동이 서울 평균보다 덜 맞는지를 본다."""
import sys, json, numpy as np, collections
sys.path.insert(0, sys.argv[3])
Z = np.load(sys.argv[1]); base = sys.argv[2]
C = {int(k[1:]): Z[k] for k in Z.files if k[0] == 'c'}
later = np.unique(np.concatenate([C[y] for y in range(2016, 2027)]))
later_bon = np.unique(later // 10000)
topo = json.load(open(f'{base}/data/emd_topo.json'))
nm = {int(g['properties']['cd']): g['properties']['nm'] for g in topo['objects']['seoul_neighborhoods_geo']['geometries']}
def stats(y):
    c = C[y]; dong = c // 10**11              # 앞 8자리
    ok = np.isin(c, later); bon = np.isin(c // 10000, later_bon) & ~ok
    u, inv = np.unique(dong, return_inverse=True)
    n = np.bincount(inv); k = np.bincount(inv, weights=ok); b = np.bincount(inv, weights=bon)
    return {int(d): (int(n[i]), int(k[i]), int(b[i])) for i, d in enumerate(u)}
for y in (1990, 1995, 2000):
    s = stats(y); tot = sum(v[0] for v in s.values())
    lost = {d: v[0]-v[1] for d, v in s.items()}
    worst = sorted(s.items(), key=lambda kv: -(kv[1][0]-kv[1][1]))[:12]
    hi = [d for d, v in s.items() if v[0] >= 200 and (v[0]-v[1]) / v[0] >= 0.5]
    c_all = sum(v[2] for v in s.values()); c_hi = sum(s[d][2] for d in hi)
    print(f'== {y}: 2016+ 파일에 코드 없는 필지 {sum(lost.values())} / {tot}')
    print(f'   절반 넘게 사라진 동(필지 200개 이상) {len(hi)}곳, 이 동들이 사라진 필지의 {100*sum(lost[d] for d in hi)/sum(lost.values()):.0f}%, 같은 본번 대체(C)의 {100*c_hi/c_all:.0f}%')
    print('   사라진 필지가 많은 동:', ', '.join(f"{nm.get(d,d)}({s[d][0]-s[d][1]}, {100*(s[d][0]-s[d][1])/s[d][0]:.0f}%)" for d, _ in worst))
