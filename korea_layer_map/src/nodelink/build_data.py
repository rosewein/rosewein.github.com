import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW as _RAW, D as _D, W as _W  # 경로는 src/paths.py 한곳에서 정한다
OUT = str(_W("nodelink", "_")).rsplit("/", 1)[0]  # 중간 파일(격자·gpkg·요약)
SITE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "site")
import json, glob, numpy as np, geopandas as gpd, shapely
from PIL import Image
X0,Y0,CS=-100000.0,0.0,50.0; NX,NY=17000,14400
B=20  # 20 cells = 1km
S=json.load(open(f"{OUT}/summary.json"))
names=[]; nid={}
def nm(s):
    s=(s or "").strip()
    if s in ("-","0","None","nan"): s=""
    if s not in nid: nid[s]=len(names); names.append(s)
    return nid[s]
eds=[]
for e in S:
    d=e["date"]
    g=np.unpackbits(np.load(f"{OUT}/grid_{d}.npy"))[:NY*NX].reshape(NY,NX)
    c=g.reshape(NY//B,B,NX//B,B).sum(axis=(1,3)).astype(np.float32)
    v=(np.clip(c/30.0,0,1)**0.5*255).astype(np.uint8)[::-1]   # 북쪽이 위
    Image.fromarray(v,"L").save(f"{SITE}/net_{d}.png", optimize=True)
    rec={"d":d,"links":e["links"],"km":e["km"],"conn":e["conn_km"],"new":e.get("new_km",{}),"gone":e.get("gone_km",{}),
         "crs":e["crs"],"enc":e.get("enc","cp949"),"cells":int(g.sum())}
    segs=[]; top=[]
    try: gd=gpd.read_file(f"{OUT}/new_{d}.gpkg")
    except Exception: gd=None
    if gd is not None:
        gd=gd[gd["rank"].isin(["101","102","103","104","105","106"]) & ~gd["conn"].astype(bool)].copy()
        gd["ROAD_NAME"]=gd["ROAD_NAME"].fillna("").astype(str).str.strip()
        t=gd[gd["rank"]!="104"].groupby(["rank","ROAD_NAME"])["len"].sum().sort_values(ascending=False).head(10)
        top=[[r,nm(n),round(v/1000,1)] for (r,n),v in t.items()]
        geo=shapely.simplify(gd.geometry.values, 40)
        for r,n,L,gm in zip(gd["rank"],gd["ROAD_NAME"],gd["len"],geo):
            parts=[gm] if gm.geom_type=="LineString" else list(getattr(gm,"geoms",[]))
            for p in parts:
                xy=np.asarray(p.coords)
                q=np.round((xy-[X0,Y0])/20).astype(int)
                dq=np.vstack([q[:1],np.diff(q,axis=0)]).ravel().tolist()
                segs.append([int(r),nm(n),round(L/1000,2),dq])
    rec["top"]=top; rec["segs"]=segs
    eds.append(rec)
data={"grid":{"x0":X0,"y0":Y0,"cs":1000,"nx":NX//B,"ny":NY//B,"q":20},"eds":eds,"names":names}
json.dump(data,open(f"{SITE}/data.json","w"),ensure_ascii=False,separators=(",",":"))
print("names",len(names),"segs",sum(len(e["segs"]) for e in eds))
