import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW as _RAW, D as _D, W as _W  # 경로는 src/paths.py 한곳에서 정한다
import json, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.collections import LineCollection
fp=[f for f in font_manager.findSystemFonts() if "NotoSansCJK-Regular" in f]
font_manager.fontManager.addfont(fp[0]); plt.rcParams["font.family"]=font_manager.FontProperties(fname=fp[0]).get_name()
S=json.load(open(_D("road","전국고속도로_단순_20261127.geojson")))["features"]
O=json.load(open(_W("road","전국고속도로_선형_20261127.geojson")))["features"]
fig,axs=plt.subplots(1,3,figsize=(18,7.5))
views=[((125.9,129.7,34.5,38.4),"전국"),((126.6,127.35,37.2,37.75),"수도권"),((128.35,128.75,35.75,36.0),"대구 둘레")]
for ax,((x0,x1,y0,y1),t) in zip(axs,views):
    ax.add_collection(LineCollection([f["geometry"]["coordinates"] for f in O],colors="#e3e7ec",linewidths=2.2))
    for own,c in (("재정","#173f6b"),("민자","#6b9bd1")):
        ax.add_collection(LineCollection([f["geometry"]["coordinates"] for f in S if f["properties"]["owner"]==own],colors=c,linewidths=0.9 if t=="전국" else 1.3))
    ax.set_xlim(x0,x1); ax.set_ylim(y0,y1); ax.set_aspect(1/0.81); ax.axis("off"); ax.set_title(t,fontsize=13)
fig.suptitle("단순화한 고속도로(진한 파랑 재정, 옅은 파랑 민자) 위에 원래 양방향 선(회색)",fontsize=14)
plt.savefig(_W("checks","check_simplify.png"),dpi=110,bbox_inches="tight")
