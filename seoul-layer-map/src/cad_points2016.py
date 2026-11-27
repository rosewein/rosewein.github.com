"""2016-01-13 연속지적도(.prj는 EPSG:2097이라 적혀 있으나 실제로는 EPSG:5174(중부원점 127°00′10.405″) 기준. 2097로 바꾸면 x가 255m 어긋남) → 대표점을 EPSG:5186으로 바꿔 npz로. 2026 지적도와 같은 코드 필지로 어긋남을 점검."""
import sys, numpy as np, pyogrio, shapely
from pyproj import Transformer
df = pyogrio.read_dataframe(sys.argv[1], encoding='utf-8', columns=['A1'])
ok = df['A1'].str.fullmatch(r'\d{19}').fillna(False) & df.geometry.notna()
df = df[ok]
xy = shapely.get_coordinates(shapely.point_on_surface(df.geometry.values))
c = df['A1'].astype('int64').values
t = Transformer.from_crs(5174, 5186, always_xy=True)
X, Y = t.transform(xy[:, 0], xy[:, 1])
P = np.load(sys.argv[2]); pc = P['c']
i = np.searchsorted(pc, c); i = np.minimum(i, len(pc) - 1); m = pc[i] == c
dx = P['x'][i[m]] - X[m]; dy = P['y'][i[m]] - Y[m]; d = np.hypot(dx, dy)
print('2016 필지', len(c), '| 2026과 같은 코드', m.sum(), f'| 대표점 거리 중앙값 {np.median(d):.2f}m, 90% {np.percentile(d,90):.2f}m, dx 중앙 {np.median(dx):.2f}, dy 중앙 {np.median(dy):.2f}')
o = np.argsort(c)
np.savez(sys.argv[3], c=c[o], x=X[o], y=Y[o])
