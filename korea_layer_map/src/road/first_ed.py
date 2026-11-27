# 민자 노선(OSM operator·개통일 묶음)마다 표준노드링크 각 판 도로망이 OSM 선을 얼마나 덮는지 셈
import json, sys, collections, numpy as np
from pyproj import Transformer
src, griddir, out = sys.argv[1], sys.argv[2], sys.argv[3]
X0,Y0,CS,NX,NY = -100000.0,0.0,50.0,17000,14400
EDS=["2008-11-05","2009-12-16","2010-12-31","2011-12-07","2012-11-20","2013-11-28","2014-11-17","2015-12-31",
"2016-12-23","2017-12-21","2018-12-21","2019-09-20","2020-11-30","2021-12-09","2022-07-08","2023-12-18",
"2024-11-29","2025-12-30","2026-11-11"]
d=json.load(open(src))
tr=Transformer.from_crs(4326,5186,always_xy=True)
groups=collections.defaultdict(list)
for w in d['ways']:
    op=w['operator'].replace('주식회사','(주)').replace(' (주)','(주)').strip()
    if op in ('한국도로공사','') or not w['coords']: continue
    groups[(op,w['opening'])].append(w['coords'])
pts={}; lens={}
for k,ws in groups.items():
    P=[]; L=0
    for c in ws:
        x,y=tr.transform([p[0] for p in c],[p[1] for p in c]); xy=np.c_[x,y]
        for a,b in zip(xy[:-1],xy[1:]):
            l=np.hypot(*(b-a)); L+=l; n=max(1,int(l//25))
            t=(np.arange(n)+0.5)/n; P.append(a+(b-a)*t[:,None])
    pts[k]=np.vstack(P); lens[k]=L/1000
res={str(k):{"len_km":round(lens[k],1),"n":len(pts[k]),"cov":{}} for k in pts}
for e in EDS:
    g=np.unpackbits(np.load(f"{griddir}/grid_{e}.npy"))[:NX*NY].reshape(NY,NX).astype(bool)
    for k,P in pts.items():
        ix=np.floor((P[:,0]-X0)/CS).astype(int); iy=np.floor((P[:,1]-Y0)/CS).astype(int)
        hit=np.zeros(len(P),bool)
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                jx=np.clip(ix+dx,0,NX-1); jy=np.clip(iy+dy,0,NY-1); hit|=g[jy,jx]
        res[str(k)]["cov"][e]=round(float(hit.mean()),3)
    del g; print(e,flush=True)
json.dump(res,open(out,'w'),ensure_ascii=False,indent=1)
