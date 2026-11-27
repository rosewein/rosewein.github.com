"""같은 본번 대체(C)가 실제 위치와 얼마나 떨어지는지 대조.
진짜 위치: (1) 이력 사슬(L)로 이어진 2026 필지의 대표점, (2) 30588 이동 전 도형의 대표점.
대체 위치: 2026 지적도에서 같은 동·대장·본번 필지 대표점들의 중앙(본번이 없으면 비교에서 뺌).
    python3 parcel_check_bonbun.py <pnu_price.npz> <lineage.pkl> <cad2026_pts.npz> <30588 shp>
주의: 30588 도형은 좌표계가 섞여 있어 (2)는 서울 5186 범위 밖 도형 때문에 크게 틀린다. 범위 안 도형만 쓴 결과는 HANDOFF.md에 적었다.
"""
import sys, pickle, numpy as np, pandas as pd, pyogrio, shapely
Z = np.load(sys.argv[1]); fwd, why = pickle.load(open(sys.argv[2], 'rb'))
P = np.load(sys.argv[3]); pc, px, py = P['c'], P['x'], P['y']
pos = dict(zip(pc.tolist(), zip(px.tolist(), py.tolist())))
# 같은 본번 무리의 중앙 위치(2026 지적도)
bk = pc // 10000
u, inv = np.unique(bk, return_inverse=True)
bx = np.bincount(inv, px) / np.bincount(inv); by = np.bincount(inv, py) / np.bincount(inv)
bpos = dict(zip(u.tolist(), zip(bx.tolist(), by.tolist())))
now = set(pc.tolist())
def resolve(p):
    k = 0
    while p in fwd and k < 20:
        p = fwd[p]; k += 1
        if p in now: return p
    return None
c90 = Z['c1990']; later = np.unique(np.concatenate([Z[f'c{y}'] for y in range(2016, 2027)]))
gone = c90[~np.isin(c90, later)]
d = []
for p in gone.tolist():
    t = resolve(p)
    if t is None: continue
    b = bpos.get(p // 10000)
    if b is None: continue
    tx, ty = pos[t]; d.append(np.hypot(tx - b[0], ty - b[1]))
d = np.array(d)
print(f'(1) 1990 사라진 필지 중 이력으로 2026 필지까지 이어지고 같은 본번도 남은 {len(d)}개: 거리 중앙값 {np.median(d):.0f}m, 90% {np.percentile(d,90):.0f}m, 250m 넘음 {np.mean(d>250)*100:.1f}%, 500m 넘음 {np.mean(d>500)*100:.1f}%')
# (2) 30588 이동 전 도형
g = pyogrio.read_dataframe(sys.argv[4], encoding='cp949', columns=['ADM_SECT_C','LAND_LOC_C','LEDG_GBN','BOBN','BUBN','LAND_MOV_B'])
g = g[(g['LAND_MOV_B'] == '1') & g['LEDG_GBN'].isin(['1','2']) & g[['ADM_SECT_C','LAND_LOC_C','BOBN','BUBN']].notna().all(axis=1)]
s = g['ADM_SECT_C'].str.zfill(5) + g['LAND_LOC_C'].str.zfill(5) + g['LEDG_GBN'] + g['BOBN'].str.zfill(4) + g['BUBN'].str.zfill(4)
keep = s.str.fullmatch(r'\d{19}').fillna(False) & g.geometry.notna()
g = g[keep]; s = s[keep].astype('int64').values
xy = shapely.get_coordinates(shapely.point_on_surface(g.geometry.values))
c05 = Z['c2005']; gone05 = set(c05[~np.isin(c05, later)].tolist())
d2 = []
for p, (x, y) in zip(s.tolist(), xy.tolist()):
    if p not in gone05: continue
    b = bpos.get(p // 10000)
    if b is None: continue
    d2.append(np.hypot(x - b[0], y - b[1]))
d2 = np.array(d2)
print(f'(2) 2005 공시지가에 있다가 사라졌고 30588 이동 전 도형이 있는 필지 중 같은 본번이 남은 {len(d2)}개: 거리 중앙값 {np.median(d2):.0f}m, 90% {np.percentile(d2,90):.0f}m, 250m 넘음 {np.mean(d2>250)*100:.1f}%, 500m 넘음 {np.mean(d2>500)*100:.1f}%')
