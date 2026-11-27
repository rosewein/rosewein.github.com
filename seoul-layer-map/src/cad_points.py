"""연속지적도형정보(dsId=23, 서울 2026-11-08) → 필지 고유번호별 대표점(EPSG:5186) npz. 위치 대조용, 저장소에 넣지 않음.
    python3 cad_points.py <AL_D002_11_YYYYMMDD.shp> <출력 npz>
"""
import sys, numpy as np, pyogrio, shapely
df = pyogrio.read_dataframe(sys.argv[1], encoding='cp949', columns=['A1'])
ok = df['A1'].str.fullmatch(r'\d{19}').fillna(False)
df = df[ok]
pts = shapely.point_on_surface(df.geometry.values)
xy = shapely.get_coordinates(pts)
c = df['A1'].astype('int64').values
o = np.argsort(c)
np.savez(sys.argv[2], c=c[o], x=xy[o,0], y=xy[o,1], area=shapely.area(df.geometry.values)[o])
print(len(c), '필지, 고유번호 중복', len(c) - len(np.unique(c)))
