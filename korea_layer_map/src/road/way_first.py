# way마다 표준노드링크 판별 덮임 비율 → 처음 80% 넘은 판
import json, sys, numpy as np
from pyproj import Transformer
src, griddir, out = sys.argv[1:4]
X0,Y0,CS,NX,NY = -100000.0,0.0,50.0,17000,14400
EDS=["2008-11-05","2009-12-16","2010-12-31","2011-12-07","2012-11-20","2013-11-28","2014-11-17","2015-12-31",
"2016-12-23","2017-12-21","2018-12-21","2019-09-20","2020-11-30","2021-12-09","2022-07-08","2023-12-18",
"2024-11-29","2025-12-30","2026-11-11"]
d=json.load(open(src)); tr=Transformer.from_crs(4326,5186,always_xy=True)
W=[w for w in d['ways'] if len(w['coords'])>1]
P=[];owner=[];L=[]
for i,w in enumerate(W):
    x,y=tr.transform([p[0] for p in w['coords']],[p[1] for p in w['coords']]); xy=np.c_[x,y]; tot=0
    for a,b in zip(xy[:-1],xy[1:]):
        l=float(np.hypot(*(b-a))); tot+=l; n=max(1,int(l//25)); t=(np.arange(n)+0.5)/n
        P.append(a+(b-a)*t[:,None]); owner.append(np.full(n,i))
    L.append(tot)
P=np.vstack(P); owner=np.concatenate(owner)
ix=np.floor((P[:,0]-X0)/CS).astype(int); iy=np.floor((P[:,1]-Y0)/CS).astype(int)
cov=np.zeros((len(EDS),len(W)))
cnt=np.bincount(owner,minlength=len(W))
for k,e in enumerate(EDS):
    g=np.unpackbits(np.load(f"{griddir}/grid_{e}.npy"))[:NX*NY].reshape(NY,NX).astype(bool)
    hit=np.zeros(len(P),bool)
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            hit|=g[np.clip(iy+dy,0,NY-1),np.clip(ix+dx,0,NX-1)]
    cov[k]=np.bincount(owner,weights=hit,minlength=len(W))/np.maximum(cnt,1)
    del g; print(e,flush=True)
res=[]
for i,w in enumerate(W):
    c=cov[:,i]; f=next((EDS[k] for k in range(len(EDS)) if c[k]>=0.8),None)
    res.append(dict(id=w['id'],len=round(L[i]),first=f,cov=[round(float(v),2) for v in c]))
json.dump(res,open(out,'w'))
