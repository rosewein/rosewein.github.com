import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW as _RAW, D as _D, W as _W  # 경로는 src/paths.py 한곳에서 정한다
OUT = str(_W("nodelink", "_")).rsplit("/", 1)[0]  # 중간 파일(격자·gpkg·요약)
SITE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "site")
import geopandas as gpd, json, glob, os
rn={"101":"고속국도","102":"도시고속국도","103":"일반국도","104":"특별·광역시도","105":"국가지원지방도","106":"지방도","107":"시·군도"}
for f in sorted(glob.glob(f"{OUT}/new_*.gpkg")):
    d=_os.path.basename(f)[4:14]; g=gpd.read_file(f)
    g=g[g["rank"].isin(["101","102","103","105","106"]) & ~g["conn"].astype(bool)]
    g["ROAD_NAME"]=g["ROAD_NAME"].fillna("").str.strip()
    t=g.groupby(["rank","ROAD_NAME"])["len"].sum().sort_values(ascending=False).head(8)
    print(d, [(rn[r], n or "(이름 없음)", round(v/1000,1)) for (r,n),v in t.items()])
