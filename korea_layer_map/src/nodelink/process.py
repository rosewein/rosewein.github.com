# 표준노드링크 판마다: 등급별 길이 요약 + 바로 앞 판 도로망에서 100m 넘게 떨어진 링크(새로 실린 도로) 뽑기
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW as _RAW, D as _D, W as _W  # 경로는 src/paths.py 한곳에서 정한다
OUT = str(_W("nodelink", "_")).rsplit("/", 1)[0]  # 중간 파일(격자·gpkg·요약)
SITE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "site")
import os, sys, json, shutil, subprocess, time
import numpy as np, pyogrio, shapely, geopandas as gpd
D = str(_RAW)
ED = [("2008-11-05","[20081105버전]전국표준노드링크.zip"),("2009-12-16","전국표준노드링크2009_12_16.zip"),
("2010-12-31","[전국표준노드링크]20101231.zip"),("2011-12-07","[전국표준노드링크]20111207.zip"),
("2012-11-20","[전국표준노드링크]20121120.zip"),("2013-11-28","[전국표준노드링크]20131128.zip"),
("2014-11-17","[전국표준노드링크]20141117.zip"),("2015-12-31","[2015-12-31]+전국표준노드링크.zip"),
("2016-12-23","[2016-12-23]+전국표준노드링크.zip"),("2017-12-21","[2017-12-21]+전국표준노드링크.zip"),
("2018-12-21","[2018-12-21]전국표준노드링크.zip"),("2019-09-20","[2019-09-20]+전국표준노드링크.zip"),
("2020-11-30","[2020-11-30]NODELINKDATA.zip"),("2021-12-09","[2021-12-09]NODELINKDATA.zip"),
("2022-07-08","[2022-07-08]NODELINKDATA.zip"),("2023-12-18","[2023-12-18]NODELINKDATA.zip"),
("2024-11-29","[2024-11-29]NODELINKDATA.zip"),("2025-12-30","[2025-12-30]NODELINKDATA.zip"),
("2026-11-11","[2026-11-11]NODELINKDATA.zip")]
X0,Y0,CS = -100000.0, 0.0, 50.0
NX,NY = 17000, 14400
STEP=25.0; R=2   # 25m 간격 점, 50m 칸, 둘레 2칸(=100m)
os.makedirs(OUT, exist_ok=True)

def dilate(g, r=R):
    h=g.copy()
    for d in range(1,r+1):
        h[:,d:]|=g[:,:-d]; h[:,:-d]|=g[:,d:]
    v=h.copy()
    for d in range(1,r+1):
        v[d:,:]|=h[:-d,:]; v[:-d,:]|=h[d:,:]
    return v

def cells(xy):
    ix=np.floor((xy[:,0]-X0)/CS).astype(np.int64); iy=np.floor((xy[:,1]-Y0)/CS).astype(np.int64)
    ok=(ix>=0)&(ix<NX)&(iy>=0)&(iy<NY)
    return ix,iy,ok

def is_conn(v):
    s=str(v).strip()
    return s not in ("0","000","","None","nan")

