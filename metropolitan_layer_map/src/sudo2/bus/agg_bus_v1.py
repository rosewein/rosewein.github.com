"""노선 경로를 도로 구간(무방향)별로 모아, 지나는 노선 묶음이 같은 구간끼리 이은 선(chain)을 만든다 → bus_gg.json"""
import json, pickle, collections, numpy as np
import shapely
Z = np.load('/home/claude/sudo2/bus/busgraph.npz'); X, Y = Z['x'], Z['y']
rs = json.load(open('/home/claude/sudo2/bus/routes_gg.json')) + json.load(open('/home/claude/sudo2/bus/routes_ic.json')) + json.load(open('/home/claude/sudo2/bus/routes_se.json'))
YB = json.load(open('/home/claude/sudo2/bus/years_bus.json'))
DUP = {'232000061'}  # 경기 BMS에도 있는 강화–신촌 3000번(인천 면허 자료로 그림)
rs = [r for r in rs if r['id'] not in DUP]
P = pickle.load(open('/home/claude/sudo2/bus/paths_all.pkl', 'rb'))
E = collections.defaultdict(set)
brk = {}
for ri, r in enumerate(rs):
    p = P[r['id']]['path']; brk[ri] = P[r['id']]['breaks']
    for a, b in zip(p, p[1:]):
        if a < 0 or b < 0 or a == b: continue
        E[(min(a, b), max(a, b))].add(ri)
adj = collections.defaultdict(list)
for (a, b) in E: adj[a].append(b); adj[b].append(a)
key = lambda a, b: (min(a, b), max(a, b))
def is_break(n):
    nb = adj[n]
    if len(nb) != 2: return True
    return E[key(n, nb[0])] != E[key(n, nb[1])]
seen = set(); chains = []
for (a, b) in list(E):
    if (a, b) in seen: continue
    # 양쪽으로 늘려 사슬 하나
    rset = E[(a, b)]; seen.add((a, b)); seq = [a, b]
    for end in (0, 1):
        while True:
            n = seq[-1] if end else seq[0]; prev = seq[-2] if end else seq[1]
            if is_break(n): break
            nx = [m for m in adj[n] if m != prev][0]
            k = key(n, nx)
            if k in seen or E[k] != rset: break
            seen.add(k)
            if end: seq.append(nx)
            else: seq.insert(0, nx)
    ls = shapely.LineString([(X[i], Y[i]) for i in seq]).simplify(0.00006)
    chains.append(dict(p=[[round(x, 5), round(y, 5)] for x, y in ls.coords], r=sorted(rset)))
chains.sort(key=lambda c: len(c['r']))
SNAP = {'경기': 2023, '인천': 2024, '서울': 2026}
def ymeta(r):
    y = YB.get(r['id'], {})
    reg = r.get('reg', '경기')
    return dict(y=y.get('y'), yh=y.get('how'), ys=y.get('src'), reg=reg, d=SNAP[reg])
meta = [dict(n=r['name'], o=r['o'], e=r['e'], v=r.get('variants', []), b=brk[i], **ymeta(r)) for i, r in enumerate(rs)]
# 출발점(바깥 끝)
starts = [[round(r['pts'][0][0], 5), round(r['pts'][0][1], 5)] for r in rs]
json.dump(dict(ch=chains, rt=meta, st=starts), open('/home/claude/sudo2/bus/bus_gg.json', 'w'), ensure_ascii=False, separators=(',', ':'))
cnt = collections.Counter(len(c['r']) for c in chains)
print('chains', len(chains), 'max routes on a chain', max(cnt), 'breaks', sum(brk.values()))
import os; print(os.path.getsize('/home/claude/sudo2/bus/bus_gg.json') // 1024, 'KB')
