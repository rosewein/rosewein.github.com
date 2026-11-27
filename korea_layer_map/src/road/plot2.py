import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW as _RAW, D as _D, W as _W  # 경로는 src/paths.py 한곳에서 정한다
import json, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
fp=[f for f in font_manager.findSystemFonts() if "NotoSansCJK-Regular" in f]
font_manager.fontManager.addfont(fp[0]); plt.rcParams["font.family"]=font_manager.FontProperties(fname=fp[0]).get_name()
F=json.load(open(_W("road","전국고속도로_선형_20261127.geojson")))["features"]
cum=json.load(open(_W("road","cum_len.json")))
years=[1970,1980,1990,2000,2005,2010,2020,2026]
fig,axs=plt.subplots(2,4,figsize=(16,11.5))
for ax,y in zip(axs.flat,years):
    lim=f"{y}-12-31" if y<2026 else "2026-11-27"
    def on(f): return f["properties"]["route_date"] and f["properties"]["route_date"]<=lim
    ax.add_collection(LineCollection([f["geometry"]["coordinates"] for f in F if not on(f)],colors="#dde2e8",linewidths=0.6))
    ax.add_collection(LineCollection([f["geometry"]["coordinates"] for f in F if on(f) and f["properties"]["owner"]=="재정"],colors="#173f6b",linewidths=1.1))
    ax.add_collection(LineCollection([f["geometry"]["coordinates"] for f in F if on(f) and f["properties"]["owner"]=="민자"],colors="#6b9bd1",linewidths=1.3))
    ax.set_xlim(125.9,129.7); ax.set_ylim(34.5,38.4); ax.set_aspect(1/0.81); ax.axis("off")
    ax.set_title(("2026-11-27" if y==2026 else f"{y}년 말")+f"  약 {cum[str(min(y,2026))]:,.0f}km",fontsize=13)
fig.legend(handles=[Line2D([],[],color="#173f6b",lw=2,label="재정(한국도로공사)"),Line2D([],[],color="#6b9bd1",lw=2,label="민자"),Line2D([],[],color="#dde2e8",lw=2,label="아직 없음")],loc="lower center",ncol=3,frameon=False,fontsize=11,bbox_to_anchor=(0.5,0.035))
fig.suptitle("전국 고속도로 — 연말 상태 (검사용, 길이는 OSM 양방향 합의 절반)",fontsize=15)
fig.text(0.5,0.015,"선은 지금 OSM 선형이다. 옛 선을 버린 구간은 지금 선으로 그렸고, 지금 고속도로가 아닌 구간(경부 한남~양재, 경인 해제 구간)은 빠져 있다.",ha="center",fontsize=10,color="#555")
plt.savefig(_W("checks","check_snapshots_all.png"),dpi=110,bbox_inches="tight")