prev=None
START=sys.argv[1] if len(sys.argv)>1 else None
summary=json.load(open(f"{OUT}/summary.json")) if START else []
eds=ED if not START else ED[[d for d,_ in ED].index(START)-1:]
first_resume=bool(START)
for date, fn in eds:
    t=time.time()
    tmp=f"{OUT}/unzip_{date}"
    subprocess.run([sys.executable,"-I",_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),"extract.py"),os.path.join(D,fn),tmp],check=True,capture_output=True)
    shp=f"{tmp}/MOCT_LINK.shp"
    enc="cp949"
    cpg=shp[:-4]+".cpg"
    if os.path.exists(cpg) and "UTF" in open(cpg).read().upper(): enc="utf-8"
    else:
        try:
            t8=pyogrio.read_dataframe(shp, columns=None, read_geometry=False, max_features=20000, encoding="utf-8")
            sc=" ".join(t8.select_dtypes("object").astype(str).values.ravel()[:200000])
            if sc.count("\ufffd")==0 and any("\uac00"<=ch<="\ud7a3" for ch in sc): enc="utf-8"
        except Exception: pass
    info=pyogrio.read_info(shp, encoding=enc)
    fmap={f.upper().rstrip("_"):f for f in info["fields"]}
    want=[fmap[c] for c in ["LINK_ID","ROAD_RANK","ROAD_NAME","CONNECT","LANES","ROAD_NO"] if c in fmap]
    df=pyogrio.read_dataframe(shp, columns=want, encoding=enc)
    df=df.rename(columns={v:k for k,v in fmap.items() if v in want})
    prj=open(shp[:-4]+".prj").read()
    if "PROJCS" in prj:
        assert "Central_Belt" in prj and "127" in prj, prj[:200]
        df=df.set_crs(5186, allow_override=True); crs="TM 중부원점(Central Belt 60)"
    else:
        df=df.set_crs(4326, allow_override=True).to_crs(5186); crs="경위도(ITRF2000)"
    df=df[~df.geometry.is_empty & df.geometry.notna()].reset_index(drop=True)
    df["rank"]=df["ROAD_RANK"].astype(str).str.strip()
    df["conn"]=df["CONNECT"].map(is_conn) if "CONNECT" in df else False
    df["len"]=shapely.length(df.geometry.values)
    # 요약
    s={"date":date,"file":fn,"crs":crs,"enc":enc,"links":int(len(df)),"km":{},"conn_km":round(float(df.loc[df.conn,"len"].sum())/1000,1)}
    for rk,g in df[~df.conn].groupby("rank"): s["km"][rk]=round(float(g["len"].sum())/1000,1)
    # 점 찍기
    lin_parts=[]; idx_parts=[]
    G=df.geometry.values
    for a in range(0,len(G),150000):
        seg=shapely.segmentize(G[a:a+150000], STEP)
        xy,ii=shapely.get_coordinates(seg, return_index=True); del seg
        ix,iy,ok=cells(xy); del xy
        lin=np.where(ok, iy*NX+ix, -1).astype(np.int32)
        lin_parts.append(lin); idx_parts.append((ii+a).astype(np.int32))
        del ix,iy,ok,ii
    lin=np.concatenate(lin_parts); idx=np.concatenate(idx_parts); del lin_parts, idx_parts
    ok=lin>=0
    grid=np.zeros(NY*NX,dtype=bool); grid[lin[ok]]=True; grid=grid.reshape(NY,NX)
    cur={"grid":grid,"lin":lin,"idx":idx,"df":df[["rank","ROAD_NAME","conn","len","geometry"]] if "ROAD_NAME" in df else df[["rank","conn","len","geometry"]]}
    if prev is not None:
        pd_=dilate(prev["grid"]).reshape(-1)
        cov=np.zeros(len(lin),dtype=bool); cov[ok]=pd_[lin[ok]]; del pd_
        n=np.bincount(idx, minlength=len(df)); c=np.bincount(idx, weights=cov, minlength=len(df))
        frac_new=1-c/np.maximum(n,1)
        new=(frac_new>=0.8)&(df["len"].values>=100)
        nd=df[new]
        s["new_km"]={rk:round(float(g["len"].sum())/1000,1) for rk,g in nd[~nd.conn].groupby("rank")}
        s["new_conn_km"]=round(float(nd.loc[nd.conn,"len"].sum())/1000,1)
        # 앞 판에는 있고 이번 판엔 없는(100m 밖) 링크
        cd=dilate(grid).reshape(-1); p=prev
        pok=p["lin"]>=0
        pc=np.zeros(len(p["idx"]),dtype=bool); pc[pok]=cd[p["lin"][pok]]; del cd
        pn=np.bincount(p["idx"],minlength=len(p["df"])); pcc=np.bincount(p["idx"],weights=pc,minlength=len(p["df"]))
        gone=(1-pcc/np.maximum(pn,1)>=0.8)&(p["df"]["len"].values>=100)
        gd=p["df"][gone]
        s["gone_km"]={rk:round(float(g["len"].sum())/1000,1) for rk,g in gd[~gd.conn].groupby("rank")}
        # 새 링크 저장(등급 101–106, 연결로 포함 표시)
        keep=nd[nd["rank"].isin(["101","102","103","104","105","106","107"])].copy()
        keep["geometry"]=shapely.simplify(keep.geometry.values, 20)
        keep[["rank","ROAD_NAME","conn","len","geometry"]].to_file(f"{OUT}/new_{date}.gpkg", driver="GPKG")
        gd2=gd[gd["rank"].isin(["101","102","103","105","106"])].copy()
        gd2["geometry"]=shapely.simplify(gd2.geometry.values, 20)
        gd2[["rank","ROAD_NAME","conn","len","geometry"]].to_file(f"{OUT}/gone_{date}.gpkg", driver="GPKG")
    elif not START:
        b=df[df["rank"].isin(["101","102","103","104","105","106","107"])].copy()
        b["geometry"]=shapely.simplify(b.geometry.values, 20)
        b[["rank","ROAD_NAME","conn","len","geometry"]].to_file(f"{OUT}/base_{date}.gpkg", driver="GPKG")
    np.save(f"{OUT}/grid_{date}.npy", np.packbits(grid))
    if date=="2026-11-11":
        b=df[df["rank"].isin(["101","102","103","105","106"]) & ~df.conn].copy()
        b["geometry"]=shapely.simplify(b.geometry.values, 20)
        b[["rank","ROAD_NAME","conn","len","geometry"]].to_file(f"{OUT}/last_{date}.gpkg", driver="GPKG")
    prev=cur
    shutil.rmtree(tmp)
    if first_resume:
        first_resume=False; print("resume base", date, flush=True); continue
    summary=[x for x in summary if x["date"]!=date]+[s]
    summary.sort(key=lambda x:x["date"])
    json.dump(summary, open(f"{OUT}/summary.json","w"), ensure_ascii=False, indent=1)
    print(date, crs, s["links"], s["km"], "new:", s.get("new_km"), "gone:", s.get("gone_km"), f"{time.time()-t:.0f}s", flush=True)
