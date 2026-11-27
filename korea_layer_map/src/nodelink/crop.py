import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW as _RAW, D as _D, W as _W  # 경로는 src/paths.py 한곳에서 정한다
OUT = str(_W("nodelink", "_")).rsplit("/", 1)[0]  # 중간 파일(격자·gpkg·요약)
SITE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "site")
import json, glob, numpy as np
from PIL import Image
fs=sorted(glob.glob(f"{SITE}/net_*.png"))
m=None
for f in fs:
    a=np.array(Image.open(f))>0
    m=a if m is None else (m|a)
rows=np.where(m.any(1))[0]; cols=np.where(m.any(0))[0]
r0,r1=max(rows[0]-12,0),min(rows[-1]+12,m.shape[0]-1); c0,c1=max(cols[0]-12,0),min(cols[-1]+12,m.shape[1]-1)
for f in fs:
    Image.open(f).crop((c0,r0,c1+1,r1+1)).save(f,optimize=True)
d=json.load(open(f"{SITE}/data.json"))
X0=d["grid"]["x0"]; top=d["grid"]["y0"]+d["grid"]["ny"]*1000
d["img"]={"left":X0+c0*1000,"top":top-r0*1000,"w":int(c1-c0+1),"h":int(r1-r0+1),"cs":1000}
json.dump(d,open(f"{SITE}/data.json","w"),ensure_ascii=False,separators=(",",":"))
print(d["img"])
