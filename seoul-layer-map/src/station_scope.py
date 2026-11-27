"""역 둘레 땅값 비교에 쓸 수 있는 역 수 세기.

사용: python3 station_scope.py <seoul-layer-map 폴더>

- data/emd_topo.json의 법정동을 합친 서울 경계 안 역만 센다.
- 역이 처음 열린 해(first) 앞뒤로 몇 년씩이 공시지가 기간(1990–2026)에 드는지,
  개통 때 1km 안에 먼저 열린 역이 있었는지, 같은 해 연 이웃 역이 1km 안인지를 본다.
- 거리는 EPSG:5186(m)으로 바꿔 잰다. shapely, pyproj 필요.
"""
import json, math, collections, sys
from shapely.geometry import Polygon, MultiPolygon, Point, shape
from shapely.ops import unary_union, transform
from pyproj import Transformer

base = sys.argv[1]
topo = json.load(open(f'{base}/data/emd_topo.json'))
sx, sy = topo['transform']['scale']; tx, ty = topo['transform']['translate']
arcs = []
for a in topo['arcs']:
    x = y = 0; pts = []
    for dx, dy in a:
        x += dx; y += dy; pts.append((x*sx+tx, y*sy+ty))
    arcs.append(pts)
def ring(idx):
    out = []
    for i in idx:
        seg = arcs[i] if i >= 0 else arcs[~i][::-1]
        out.extend(seg if not out else seg[1:])
    return out
polys = {}
for g in topo['objects']['seoul_neighborhoods_geo']['geometries']:
    if g['type'] == 'Polygon':
        p = Polygon(ring(g['arcs'][0]), [ring(r) for r in g['arcs'][1:]])
    else:
        p = MultiPolygon([Polygon(ring(pp[0]), [ring(r) for r in pp[1:]]) for pp in g['arcs']])
    polys[g['properties']['cd']] = (g['properties']['nm'], p.buffer(0))
seoul = unary_union([p for _, p in polys.values()])
to5186 = Transformer.from_crs(4326, 5186, always_xy=True).transform

m = json.load(open(f'{base}/data/metro.json'))
st = [s for s in m['stations'] if seoul.contains(Point(s['lng'], s['lat']))]
print('서울 안 역:', len(st), '/ 전체', len(m['stations']))
for s in st:
    s['xy'] = to5186(s['lng'], s['lat'])
def dist(a, b): return math.hypot(a['xy'][0]-b['xy'][0], a['xy'][1]-b['xy'][1])

rows = []
for s in st:
    T = s['first']
    # 그 역이 처음 열린 해보다 앞서 열려 있던 다른 역 중 가장 가까운 것
    prev = [dist(s, o) for o in st if o is not s and o['first'] < T]
    same = [dist(s, o) for o in st if o is not s and o['first'] == T]
    rows.append((s['name'], T, min(prev) if prev else 1e9, min(same) if same else 1e9))

def win(T, pre, post): return T - pre >= 1990 and T + post <= 2026
for pre, post in [(5, 5), (3, 5), (5, 3)]:
    elig = [r for r in rows if win(r[1], pre, post)]
    iso500 = [r for r in elig if r[2] > 1000]
    iso = [r for r in elig if r[2] > 1000 and r[3] > 1000]
    print(f'전 {pre}년·후 {post}년이 1990–2026 안에 드는 역: {len(elig)} | 개통 때 1km 안에 먼저 연 역이 없는 역: {len(iso500)} | 같은 해 연 역도 1km 밖: {len(iso)}')
yrs = collections.Counter(r[1] for r in rows if win(r[1], 5, 5) and r[2] > 1000)
print('위 조건(±5년, 1km 안 먼저 연 역 없음)의 개통 연도별 역 수:', sorted(yrs.items()))
# 같은 해 개통 역끼리 500m 버퍼가 겹치는 비율 (역 간격 1km 미만)
elig = [r for r in rows if win(r[1], 5, 5)]
print('±5년 대상 중 같은 해 연 이웃 역이 1km 안:', sum(1 for r in elig if r[3] < 1000), '/ 500m 안:', sum(1 for r in elig if r[3] < 500))
# 환승: 이미 있던 역에 새 노선이 더해진 경우
add = [(s['name'], s['first'], {l: y for l, y in s['opens'].items() if y > s['first']}) for s in st if any(y > s['first'] and win(y, 5, 5) for y in s['opens'].values())]
print('±5년 창이 드는 해에 기존 역에 노선이 더해진 경우:', len(add))
