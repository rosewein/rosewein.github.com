"""비교 대상 역(개통 전후 5년이 1990–2026에 들고, 개통 때 1km 안에 먼저 연 역이 없던 곳) 둘레 500m에 걸친 법정동에서
개통 5년 전 필지가 2016–2026년 파일에 같은 코드로 남은 비율(A+B)을 그 해 서울 전체와 견준다."""
import sys, json, math, numpy as np
from shapely.geometry import Polygon, MultiPolygon, Point
from shapely.ops import unary_union, transform
from pyproj import Transformer
Z = np.load(sys.argv[1]); base = sys.argv[2]
C = {int(k[1:]): Z[k] for k in Z.files if k[0] == 'c'}
later = np.unique(np.concatenate([C[y] for y in range(2016, 2027)])); import pickle; fwd, _w = pickle.load(open(sys.argv[3], "rb")); _ls = set(later.tolist())
def _res(p):
    k = 0
    while p in fwd and k < 20:
        p = fwd[p]; k += 1
        if p in _ls: return True
    return False
def located(c):
    ok = np.isin(c, later); idx = np.where(~ok)[0]
    if len(sys.argv) > 3: ok[idx[[_res(int(p)) for p in c[idx]]]] = True
    return ok
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
tr = Transformer.from_crs(4326, 5186, always_xy=True).transform
dong = {}
for g in topo['objects']['seoul_neighborhoods_geo']['geometries']:
    p = Polygon(ring(g['arcs'][0]), [ring(r) for r in g['arcs'][1:]]) if g['type'] == 'Polygon' else \
        MultiPolygon([Polygon(ring(pp[0]), [ring(r) for r in pp[1:]]) for pp in g['arcs']])
    dong[int(g['properties']['cd'])] = transform(tr, p.buffer(0))
seoul = unary_union(list(dong.values()))
m = json.load(open(f'{base}/data/metro.json'))
st = []
for s in m['stations']:
    xy = tr(s['lng'], s['lat'])
    if seoul.contains(Point(xy)): st.append((s['name'], s['first'], xy))
def d(a, b): return math.hypot(a[0]-b[0], a[1]-b[1])
rate = {}
for y in range(1990, 2027):
    c = C[y]; ok = located(c); dg = c // 10**11
    u, inv = np.unique(dg, return_inverse=True)
    rate[y] = (dict(zip(u.tolist(), np.bincount(inv).tolist())), dict(zip(u.tolist(), np.bincount(inv, weights=ok).tolist())), ok.mean())
rows = []
for name, T, xy in st:
    if not (T - 5 >= 1990 and T + 5 <= 2026): continue
    if any(o[1] < T and d(o[2], xy) <= 1000 for o in st if o[0] != name): continue
    buf = Point(xy).buffer(500)
    ds = [cd for cd, p in dong.items() if p.intersects(buf)]
    n, k, seo = rate[T-5]
    nn = sum(n.get(cd, 0) for cd in ds); kk = sum(k.get(cd, 0) for cd in ds)
    rows.append((name, T, nn, kk / nn if nn else float('nan'), seo))
r = np.array([x[3] for x in rows]); s = np.array([x[4] for x in rows])
print('역', len(rows), '| 역 둘레 500m에 걸친 동의 위치 찾는 비율(A+B, 이력 파일을 주면 +L) 중앙값', f'{np.nanmedian(r)*100:.1f}%', '| 같은 해 서울', f'{np.median(s)*100:.1f}%')
print('서울보다 10%p 넘게 낮은 역:', sum(1 for x in rows if x[3] < x[4] - 0.10), '/ 낮은 순:', ', '.join(f'{x[0]}({x[1]}, {x[3]*100:.0f}%)' for x in sorted(rows, key=lambda x: x[3])[:10]))
by = {}
for x in rows: by.setdefault(x[1], []).append(x[3] - x[4])
print('개통 연도별 (역 둘레 − 서울) 중앙값 %p:', ', '.join(f'{y}:{np.median(v)*100:+.1f}(n={len(v)})' for y, v in sorted(by.items())))
