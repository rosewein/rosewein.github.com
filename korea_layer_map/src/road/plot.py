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
gj=json.load(open(_W("road","재정고속도로_선형_20261127.geojson")))
F=gj["features"]
# 1) 해마다 쌓인 그림
years=[1970,1975,1980,1990,2000,2010,2020,2026]
fig,axs=plt.subplots(2,4,figsize=(16,11.5))
for ax,y in zip(axs.flat,years):
    old=[f["geometry"]["coordinates"] for f in F if f["properties"]["route_date"] and f["properties"]["route_date"]<=f"{y}-12-31"]
    rest=[f["geometry"]["coordinates"] for f in F if not(f["properties"]["route_date"] and f["properties"]["route_date"]<=f"{y}-12-31")]
    ax.add_collection(LineCollection(rest,colors="#d9dee5",linewidths=0.6))
    ax.add_collection(LineCollection(old,colors="#173f6b",linewidths=1.1))
    km=sum(1 for _ in old)
    ax.set_xlim(125.9,129.7); ax.set_ylim(34.5,38.4); ax.set_aspect(1/0.81); ax.axis("off")
    ax.set_title(f"{y}년 말" if y<2026 else "2026-11-27",fontsize=14)
fig.suptitle("재정 고속국도 — 구간표 날짜(처음 고속도로가 열린 날)로 본 연말 상태 (검사용, 민자 노선 빼고)",fontsize=15)
fig.text(0.5,0.02,"선은 지금 OSM 선형이다. 옛 선을 버린 구간(영동 대관령 등)과 선형이 없는 구간(경부 한남~양재, 경인 해제 구간)은 지금 선으로 그리거나 빠져 있다.",ha="center",fontsize=10,color="#555")
plt.savefig(_W("checks","check_snapshots.png"),dpi=110,bbox_inches="tight")
# 2) 지금 선형 날짜(연대별) + 메운 선·안 붙은 선
plt.close(); fig,axs=plt.subplots(1,2,figsize=(16,9.5))
ramp={1960:"#0b2545",1970:"#13315c",1980:"#1d4e89",1990:"#2f6fb3",2000:"#5591cf",2010:"#8ab4e3",2020:"#bcd4f0"}
ax=axs[0]
for dec,c in ramp.items():
    seg=[f["geometry"]["coordinates"] for f in F if f["properties"]["geom_date"][:3]==str(dec)[:3]]
    ax.add_collection(LineCollection(seg,colors=c,linewidths=1.2,label=f"{dec}년대"))
ax.set_title("지금 선형이 열린 연대 (선형 이설은 이설한 해)",fontsize=13); ax.legend(loc="lower right",fontsize=10,frameon=False)
ax=axs[1]
base=[f["geometry"]["coordinates"] for f in F if not f["properties"]["fill"]]
ax.add_collection(LineCollection(base,colors="#d9dee5",linewidths=0.7))
for tag,c,lw in (("맞은편 차로","#2f6fb3",1.8),("틈 메움","#0b2545",2.4),("안 붙음","#c2410c",2.4)):
    seg=[f["geometry"]["coordinates"] for f in F if f["properties"]["fill"]==tag]
    ax.add_collection(LineCollection(seg,colors=c,linewidths=lw,label=tag))
ax.set_title("경로로 바로 붙지 않은 선",fontsize=13); ax.legend(loc="lower right",fontsize=10,frameon=False)
for ax in axs: ax.set_xlim(125.9,129.7); ax.set_ylim(34.5,38.4); ax.set_aspect(1/0.81); ax.axis("off")
plt.savefig(_W("checks","check_dates.png"),dpi=110,bbox_inches="tight")
